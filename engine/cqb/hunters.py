"""Generic Go testing hunters. Red only on the allowlist; otherwise yellow."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .collect import matches_globs
from .go_source import extract_functions, is_http_handler, strip_comments_and_strings

CALL_RE_TMPL = r"\b{name}\s*\("
FATAL_SHORT_RE = re.compile(
    r"""\bt\.(?:Fatal|Error|Fatalf|Errorf|FailNow)\(\s*("([^"]*)"|`([^`]*)`)"""
)
TIME_NOW_RE = re.compile(r"\btime\.Now\s*\(")
RAND_RE = re.compile(r"\brand\.(?:Int|Float|Read|Intn|Perm)\s*\(")


@dataclass
class Finding:
    hunter: str
    file: str
    line: int
    message: str
    color: str  # yellow or red


def _color(rel: str, allowlist: list[str], prefixes: list[str] | None = None) -> str:
    if allowlist and matches_globs(rel, allowlist, prefixes=prefixes):
        return "red"
    return "yellow"


def _line_of(src: str, idx: int) -> int:
    return src[:idx].count("\n") + 1


def quick_test_findings(
    *,
    rel: str,
    src: str,
    test_src: str | None,
    testable_include: list[str],
    testable_exclude: list[str],
    allowlist: list[str],
    new_func_names: list[str],
    prefixes: list[str] | None = None,
) -> list[Finding]:
    if not matches_globs(rel, testable_include, prefixes=prefixes):
        return []
    if matches_globs(rel, testable_exclude, prefixes=prefixes):
        return []
    funcs = extract_functions(src)
    findings: list[Finding] = []
    tests = test_src or ""
    for fn in funcs:
        if fn.name not in new_func_names:
            continue
        if fn.name.startswith("Test") or fn.name.startswith("Benchmark"):
            continue
        if is_http_handler(fn):
            continue
        has_test_name = bool(re.search(rf"\bfunc\s+Test{re.escape(fn.name)}(?:_|\s*\()", tests))
        has_call = bool(re.search(rf"\b{re.escape(fn.name)}\s*\(", tests))
        if not (has_test_name and has_call):
            findings.append(
                Finding(
                    hunter="quick_test",
                    file=rel,
                    line=fn.sig_line,
                    message=f"new symbol {fn.name} lacks Test{fn.name} that invokes {fn.name}(",
                    color=_color(rel, allowlist, prefixes),
                )
            )
    return findings


def content_findings(
    *,
    rel: str,
    test_src: str,
    allowlist: list[str],
    prefixes: list[str] | None = None,
) -> list[Finding]:
    if not rel.endswith("_test.go"):
        return []
    cleaned = strip_comments_and_strings(test_src)
    findings: list[Finding] = []
    color = _color(rel, allowlist, prefixes)

    for m in FATAL_SHORT_RE.finditer(test_src):
        lit = m.group(2) if m.group(2) is not None else (m.group(3) or "")
        if "%" in lit:
            continue
        findings.append(
            Finding(
                hunter="blind_assert",
                file=rel,
                line=_line_of(test_src, m.start()),
                message=f"short t.Fatal/Error literal {lit!r} without comparison",
                color=color,
            )
        )

    # Compound: two or more assert-like calls on one line, or && inside assert.
    for i, line in enumerate(test_src.splitlines(), 1):
        calls = len(re.findall(r"\bt\.(?:Fatal|Error|Fatalf|Errorf|Helper)\s*\(", line))
        if calls >= 2 or ("&&" in line and re.search(r"\bt\.(?:Fatal|Error)", line)):
            findings.append(
                Finding(
                    hunter="compound_assert",
                    file=rel,
                    line=i,
                    message="compound assertion on one line",
                    color=color,
                )
            )

    for m in TIME_NOW_RE.finditer(cleaned):
        findings.append(
            Finding(
                hunter="non_deterministic",
                file=rel,
                line=_line_of(cleaned, m.start()),
                message="time.Now in a test",
                color=color,
            )
        )
    for m in RAND_RE.finditer(cleaned):
        findings.append(
            Finding(
                hunter="non_deterministic",
                file=rel,
                line=_line_of(cleaned, m.start()),
                message="math/rand in a test",
                color=color,
            )
        )

    # Order-dependent: package-level var mutated in Test* without t.Cleanup / mutex.
    if re.search(r"^var\s+\w+", cleaned, re.MULTILINE) and re.search(
        r"^\w+\s*=", cleaned, re.MULTILINE
    ):
        if "t.Parallel" not in test_src and "t.Cleanup" not in test_src:
            # only flag if tests assign to package identifiers
            findings.append(
                Finding(
                    hunter="order_dependent",
                    file=rel,
                    line=1,
                    message="package-level state mutated without cleanup",
                    color=color,
                )
            )

    # Duplicate observable literals across t.Fatal/Error
    lits: dict[str, list[int]] = {}
    for m in FATAL_SHORT_RE.finditer(test_src):
        lit = m.group(2) if m.group(2) is not None else (m.group(3) or "")
        if len(lit) < 2:
            continue
        lits.setdefault(lit, []).append(_line_of(test_src, m.start()))
    for lit, lines in lits.items():
        if len(lines) >= 2:
            findings.append(
                Finding(
                    hunter="duplicate_observable",
                    file=rel,
                    line=lines[0],
                    message=f"duplicate observable literal {lit!r} on lines {lines}",
                    color=color,
                )
            )

    return findings


