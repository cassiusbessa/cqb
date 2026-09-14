"""Cover slot: allowlist only. Empty allowlist → skip. Hook never rewrites the baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .collect import matches_globs


@dataclass
class CoverResult:
    color: str
    reason: str
    files: list[dict]


def _parse_coverprofile(text: str) -> dict[str, tuple[int, int]]:
    """file -> (covered_stmts, total_stmts) from go coverprofile."""
    files: dict[str, list[tuple[int, int]]] = {}
    for line in text.splitlines():
        if line.startswith("mode:") or not line.strip():
            continue
        # path:start.line,start.col,end.line,end.col numstmts count
        try:
            loc, rest = line.rsplit(" ", 2)[0], line.split()
            if len(rest) < 3:
                continue
            numstmts = int(rest[-2])
            count = int(rest[-1])
            path = rest[0].split(":")[0]
        except (ValueError, IndexError):
            continue
        files.setdefault(path, []).append((numstmts, count))
    out: dict[str, tuple[int, int]] = {}
    for path, rows in files.items():
        total = sum(n for n, _ in rows)
        covered = sum(n for n, c in rows if c > 0)
        out[path] = (covered, total)
    return out


def evaluate_cover(
    *,
    allowlist: list[str],
    diff_files: list[str],
    coverprofile: str | None,
    baseline_path: Path | None,
    rewrite_baseline: bool,
    io_floor: int,
    io_files: set[str],
    invoked_pure: set[str],
    prefixes: list[str] | None = None,
) -> CoverResult:
    if rewrite_baseline:
        # Constitution: the hook/run path must not rewrite. Callers pass False.
        raise AssertionError("cover baseline must not be rewritten by the gate run")
    if not allowlist:
        return CoverResult(color="skip", reason="empty red allowlist", files=[])

    scoped = [
        f
        for f in diff_files
        if matches_globs(f, allowlist, prefixes=prefixes) and f.endswith(".go") and not f.endswith("_test.go")
    ]
    if not scoped:
        return CoverResult(color="skip", reason="no allowlist production files in diff", files=[])
    # Missing profile is 0% (invocation / I/O floor still apply). Never yellow for "no flag".
    if not coverprofile:
        coverprofile = "mode: set\n"

    stats = _parse_coverprofile(coverprofile)
    baseline: dict[str, float] = {}
    if baseline_path and baseline_path.is_file():
        try:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            baseline = {}

    details: list[dict] = []
    red = False
    yellow = False
    stale = False
    for rel in scoped:
        # coverprofile paths may be module-qualified; match by suffix
        hit = None
        for k, v in stats.items():
            if k.endswith(rel) or k.endswith("/" + rel) or rel.endswith(k):
                hit = v
                break
        covered, total = hit if hit else (0, 0)
        pct = (100.0 * covered / total) if total else 0.0
        is_io = rel in io_files or any(rel.endswith(x) or x.endswith(rel) for x in io_files)
        rec = {"file": rel, "pct": round(pct, 1), "io": is_io}
        if is_io and pct < io_floor:
            rec["issue"] = f"I/O cover {pct:.1f}% < {io_floor}%"
            red = True
        elif not is_io and rel not in invoked_pure:
            rec["issue"] = "pure helper on allowlist lacks invoking test"
            red = True
        prev = baseline.get(rel)
        if prev is not None:
            if pct + 0.05 < float(prev):
                rec["issue"] = f"ratchet: {pct:.1f}% < baseline {prev}"
                red = True
            elif pct > float(prev) + 0.5:
                rec["stale_baseline"] = True
                yellow = True
                stale = True
        details.append(rec)

    if red:
        return CoverResult(color="red", reason="allowlist cover below floor or ratchet", files=details)
    if stale:
        return CoverResult(color="yellow", reason="stale cover baseline (real cover higher than recorded)", files=details)
    if yellow:
        return CoverResult(color="yellow", reason="cover incomplete", files=details)
    return CoverResult(color="green", reason="allowlist cover ok", files=details)
