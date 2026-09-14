---
name: cqb
description: Run the CQB code-review ritual (/cqb).
---

Run the skill `cqb` (gather → layers → triage → present). `/cqb` runs `cqb run --mode review` (or default `cqb run` if the operator asked only for the working tree), waits for `.quality/last.json`, and interprets the colors. If review mode asks for `--base`, stop and ask which ref — do not guess `HEAD`.
