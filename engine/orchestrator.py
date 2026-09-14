#!/usr/bin/env python3
"""CQB orchestrator: diff-scoped gate. Exit 1 only when a slot is red."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Allow running from a vendored .cqb/engine/ tree or from the kit checkout.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cqb import bundle as bundlemod  # noqa: E402
from cqb.collect import collect_files, matches_globs, matches_prefix  # noqa: E402
from cqb.complexity import classify  # noqa: E402
from cqb.config import load_config  # noqa: E402
from cqb.cover import evaluate_cover  # noqa: E402
from cqb.e2e import evaluate_e2e  # noqa: E402
from cqb.gitutil import added_lines_for_file, git_show  # noqa: E402
from cqb.hunters import (  # noqa: E402
    boundary_findings,
    content_findings,
    placebo_findings,
    quick_test_findings,
    unique_findings,
)
from cqb.hygiene import evaluate_hygiene  # noqa: E402
from cqb.mutation import evaluate_mutation  # noqa: E402


def _read(root: Path, rel: str) -> str | None:
    p = root / rel
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return None


def _added_lines(root: Path, rel: str, src: str, mode: str) -> tuple[str | None, set[int]]:
    head = git_show(root, f"HEAD:{rel}")
    if head is None:
        return None, set(range(1, src.count("\n") + 2))
    return head, added_lines_for_file(root, rel, mode)


def _generate_coverprofile(root: Path, files: list[str], allowlist: list[str], prefixes: list[str]) -> str:
    scoped = [
        f
        for f in files
        if matches_globs(f, allowlist, prefixes=prefixes) and f.endswith(".go") and not f.endswith("_test.go")
    ]
    if not scoped:
        return "mode: set\n"
    pkgs = sorted({"./" + (os.path.dirname(f).replace("\\", "/") or ".") for f in scoped})
    work = root / ".cqb" / "work"
    work.mkdir(parents=True, exist_ok=True)
    dest = work / "cover.out"
    subprocess.run(
        ["go", "test", "-vet=off", "-coverprofile", str(dest), *pkgs],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if dest.is_file():
        return dest.read_text(encoding="utf-8")
    return "mode: set\n"


def _io_files(root: Path, files: list[str], io_imports: list[str]) -> set[str]:
    hit: set[str] = set()
    for rel in files:
        src = _read(root, rel)
        if not src:
            continue
        for imp in io_imports:
            if f'"{imp}"' in src:
                hit.add(rel)
                break
    return hit


def run(root: Path, mode: str, explicit: list[str] | None, extra_cover: str | None, extra_mut: str | None) -> dict:
    cfg = load_config(root / "cqb.yaml")
    files = collect_files(root, mode, explicit)
    prefixes = cfg.prefix_list()
    in_prefix = [f for f in files if matches_prefix(f, prefixes)]
    if prefixes and not in_prefix:
        return bundlemod.empty_skip(
            mode,
            reason="diff outside configured prefix",
            ignored_keys=cfg.ignored_keys,
        )

    scoped = in_prefix if prefixes else files
    go_files = [f for f in scoped if f.endswith(".go")]

    hy = evaluate_hygiene(root, go_files)
    lint_slot = bundlemod.slot(hy.color, reason=hy.reason, gofmt=hy.gofmt, vet=hy.vet, build=hy.build)

    ceilings = {
        "cognitive": cfg.complexity.cognitive,
        "cyclomatic": cfg.complexity.cyclomatic,
        "nested_if": cfg.complexity.nested_if,
        "delta": cfg.complexity.delta,
    }
    complexity_rows = []
    new_names_by_file: dict[str, list[str]] = {}
    for rel in go_files:
        if rel.endswith("_test.go"):
            continue
        src = _read(root, rel)
        if src is None:
            continue
        head = git_show(root, f"HEAD:{rel}")
        added = added_lines_for_file(root, rel, mode) if head is not None else set()
        rows = classify(
            file=rel,
            current_src=src,
            head_src=head,
            added_lines=added,
            ceilings=ceilings,
        )
        complexity_rows.extend(rows)
        new_names_by_file[rel] = [r.name for r in rows if r.kind == "new"]

    cx_yellow = [r for r in complexity_rows if r.yellow]
    if cx_yellow:
        cx_slot = bundlemod.slot(
            "yellow",
            reason="complexity over ceiling (never red)",
            functions=[r.__dict__ for r in complexity_rows],
        )
    elif complexity_rows:
        cx_slot = bundlemod.slot("green", reason="complexity under ceiling", functions=[r.__dict__ for r in complexity_rows])
    else:
        cx_slot = bundlemod.slot("skip", reason="no functions in scope", functions=[])

    hunter_hits = []
    seen_test: set[str] = set()
    for rel in go_files:
        if rel.endswith("_test.go"):
            if rel in seen_test:
                continue
            seen_test.add(rel)
            hunter_hits.extend(
                content_findings(
                    rel=rel,
                    test_src=_read(root, rel) or "",
                    allowlist=cfg.red_allowlist,
                    prefixes=prefixes,
                )
            )
            hunter_hits.extend(
                placebo_findings(
                    rel=rel,
                    test_src=_read(root, rel) or "",
                    allowlist=cfg.red_allowlist,
                    enabled="placebo_validator" in cfg.extra_hunters,
                    prefixes=prefixes,
                )
            )
            continue
        src = _read(root, rel) or ""
        test_rel = rel[:-3] + "_test.go"
        test_src = _read(root, test_rel)
        _, added = _added_lines(root, rel, src, mode)
        hunter_hits.extend(
            quick_test_findings(
                rel=rel,
                src=src,
                test_src=test_src,
                testable_include=cfg.testable.include,
                testable_exclude=cfg.testable.exclude,
                allowlist=cfg.red_allowlist,
                new_func_names=new_names_by_file.get(rel, []),
                prefixes=prefixes,
            )
        )
        hunter_hits.extend(
            boundary_findings(
                rel=rel,
                src=src,
                test_src=test_src,
                added_lines=added,
                allowlist=cfg.red_allowlist,
                prefixes=prefixes,
            )
        )
        if test_src and test_rel not in seen_test:
            seen_test.add(test_rel)
            hunter_hits.extend(
                content_findings(
                    rel=test_rel,
                    test_src=test_src,
                    allowlist=cfg.red_allowlist,
                    prefixes=prefixes,
                )
            )

    hunter_hits = unique_findings(hunter_hits)
    if hunter_hits:
        if any(h.color == "red" for h in hunter_hits):
            h_color = "red"
        else:
            h_color = "yellow"
        hunters_slot = bundlemod.slot(
            h_color,
            reason=f"{len(hunter_hits)} hunter finding(s)",
            findings=[h.__dict__ for h in hunter_hits],
        )
    else:
        hunters_slot = bundlemod.slot("green", reason="no hunter findings", findings=[])

    docker_present = shutil.which("docker") is not None
    e2e = evaluate_e2e(root, cfg.e2e.catalog_root, scoped, prefixes, docker_present)
    e2e_slot = bundlemod.slot(
        e2e.color,
        reason=e2e.reason,
        implied=e2e.implied,
        catalog_errors=e2e.catalog_errors,
    )

    invoked_pure: set[str] = set()
    for rel, names in new_names_by_file.items():
        test_src = _read(root, rel[:-3] + "_test.go") or ""
        for n in names:
            if f"{n}(" in test_src:
                invoked_pure.add(rel)

    coverprofile = extra_cover
    env_profile = os.environ.get("CQB_COVERPROFILE")
    if not coverprofile and env_profile and Path(env_profile).is_file():
        coverprofile = Path(env_profile).read_text(encoding="utf-8")
    if not coverprofile and cfg.red_allowlist:
        coverprofile = _generate_coverprofile(root, go_files, cfg.red_allowlist, prefixes)

    cov = evaluate_cover(
        allowlist=cfg.red_allowlist,
        diff_files=go_files,
        coverprofile=coverprofile,
        baseline_path=root / cfg.cover.baseline_path,
        rewrite_baseline=False,
        io_floor=cfg.cover.io_floor,
        io_files=_io_files(root, go_files, cfg.io_imports),
        invoked_pure=invoked_pure,
        prefixes=prefixes,
    )
    cover_slot = bundlemod.slot(cov.color, reason=cov.reason, files=cov.files)

    # Mutation runs when a new symbol HAS an invoking test.
    new_tested = False
    for rel, names in new_names_by_file.items():
        test_src = _read(root, rel[:-3] + "_test.go") or ""
        for n in names:
            if f"Test{n}" in test_src and f"{n}(" in test_src:
                new_tested = True
    mut_json = extra_mut
    env_mut = os.environ.get("CQB_MUTATION_JSON")
    if not mut_json and env_mut and Path(env_mut).is_file():
        mut_json = Path(env_mut).read_text(encoding="utf-8")
    mut = evaluate_mutation(
        tool_present=shutil.which("gremlins") is not None or bool(mut_json),
        report_path=None,
        report_json=mut_json,
        should_run=new_tested,
    )
    # Missing tool: unavailable even if should_run. Fixture JSON counts as a report (tests).
    if new_tested and shutil.which("gremlins") is None and not mut_json:
        mut_slot = bundlemod.slot("unavailable", reason="gremlins not on PATH", survivors=[])
    else:
        mut_slot = bundlemod.slot(mut.color, reason=mut.reason, survivors=mut.survivors)

    test_slot = bundlemod.slot("skip", reason="package tests are not auto-run in v1 orchestrator (hygiene covers build)")
    # Quick-test lives under hunters; keep a test slot for bundle shape.
    if any(h.hunter == "quick_test" for h in hunter_hits):
        qt = [h for h in hunter_hits if h.hunter == "quick_test"]
        tcolor = "red" if any(h.color == "red" for h in qt) else "yellow"
        test_slot = bundlemod.slot(tcolor, reason="missing invoking tests on new symbols", findings=[h.__dict__ for h in qt])
    elif new_tested:
        test_slot = bundlemod.slot("green", reason="new symbols have invoking tests")

    ignored_note = ""
    if cfg.ignored_keys:
        ignored_note = "ignored constitution-breaking keys: " + ", ".join(cfg.ignored_keys)

    return bundlemod.assemble(
        mode=mode,
        skipped=False,
        skip_reason=ignored_note,
        ignored_keys=cfg.ignored_keys,
        slots={
            "lint": lint_slot,
            "test": test_slot,
            "e2e": e2e_slot,
            "cover": cover_slot,
            "hunters": hunters_slot,
            "mutation": mut_slot,
            "complexity": cx_slot,
        },
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cqb-engine", description="CQB quality-gate orchestrator")
    p.add_argument("--root", required=True)
    p.add_argument("--mode", default="uncommitted", choices=["uncommitted", "staged", "file-list", "push"])
    p.add_argument("--files", default="", help="comma-separated paths for file-list mode")
    p.add_argument("--output", default="")
    p.add_argument("--coverprofile", default="")
    p.add_argument("--mutation-json", default="")
    args = p.parse_args(argv)
    root = Path(args.root).resolve()
    files = [f for f in args.files.split(",") if f] if args.files else []
    cover = Path(args.coverprofile).read_text(encoding="utf-8") if args.coverprofile else None
    mut = Path(args.mutation_json).read_text(encoding="utf-8") if args.mutation_json else None
    doc = run(root, args.mode, files or None, cover, mut)
    text = json.dumps(doc, indent=2)
    out = args.output or os.environ.get("CQB_OUTPUT", "")
    if out:
        dest = Path(out)
        if not dest.is_absolute():
            dest = root / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text + "\n", encoding="utf-8")
    sys.stdout.write(text + "\n")
    return _exit_code(doc, args.mode)


def _exit_code(doc: dict, mode: str) -> int:
    if doc.get("has_red"):
        return 1
    e2e = (doc.get("slots") or {}).get("e2e") or {}
    # Flagged push: implied e2e without Docker is as blocking as hygiene red.
    if mode == "push" and e2e.get("color") == "unavailable" and e2e.get("implied"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
