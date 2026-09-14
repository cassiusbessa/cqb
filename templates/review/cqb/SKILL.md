---
name: cqb
description: >-
  Code review ritual (gather → parallel layers → triage → present) plus the
  local CQB quality gate. Use when the user says /cqb, asks for a code review,
  or wants the quality bundle interpreted. Document-only targets use editorial
  lenses in this same slash.
---

# /cqb — review ritual

Operator-facing language: **pt-BR**. Hunter prompts MAY stay in English.
Never paste the raw JSON bundle into the chat.

`/cqb` **runs** `cqb run` and then interprets `.quality/last.json`. The
operator does not need to type `cqb run` first. The CLI remains for the
terminal and the hook.

## Gather

1. Read `cqb.yaml`. If the diff does **not** touch any configured `prefix`,
   do not start `cqb run`. `{quality_bundle}` stays empty. Verification-gap
   MUST NOT wait.
2. Unless the operator asked for `uncommitted`, `staged`, `push`, or a file
   list, start `cqb run --mode review --output .quality/last.json` in the
   background. Set a running flag (for example `.quality/running`) and clear
   it when the process exits.
3. If that command fails because the review base is **ambiguous** (it asks
   for `--base`), **STOP and ask** which git ref to compare. Then re-run
   `cqb run --mode review --base <ref> --output .quality/last.json`.
   MUST NOT silently diff the working tree against `HEAD`.
4. If the operator asked only for uncommitted / working-tree files, use
   default `cqb run` (working tree versus `HEAD`) instead of `--mode review`.
5. Classify the target: Go/code diff → code layers. Spec/proposal markdown
   with no code → editorial lenses only. Do not invent code triage on prose.
   Do not install BMAD sprint/story modules.

## Layers (code diff, in parallel)

Launch independent layers. Blind and edge MAY start without waiting for the bundle.

- Blind: unused branches, ignored errors, silent catch.
- Edge: empty inputs, timeouts, missing config.
- Verification-gap: wait until `.quality/last.json` is valid JSON **with `has_red`** and the running flag is gone. `skip` and `unavailable` are **not** a pass. Docker missing → `e2e: unavailable`, review continues, e2e was not executed.
- Overlay: path-scoped rules and skills already in this repo take precedence over kit examples on matching paths. Do not overwrite those files. Bundle **colors** are not overridable by a skill (a rule MUST NOT turn a red slot green).

## Layers (document-only)

Structure and prose lenses only. No code hunters, no fake patch list for markdown.

## Triage

Classify each finding: `patch` / `defer` / `decision_needed` / `rejected`.

- Defer findings whose fix is to edit agent-context (AGENTS.md, rules, other specs).
- Defer issues the loaded OpenSpec pack already accepted (non-goal or explicit risk) unless this change enlarged the hole.
- A missing `Test<Symbol>` that **invokes** a **new** symbol on a testable path MUST NOT be `defer` only because the repo "has almost no suite". Off the strict-paths list that signal is yellow; on the list it is red. Legacy missing tests remain eligible for `defer`.
- Consumer glob rule wins on style (for example sequential `if err != nil` in HTTP handlers) when it matches the path.

## Present (always in this order)

1. Prose summary of the bundle: colors and **why** each flagged function is yellow/red. `skip`/`unavailable` called out as not executed, not as passed.
2. Then the unified review: patch / defer / decision_needed / rejected.

Do not dump `.quality/last.json`.
