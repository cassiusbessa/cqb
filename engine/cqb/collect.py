"""Diff-scoped file collection. Never walks the whole module."""

from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path


GENERATED_SUFFIXES = (".sql.go",)
GENERATED_BASENAMES = {"models.go"}
GENERATED_DIR_MARKERS = ("/docs/",)


def is_generated(rel: str) -> bool:
    norm = rel.replace("\\", "/")
    base = os.path.basename(norm)
    if any(norm.endswith(s) for s in GENERATED_SUFFIXES):
        return True
    if base in GENERATED_BASENAMES:
        return True
    if any(m in f"/{norm}/" or norm.startswith("docs/") or f"/{m.strip('/')}/" in f"/{norm}/" for m in ("docs/",)):
        if "/docs/" in f"/{norm}" or norm.startswith("docs/"):
            return True
    return False


def _norm_rel(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("./")


def module_rel(git_path: str, prefixes: list[str] | None) -> str:
    """Strip the first matching prefix. Overlapping prefixes: most-specific first."""
    norm = _norm_rel(git_path)
    if not prefixes:
        return norm
    for p in prefixes:
        p = _norm_rel(p).rstrip("/")
        if not p:
            continue
        if norm == p:
            return ""
        if norm.startswith(p + "/"):
            return norm[len(p) + 1 :]
    return norm


def match_paths(git_path: str, prefixes: list[str] | None) -> list[str]:
    """Git-relative path plus module-relative path (prefix stripped)."""
    norm = _norm_rel(git_path)
    out = [norm]
    stripped = module_rel(norm, prefixes)
    if stripped not in out:
        out.append(stripped)
    return out


def matches_prefix(rel: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return True
    norm = _norm_rel(rel)
    for p in prefixes:
        p = _norm_rel(p).rstrip("/")
        if not p:
            return True
        if norm == p or norm.startswith(p + "/"):
            return True
    return False


def _glob_one(norm: str, g: str) -> bool:
    g = g.replace("\\", "/")
    if not g:
        return False
    if fnmatch.fnmatch(norm, g) or fnmatch.fnmatch(os.path.basename(norm), g):
        return True
    if g.endswith("/**"):
        base = g[:-3].rstrip("/")
        if norm == base or (base and norm.startswith(base + "/")):
            return True
        if fnmatch.fnmatch(norm, g):
            return True
    # Directory include: "internal/" matches internal and anything under it.
    if "*" not in g and "?" not in g and "[" not in g and g.endswith("/"):
        base = g.rstrip("/")
        if norm == base or norm.startswith(base + "/"):
            return True
    if g.endswith("*") and not g.endswith("**"):
        stem = g.rstrip("*").rstrip("/")
        if stem and (norm == stem or norm.startswith(stem)):
            return True
    return False


def matches_globs(rel: str, globs: list[str], prefixes: list[str] | None = None) -> bool:
    if not globs:
        return False
    for cand in match_paths(rel, prefixes):
        for g in globs:
            if _glob_one(cand, g.replace("\\", "/")):
                return True
    return False


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return r.stdout


def collect_files(root: Path, mode: str, explicit: list[str] | None = None) -> list[str]:
    root = root.resolve()
    names: list[str] = []
    if mode == "file-list":
        names = [n.replace("\\", "/") for n in (explicit or [])]
    elif mode == "staged":
        names = _git(root, "diff", "--cached", "--name-only", "-z").split("\0")
    elif mode == "push":
        # Prefer upstream...HEAD; fall back to HEAD (empty if nothing to compare).
        out = _git(root, "diff", "--name-only", "@{u}...HEAD")
        if not out.strip():
            out = _git(root, "diff", "--name-only", "HEAD")
        names = out.splitlines()
    else:  # uncommitted: working tree vs HEAD including untracked
        names = _git(root, "diff", "--name-only", "HEAD").splitlines()
        names += _git(root, "diff", "--cached", "--name-only").splitlines()
        porcelain = _git(root, "status", "--porcelain", "-u")
        for line in porcelain.splitlines():
            if len(line) < 4:
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            names.append(path)
    cleaned: list[str] = []
    seen: set[str] = set()
    for n in names:
        n = n.strip().replace("\\", "/").strip("\0")
        if not n or n in seen:
            continue
        seen.add(n)
        if is_generated(n):
            continue
        cleaned.append(n)
    return cleaned
