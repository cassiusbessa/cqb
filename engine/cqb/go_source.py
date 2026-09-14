"""Minimal Go source helpers: strip comments, extract functions, brace match."""

from __future__ import annotations

import re
from dataclasses import dataclass


FUNC_RE = re.compile(
    r"^func\s+(?:\([^)]+\)\s*)?(\w+)\s*(?:\[[^\]]+\])?\s*\(",
    re.MULTILINE,
)


def strip_comments_and_strings(src: str) -> str:
    """Replace comments and string contents with spaces (keep newlines)."""
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        if src[i] == "/" and i + 1 < n and src[i + 1] == "/":
            i += 2
            while i < n and src[i] not in "\n":
                out.append(" ")
                i += 1
            continue
        if src[i] == "/" and i + 1 < n and src[i + 1] == "*":
            out.append("  ")
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            if i + 1 < n:
                out.append("  ")
                i += 2
            continue
        if src[i] in ('"', "`", "'"):
            quote = src[i]
            out.append(" ")
            i += 1
            while i < n:
                if src[i] == "\\" and quote != "`":
                    out.append("  ")
                    i += 2
                    continue
                if src[i] == quote:
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            continue
        out.append(src[i])
        i += 1
    return "".join(out)


def _match_parens(src: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    while i < len(src):
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(src) - 1


def _match_braces(src: str, open_idx: int) -> int:
    depth = 0
    i = open_idx
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(src) - 1


@dataclass
class GoFunc:
    name: str
    start: int  # byte offset of 'func'
    sig_line: int  # 1-based line of signature
    body: str
    params: str
    full: str


def extract_functions(src: str) -> list[GoFunc]:
    cleaned = strip_comments_and_strings(src)
    funcs: list[GoFunc] = []
    for m in FUNC_RE.finditer(cleaned):
        name = m.group(1)
        paren = cleaned.find("(", m.end() - 1)
        if paren < 0:
            continue
        close_paren = _match_parens(cleaned, paren)
        rest = cleaned[close_paren + 1 :]
        brace_rel = rest.find("{")
        if brace_rel < 0:
            continue
        brace = close_paren + 1 + brace_rel
        end = _match_braces(cleaned, brace)
        body = cleaned[brace : end + 1]
        params = cleaned[paren : close_paren + 1]
        line = cleaned[: m.start()].count("\n") + 1
        funcs.append(
            GoFunc(
                name=name,
                start=m.start(),
                sig_line=line,
                body=body,
                params=params,
                full=cleaned[m.start() : end + 1],
            )
        )
    return funcs


def is_http_handler(fn: GoFunc) -> bool:
    p = fn.params
    return "http.ResponseWriter" in p and "Request" in p


def line_offsets(src: str) -> list[int]:
    lines = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            lines.append(i + 1)
    return lines
