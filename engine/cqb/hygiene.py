"""gofmt / go vet / go build on packages of the scoped files. Failures are red."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HygieneResult:
    color: str
    reason: str
    gofmt: list[str]
    vet: str
    build: str


def _packages(files: list[str]) -> list[str]:
    pkgs: set[str] = set()
    for f in files:
        if not f.endswith(".go"):
            continue
        d = os.path.dirname(f).replace("\\", "/") or "."
        pkgs.add("./" + d if not d.startswith(".") else d)
    return sorted(pkgs)


def evaluate_hygiene(root: Path, files: list[str]) -> HygieneResult:
    pkgs = _packages(files)
    if not pkgs:
        return HygieneResult(color="skip", reason="no Go files in scope", gofmt=[], vet="", build="")

    gofmt_bad: list[str] = []
    for f in files:
        if not f.endswith(".go"):
            continue
        path = root / f
        if not path.is_file():
            continue
        r = subprocess.run(
            ["gofmt", "-l", str(path)],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if r.stdout.strip():
            gofmt_bad.append(f)

    vet = subprocess.run(
        ["go", "vet", *pkgs],
        cwd=root,
        capture_output=True,
        text=True,
    )
    build = subprocess.run(
        ["go", "build", *pkgs],
        cwd=root,
        capture_output=True,
        text=True,
    )
    parts: list[str] = []
    if gofmt_bad:
        parts.append("gofmt: " + ", ".join(gofmt_bad))
    if vet.returncode != 0:
        parts.append("vet failed")
    if build.returncode != 0:
        parts.append("build failed")
    if parts:
        return HygieneResult(
            color="red",
            reason="; ".join(parts),
            gofmt=gofmt_bad,
            vet=(vet.stderr or vet.stdout),
            build=(build.stderr or build.stdout),
        )
    return HygieneResult(color="green", reason="gofmt/vet/build ok", gofmt=[], vet="", build="")
