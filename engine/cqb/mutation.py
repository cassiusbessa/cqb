"""Mutation slot: read machine JSON. Survivors yellow. Missing tool is unavailable, never green."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MutationResult:
    color: str
    reason: str
    survivors: list[dict]


SURVIVOR_STATUSES = {"lived", "LIVED", "survived", "SURVIVED", "survivor", "SURVIVOR", "RUNNABLE"}


def evaluate_mutation(
    *,
    tool_present: bool,
    report_path: Path | None,
    report_json: str | None = None,
    should_run: bool,
) -> MutationResult:
    if not should_run:
        return MutationResult(color="skip", reason="no new tested symbol to mutate", survivors=[])
    if not tool_present:
        return MutationResult(color="unavailable", reason="gremlins not on PATH", survivors=[])
    raw: Any = None
    if report_json is not None:
        try:
            raw = json.loads(report_json)
        except json.JSONDecodeError as e:
            return MutationResult(color="yellow", reason=f"invalid mutation JSON: {e}", survivors=[])
    elif report_path and report_path.is_file():
        try:
            raw = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return MutationResult(color="yellow", reason=f"invalid mutation JSON: {e}", survivors=[])
    else:
        return MutationResult(color="unavailable", reason="no mutation report", survivors=[])

    mutants = []
    if isinstance(raw, dict):
        mutants = raw.get("mutants") or raw.get("files") or raw.get("survived") or []
        if isinstance(raw.get("survived"), list) and raw.get("mutants") is None:
            mutants = raw["survived"]
    elif isinstance(raw, list):
        mutants = raw

    survivors: list[dict] = []
    for m in mutants if isinstance(mutants, list) else []:
        if not isinstance(m, dict):
            continue
        status = str(m.get("status") or m.get("state") or m.get("result") or "")
        if status in SURVIVOR_STATUSES or m.get("survived") is True:
            survivors.append(
                {
                    "file": m.get("file") or m.get("filename") or "",
                    "line": m.get("line") or m.get("pos") or 0,
                    "kind": m.get("type") or m.get("kind") or m.get("mutator") or "",
                }
            )
    if survivors:
        return MutationResult(
            color="yellow",
            reason=f"{len(survivors)} surviving mutant(s)",
            survivors=survivors,
        )
    return MutationResult(color="green", reason="no surviving mutants", survivors=[])
