"""Load cqb.yaml. Constitution keys are ignored so they cannot invert the gate."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # stdlib-only fallback: tiny subset used in tests
    yaml = None


ILLEGAL_KEYS = frozenset(
    {
        "yellow_blocks",
        "yellow_blocks_git",
        "whole_module",
        "scan_whole_module",
        "always_on_hook",
        "legacy_absolute_red",
        "red_on_legacy_complexity",
    }
)

DEFAULT_CEILINGS = {"cognitive": 30, "cyclomatic": 30, "nested_if": 5, "delta": 5}


def _walk_illegal(obj: Any, found: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ILLEGAL_KEYS and k not in found:
                found.append(k)
            _walk_illegal(v, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk_illegal(item, found)


def _parse_yaml(text: str) -> dict[str, Any]:
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("cqb.yaml root must be a mapping")
        return data
    return _minimal_yaml(text)


def _minimal_yaml(text: str) -> dict[str, Any]:
    """Tiny indent-aware parser for the kit's own schema (no PyYAML required)."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    pending_key: str | None = None
    pending_indent = 0

    def current(indent: int) -> Any:
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        return stack[-1][1]

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        container = current(indent)
        if line.startswith("- "):
            item = _scalar(line[2:].strip())
            if pending_key is not None:
                lst: list[Any] = []
                parent = current(pending_indent)
                if isinstance(parent, dict):
                    parent[pending_key] = lst
                    stack.append((indent, lst))
                pending_key = None
                container = stack[-1][1]
            if isinstance(container, list):
                container.append(item)
            continue
        if ":" in line:
            key, _, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()
            if not isinstance(container, dict):
                continue
            if rest == "" or rest == "|" or rest == ">":
                pending_key = key
                pending_indent = indent
                container[key] = {}
                stack.append((indent, container[key]))
            else:
                pending_key = None
                container[key] = _scalar(rest)
    return root


def _scalar(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p.strip()) for p in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "none", "~"):
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


@dataclass
class Complexity:
    cognitive: int = 30
    cyclomatic: int = 30
    nested_if: int = 5
    delta: int = 5


@dataclass
class Testable:
    include: list[str] = field(default_factory=lambda: ["internal/"])
    exclude: list[str] = field(default_factory=lambda: ["internal/interface/"])


@dataclass
class E2E:
    catalog_root: str = "internal/e2e"


@dataclass
class Cover:
    io_floor: int = 80
    baseline_path: str = ".cqb/cover-baseline.json"


@dataclass
class Config:
    kit_version: str = "0.1.0"
    prefix: str = ""
    prefixes: list[str] = field(default_factory=list)
    operator_language: str = "pt-BR"
    complexity: Complexity = field(default_factory=Complexity)
    red_allowlist: list[str] = field(default_factory=list)
    testable: Testable = field(default_factory=Testable)
    io_imports: list[str] = field(
        default_factory=lambda: ["database/sql", "net/http", "os"]
    )
    extra_hunters: list[str] = field(default_factory=list)
    e2e: E2E = field(default_factory=E2E)
    cover: Cover = field(default_factory=Cover)
    ignored_keys: list[str] = field(default_factory=list)

    def prefix_list(self) -> list[str]:
        out: list[str] = []
        if self.prefix:
            out.append(self.prefix)
        out.extend(p for p in self.prefixes if p)
        return out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: Path) -> Config:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return parse_config(text)


def parse_config(text: str) -> Config:
    raw = _parse_yaml(text) if text.strip() else {}
    ignored: list[str] = []
    _walk_illegal(raw, ignored)
    cfg = Config(ignored_keys=ignored)
    if not isinstance(raw, dict):
        return cfg
    cfg.kit_version = str(raw.get("kit_version") or cfg.kit_version)
    prefix = raw.get("prefix")
    if isinstance(prefix, list):
        cfg.prefixes = [str(p) for p in prefix]
    elif prefix is not None:
        cfg.prefix = str(prefix)
    extra_prefixes = raw.get("prefixes")
    if isinstance(extra_prefixes, list):
        cfg.prefixes.extend(str(p) for p in extra_prefixes)
    if raw.get("operator_language"):
        cfg.operator_language = str(raw["operator_language"])
    cx = raw.get("complexity") or {}
    if isinstance(cx, dict):
        cfg.complexity = Complexity(
            cognitive=int(cx.get("cognitive", DEFAULT_CEILINGS["cognitive"])),
            cyclomatic=int(cx.get("cyclomatic", DEFAULT_CEILINGS["cyclomatic"])),
            nested_if=int(cx.get("nested_if", DEFAULT_CEILINGS["nested_if"])),
            delta=int(cx.get("delta", DEFAULT_CEILINGS["delta"])),
        )
    allow = raw.get("red_allowlist") or []
    if isinstance(allow, list):
        cfg.red_allowlist = [str(x) for x in allow]
    tes = raw.get("testable") or {}
    if isinstance(tes, dict):
        inc = tes.get("include")
        exc = tes.get("exclude")
        cfg.testable = Testable(
            include=[str(x) for x in inc] if isinstance(inc, list) else cfg.testable.include,
            exclude=[str(x) for x in exc] if isinstance(exc, list) else cfg.testable.exclude,
        )
    io_imp = raw.get("io_imports")
    if isinstance(io_imp, list):
        cfg.io_imports = [str(x) for x in io_imp]
    extra = raw.get("extra_hunters")
    if isinstance(extra, list):
        cfg.extra_hunters = [str(x) for x in extra]
    e2e = raw.get("e2e") or {}
    if isinstance(e2e, dict) and e2e.get("catalog_root"):
        cfg.e2e = E2E(catalog_root=str(e2e["catalog_root"]))
    cov = raw.get("cover") or {}
    if isinstance(cov, dict):
        cfg.cover = Cover(
            io_floor=int(cov.get("io_floor", 80)),
            baseline_path=str(cov.get("baseline_path", cfg.cover.baseline_path)),
        )
    return cfg
