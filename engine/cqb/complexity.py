"""Complexity on new functions (absolute) and legacy body edits (delta). Over-ceiling is yellow, never red."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .go_source import GoFunc, extract_functions

DECISION_RE = re.compile(r"\b(if|for|switch|select|case)\b")
BOOL_RE = re.compile(r"&&|\|\|")


def cyclomatic(body: str) -> int:
    return 1 + len(DECISION_RE.findall(body)) + len(BOOL_RE.findall(body))


def nested_if(body: str) -> int:
    max_depth = 0
    depth = 0
    i = 0
    tokens = re.finditer(r"\b(if|else)\b|[{}]", body)
    # Walk braces; increment on 'if' that is not else-if handled via brace depth of if-blocks.
    depth = 0
    max_depth = 0
    if_stack: list[int] = []
    last_was_else = False
    idx = 0
    while idx < len(body):
        if body.startswith("else", idx) and (idx == 0 or not body[idx - 1].isalnum()):
            last_was_else = True
            idx += 4
            continue
        if body.startswith("if", idx) and (idx == 0 or not body[idx - 1].isalnum()) and (
            idx + 2 >= len(body) or not body[idx + 2].isalnum()
        ):
            if not last_was_else:
                depth += 1
                if_stack.append(depth)
                max_depth = max(max_depth, depth)
            last_was_else = False
            idx += 2
            continue
        ch = body[idx]
        if ch == "{":
            last_was_else = False
        elif ch == "}":
            last_was_else = False
            if if_stack and depth == if_stack[-1]:
                if_stack.pop()
                depth = max(0, depth - 1)
        else:
            if not ch.isspace():
                last_was_else = False
        idx += 1
    return max_depth


def cognitive(body: str) -> int:
    """Sonar-like approximation: + (nesting+1) for if/for/switch/select; +1 for else/&&/||/case."""
    score = 0
    nesting = 0
    i = 0
    n = len(body)
    last_else = False

    def ident_at(pos: int, word: str) -> bool:
        if not body.startswith(word, pos):
            return False
        before = body[pos - 1] if pos else " "
        after = body[pos + len(word)] if pos + len(word) < n else " "
        return not before.isalnum() and not after.isalnum() and before != "_" and after != "_"

    while i < n:
        if ident_at(i, "else"):
            last_else = True
            score += 1
            i += 4
            continue
        if ident_at(i, "if"):
            inc = 1 if last_else else nesting + 1
            score += inc
            last_else = False
            i += 2
            continue
        if ident_at(i, "for") or ident_at(i, "switch") or ident_at(i, "select"):
            score += nesting + 1
            last_else = False
            i += 3 if body.startswith("for", i) else (6 if body.startswith("switch", i) else 6)
            continue
        if ident_at(i, "case"):
            score += 1
            last_else = False
            i += 4
            continue
        if body.startswith("&&", i) or body.startswith("||", i):
            score += 1
            last_else = False
            i += 2
            continue
        if body[i] == "{":
            nesting += 1
            last_else = False
        elif body[i] == "}":
            nesting = max(0, nesting - 1)
            last_else = False
        elif not body[i].isspace():
            last_else = False
        i += 1
    return score


@dataclass
class FuncComplexity:
    name: str
    file: str
    line: int
    kind: str  # "new" | "delta"
    cognitive: int
    cyclomatic: int
    nested_if: int
    delta_cognitive: int = 0
    yellow: bool = False
    reasons: list[str] | None = None


def _inner_body(body: str) -> str:
    body = body.strip()
    if body.startswith("{") and body.endswith("}"):
        return body[1:-1]
    return body


def measure_func(fn: GoFunc) -> tuple[int, int, int]:
    body = _inner_body(fn.body)
    return cognitive(body), cyclomatic(body), nested_if(body)


def classify(
    *,
    file: str,
    current_src: str,
    head_src: str | None,
    added_lines: set[int],
    ceilings: dict[str, int],
) -> list[FuncComplexity]:
    current = extract_functions(current_src)
    head_funcs = {f.name: f for f in extract_functions(head_src)} if head_src else {}
    out: list[FuncComplexity] = []
    for fn in current:
        is_new = fn.name not in head_funcs or fn.sig_line in added_lines
        # Signature added in this diff → new. Body-only → legacy if name existed.
        if fn.name in head_funcs and fn.sig_line not in added_lines:
            is_new = False
        cog, cyc, nest = measure_func(fn)
        if is_new:
            yellow = (
                cog > ceilings.get("cognitive", 30)
                or cyc > ceilings.get("cyclomatic", 30)
                or nest > ceilings.get("nested_if", 5)
            )
            reasons = []
            if cog > ceilings.get("cognitive", 30):
                reasons.append(f"cognitive {cog} > {ceilings.get('cognitive', 30)}")
            if cyc > ceilings.get("cyclomatic", 30):
                reasons.append(f"cyclomatic {cyc} > {ceilings.get('cyclomatic', 30)}")
            if nest > ceilings.get("nested_if", 5):
                reasons.append(f"nested-if {nest} > {ceilings.get('nested_if', 5)}")
            out.append(
                FuncComplexity(
                    name=fn.name,
                    file=file,
                    line=fn.sig_line,
                    kind="new",
                    cognitive=cog,
                    cyclomatic=cyc,
                    nested_if=nest,
                    yellow=yellow,
                    reasons=reasons,
                )
            )
        else:
            old = head_funcs[fn.name]
            old_cog, _, _ = measure_func(old)
            delta = max(0, cog - old_cog)
            yellow = delta > ceilings.get("delta", 5)
            reasons = [f"delta cognitive +{delta}"] if yellow else []
            out.append(
                FuncComplexity(
                    name=fn.name,
                    file=file,
                    line=fn.sig_line,
                    kind="delta",
                    cognitive=cog,
                    cyclomatic=cyc,
                    nested_if=nest,
                    delta_cognitive=delta,
                    yellow=yellow,
                    reasons=reasons,
                )
            )
    return out
