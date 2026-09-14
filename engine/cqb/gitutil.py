"""Git helpers for HEAD blobs and added line numbers (1-based, new file)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_show(root: Path, spec: str) -> str | None:
    r = subprocess.run(
        ["git", "show", spec],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    return r.stdout


def added_lines_for_file(root: Path, rel: str, mode: str) -> set[int]:
    """Line numbers in the *new* file that the diff added."""
    args = ["git", "diff", "-U0"]
    if mode == "staged":
        args += ["--cached", "--", rel]
    elif mode == "push":
        args += ["@{u}...HEAD", "--", rel]
    else:
        args += ["HEAD", "--", rel]
    r = subprocess.run(args, cwd=root, capture_output=True, text=True)
    text = r.stdout
    added: set[int] = set()
    new_line = 0
    for line in text.splitlines():
        if line.startswith("@@"):
            # @@ -a,b +c,d @@
            plus = line.split("+", 1)[1].split(" ", 1)[0]
            start_s, _, count_s = plus.partition(",")
            try:
                new_line = int(start_s)
            except ValueError:
                new_line = 0
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            new_line += 1
    return added
