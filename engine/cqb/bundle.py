"""JSON bundle assembly. Yellow never sets has_red."""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1
COLORS = ("red", "yellow", "skip", "unavailable", "green")


def slot(color: str, **extra: Any) -> dict[str, Any]:
    if color not in COLORS:
        raise ValueError(f"invalid color {color!r}")
    out = {"color": color}
    out.update(extra)
    return out


def assemble(
    *,
    mode: str,
    skipped: bool = False,
    skip_reason: str = "",
    ignored_keys: list[str] | None = None,
    slots: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    slots = slots or {}
    has_red = any(s.get("color") == "red" for s in slots.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "has_red": has_red,
        "mode": mode,
        "skipped": skipped,
        "skip_reason": skip_reason,
        "ignored_keys": list(ignored_keys or []),
        "slots": slots,
    }


def empty_skip(mode: str, reason: str, ignored_keys: list[str] | None = None) -> dict[str, Any]:
    return assemble(
        mode=mode,
        skipped=True,
        skip_reason=reason,
        ignored_keys=ignored_keys,
        slots={
            "lint": slot("skip", reason=reason),
            "test": slot("skip", reason=reason),
            "e2e": slot("skip", reason=reason),
            "cover": slot("skip", reason=reason),
            "hunters": slot("skip", reason=reason),
            "mutation": slot("skip", reason=reason),
            "complexity": slot("skip", reason=reason),
        },
    )