HTTP_STATUS_HINT = re.compile(r"\b(?:http\.Status|StatusCode|WriteHeader|status)\b", re.IGNORECASE)
TIME_HINT = re.compile(
    r"\btime\.(?:Duration|Second|Minute|Hour|Millisecond|Microsecond|Nanosecond)\b"
)
INDEX_LIT_RE = re.compile(r"\[[0-9]+\]")
NUM_LIT_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
CMP_RE = re.compile(r"(==|!=|<=|>=|<|>)")
LEN_RE = re.compile(r"\blen\s*\(")
HTTP_STATUS_NUMS = {
    "100",
    "101",
    "200",
    "201",
    "202",
    "204",
    "301",
    "302",
    "304",
    "307",
    "308",
    "400",
    "401",
    "403",
    "404",
    "405",
    "409",
    "410",
    "412",
    "415",
    "422",
    "429",
    "500",
    "502",
    "503",
    "504",
}


def _numbers_on_line(line: str) -> list[str]:
    """Numeric literals that are not slice/array indexes."""
    masked = INDEX_LIT_RE.sub("[]", line)
    return NUM_LIT_RE.findall(masked)


def _exempt_boundary_line(line: str) -> bool:
    if TIME_HINT.search(line):
        return True
    if HTTP_STATUS_HINT.search(line):
        nums = _numbers_on_line(line)
        if not nums or all(n.split(".")[0] in HTTP_STATUS_NUMS or n in HTTP_STATUS_NUMS for n in nums):
            return True
    return False


def boundary_findings(
    *,
    rel: str,
    src: str,
    test_src: str | None,
    added_lines: set[int],
    allowlist: list[str],
    prefixes: list[str] | None = None,
) -> list[Finding]:
    """New production comparisons to numeric/len literals must appear in package tests."""
    if rel.endswith("_test.go"):
        return []
    if not added_lines:
        return []
    tests = test_src or ""
    findings: list[Finding] = []
    color = _color(rel, allowlist, prefixes)
    for i, line in enumerate(src.splitlines(), 1):
        if i not in added_lines:
            continue
        stripped = line.strip()
        if stripped.startswith("//") or not stripped:
            continue
        if _exempt_boundary_line(line):
            continue
        if not CMP_RE.search(line) and not LEN_RE.search(line):
            continue
        nums = _numbers_on_line(line)
        if not nums and not LEN_RE.search(line):
            continue
        missing: list[str] = []
        for n in nums:
            if n in HTTP_STATUS_NUMS and HTTP_STATUS_HINT.search(line):
                continue
            if n not in tests:
                missing.append(n)
        if LEN_RE.search(line) and nums:
            # len(...) compared to a literal already in nums
            pass
        elif LEN_RE.search(line) and not nums:
            # len without a numeric literal (len(x) == n) — not a flag
            continue
        if not missing:
            continue
        findings.append(
            Finding(
                hunter="missing_boundary",
                file=rel,
                line=i,
                message=f"new comparison to {', '.join(missing)} has no matching literal in package tests",
                color=color,
            )
        )
    return findings


def unique_findings(hits: list[Finding]) -> list[Finding]:
    seen: set[tuple[str, str, int, str]] = set()
    out: list[Finding] = []
    for h in hits:
        key = (h.hunter, h.file, h.line, h.message)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def placebo_findings(
    *,
    rel: str,
    test_src: str,
    allowlist: list[str],
    enabled: bool,
    prefixes: list[str] | None = None,
) -> list[Finding]:
    if not enabled or not rel.endswith("_test.go"):
        return []
    findings: list[Finding] = []
    if re.search(r"\.Struct\s*\(", test_src) and not re.search(
        r"(Error|Fatal).*\.Struct|\.Struct[\s\S]{0,80}(Error|Fatal|require|assert)",
        test_src,
    ):
        findings.append(
            Finding(
                hunter="placebo_validator",
                file=rel,
                line=1,
                message="validator.Struct called without asserting the error",
                color=_color(rel, allowlist, prefixes),
            )
        )
    return findings
