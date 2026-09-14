"""E2E catalog plus implied-suite execution (`go test -tags e2e`)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .collect import matches_globs


@dataclass
class E2EResult:
    color: str
    reason: str
    implied: list[str]
    catalog_errors: list[str]
    suite_dirs: list[str] = field(default_factory=list)


def resolve_catalog_dir(root: Path, catalog_root: str, prefixes: list[str] | None) -> Path | None:
    """Prefer catalog_root as written, then prefix/catalog_root, then prefix/internal/e2e."""
    written = root / catalog_root
    if written.is_dir():
        return written
    for p in prefixes or []:
        p = p.replace("\\", "/").strip("/")
        if not p:
            continue
        nested = root / p / catalog_root
        if nested.is_dir():
            return nested
        fallback = root / p / "internal" / "e2e"
        if fallback.is_dir():
            return fallback
    return None


def _literal_exists(root: Path, line: str, prefixes: list[str] | None) -> bool:
    if (root / line).exists():
        return True
    for p in prefixes or []:
        p = p.replace("\\", "/").strip("/")
        if p and (root / p / line).exists():
            return True
    return False


def evaluate_catalog(
    root: Path,
    catalog_root: str,
    diff_files: list[str],
    prefixes: list[str] | None = None,
) -> E2EResult:
    base = resolve_catalog_dir(root, catalog_root, prefixes)
    if base is None:
        return E2EResult(color="skip", reason="no e2e catalog directory", implied=[], catalog_errors=[])

    errors: list[str] = []
    implied: list[str] = []
    suite_dirs: list[str] = []
    any_suite = False
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        any_suite = True
        globs_file = child / "globs.txt"
        if not globs_file.is_file():
            errors.append(f"missing globs.txt in {child.relative_to(root)}")
            continue
        patterns: list[str] = []
        for line in globs_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
            if "*" not in line and "?" not in line:
                if not _literal_exists(root, line, prefixes):
                    errors.append(f"glob path missing: {line} (suite {child.name})")
        if any(matches_globs(f, patterns, prefixes=prefixes) for f in diff_files):
            implied.append(child.name)
            try:
                suite_dirs.append(str(child.relative_to(root)).replace("\\", "/"))
            except ValueError:
                suite_dirs.append(child.name)

    if errors:
        return E2EResult(
            color="red",
            reason="catalog broken: " + "; ".join(errors),
            implied=[],
            catalog_errors=errors,
        )
    if not any_suite:
        return E2EResult(color="skip", reason="no e2e suites", implied=[], catalog_errors=[])
    if not implied:
        return E2EResult(color="skip", reason="no suite glob matches the diff", implied=[], catalog_errors=[])
    return E2EResult(
        color="yellow",
        reason=f"suites implied: {', '.join(implied)}",
        implied=implied,
        catalog_errors=[],
        suite_dirs=suite_dirs,
    )


def run_implied_suites(root: Path, suite_dirs: list[str], timeout: str = "8m") -> tuple[int, str]:
    """Run `go test -tags e2e` for each suite dir. Returns (exit, combined stderr/stdout)."""
    logs: list[str] = []
    worst = 0
    for rel in suite_dirs:
        pkg = "./" + rel.replace("\\", "/").lstrip("./")
        r = subprocess.run(
            ["go", "test", "-tags", "e2e", "-count=1", "-timeout", timeout, pkg],
            cwd=root,
            capture_output=True,
            text=True,
        )
        blob = (r.stdout or "") + (r.stderr or "")
        logs.append(f"{pkg}: exit {r.returncode}\n{blob}")
        if r.returncode != 0:
            worst = r.returncode
    return worst, "\n".join(logs)


def evaluate_e2e(
    root: Path,
    catalog_root: str,
    diff_files: list[str],
    prefixes: list[str] | None,
    docker_present: bool,
    *,
    execute: bool = True,
) -> E2EResult:
    cat = evaluate_catalog(root, catalog_root, diff_files, prefixes=prefixes)
    if cat.color in ("red", "skip") or not cat.implied:
        return cat
    if not docker_present:
        return E2EResult(
            color="unavailable",
            reason="docker missing while e2e suite implied",
            implied=cat.implied,
            catalog_errors=[],
            suite_dirs=cat.suite_dirs,
        )
    if not execute:
        return cat
    code, log = run_implied_suites(root, cat.suite_dirs)
    if code == 0:
        return E2EResult(
            color="green",
            reason=f"suites implied: {', '.join(cat.implied)}",
            implied=cat.implied,
            catalog_errors=[],
            suite_dirs=cat.suite_dirs,
        )
    return E2EResult(
        color="red",
        reason=f"e2e failed: {', '.join(cat.implied)}",
        implied=cat.implied,
        catalog_errors=[log[:4000]],
        suite_dirs=cat.suite_dirs,
    )
