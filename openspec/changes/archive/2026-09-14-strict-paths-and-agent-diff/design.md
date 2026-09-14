## Context

See proposal.md (Why). The kit already ships a Go CLI, a vendored Python engine, and Cursor skills. `cqb.yaml` still names the fail-git recorte `red_allowlist`; cover is skipped when that list is empty; `--mode push` maps implied e2e `unavailable` to exit 1; `cqb init` writes `.cqb/hooks/pre-push` but never sets `core.hooksPath`; `/cqb` gather diffs working tree vs `HEAD` in the same mode as the human CLI.

Host: Go 1.22+, Python 3, git. Optional Docker when a suite is implied. Public kit: invented `internal/billing` / `services/billing` only.

## Goals / Non-Goals

**Goals:**

- One yaml name that means “here a warning may fail git”, with a deprecated alias.
- Cover visible on the production diff without filling that list; red still only on matching globs.
- Identical process exit rules for daily run, push, and hook (flag still required to *run* the hook).
- Init attaches the hook **path** locally when safe; execution stays `CQB=1`.
- Agentic review uses a branch base, or asks; human `cqb run` stays vs `HEAD`.

**Non-Goals:**

- Rewriting hunters in Go.
- Always-on hook or yellow failing git.
- Overwriting an existing `core.hooksPath`.
- Inferring strict paths from test density.
- Changing e2e `globs.txt` matching rules (prefix-relative globs stay as in the previous change).

## Decisions

### D1 — `strict_paths` in yaml, `red_allowlist` alias

Load `strict_paths` first; if absent, load `red_allowlist`. If both exist, `strict_paths` wins (including `[]`). Engine internals may keep a single list field. Bundle JSON SHOULD expose `strict_paths` (alias echoed in `ignored_keys` / deprecation note if the old key was the only one).

**Rejected:** keep “allowlist” in docs only (the word is the bug). **Rejected:** a silent rename with no alias (existing consumer yaml would empty the list).

### D2 — Cover packages of changed production `.go`, color via the list

When the scoped diff has non-generated production `.go`, generate a coverprofile for **those packages** (same mechanism as today, without requiring a non-empty list). Paint cover red only for files that match `strict_paths`; otherwise yellow. Skip only when no production Go is in scope.

**Rejected:** cover red on every changed file with an empty list (first install would fail git). **Rejected:** keep skip-until-listed (operators think they must enumerate the module to see coverage).

### D3 — Exit 1 is red only

Remove the orchestrator/CLI special case: `mode == push` and e2e `unavailable` ⇒ exit 1. `unavailable` and `skip` never set `has_red`. Hook with `CQB=1` calls `cqb run --mode push` and uses that exit code.

**Rejected:** make daily run also fail on missing Docker (would surprise `cqb run` on laptops without Docker). **Rejected:** keep the hook exception (operators read it as a constitution break).

### D4 — Local `hooksPath` if unset

`cqb init` runs `git config --local core.hooksPath .cqb/hooks` only when `--get` is empty. If set, print the two-line attach recipe. Never `git config --global`. Hook script unchanged: no-op unless `CQB=1`.

**Rejected:** leave attach fully manual (operators never enable it). **Rejected:** always overwrite (breaks husky / existing hook collections). **Rejected:** a yaml `attach_hook: true` that can fire without `CQB=1`.

### D5 — `--mode review` and `--base`

New mode, not a change to default `cqb run`. Resolution order: `--base` → upstream (`@{upstream}`) → unique `main` xor `master` → error asking for `--base`. Diff = merge-base(base, HEAD)…working tree? Spec says “committed commits on the current branch that are not on the base (merge-base)”. For review of a PR-like branch, include commits since merge-base **and** uncommitted files on top, so the agent sees what the human has locally. Record that as: tree vs merge-base(base, HEAD), including untracked under prefix.

**Rejected:** `/cqb` guessing `origin/main` when both `main` and `master` exist. **Rejected:** changing default `cqb run` to merge-base (humans want uncommitted vs HEAD).

### D6 — `/cqb` calls `--mode review` unless the operator asked otherwise

Skill gather: run `cqb run --mode review -o .quality/last.json`; on the ambiguous-base error, stop and ask in pt-BR; then `--base`. If the user asked only for the working tree, use default `cqb run`. Verification-gap still waits for JSON with `has_red`. Docs: `/cqb` **is** the review-time gate; the CLI is for the terminal and the hook.

**Rejected:** documenting “slash does not replace CLI” (reads as if the agent will not run the orchestrator).

### D7 — Docs and constitution wording

Both READMEs and `/cqb-setup` use lista de rigor / strict paths. Explain: glob on that list = “this folder may block push”; you do **not** list exclusions. `globs.txt` = “run this e2e suite if the diff matches”. `prefix` is a key **in `cqb.yaml`**. Init fills `e2e.catalog_root` only when the scan finds **exactly one** e2e tree. Constitution in `openspec/config.yaml` and engine comments: empty strict paths; hook **file** may be attached; execution still `CQB=1`; yellow never fails git.

YAML may still set: `prefix` / `prefixes`, ceilings, `strict_paths`, testable include/exclude, I/O imports, extra hunters, `e2e.catalog_root`, operator language.

YAML still cannot: whole-module scan, yellow-blocks, always-on hook, red on legacy absolute complexity, red on missing tests / cover / hunters off the list.

## Risks / Trade-offs

- [Cover on every production package in a large diff is slower] → only packages of files in the diff; skip generated `*.sql.go` / `models.go` / swagger docs.
- [Alias forever] → document `red_allowlist` as deprecated; do not generate it on new yaml.
- [Init sets hooksPath, teammates without CQB on PATH] → hook no-op without `CQB=1`; script should fail closed only when the flag is set and `cqb` is missing (keep current hook behavior).
- [Review mode misses uncommitted files if we only use merge-base of commits] → include working tree on top of merge-base (D5).
- [Two e2e trees, empty catalog_root] → engine still finds suites via prefix-relative scan from the previous change; document that the operator sets `e2e.catalog_root` or `prefixes` by hand.

## Migration Plan

1. Ship parser alias + new yaml comments; `cqb init` writes `strict_paths: []` on **new** files only.
2. Flip cover skip → yellow; remove push/unavailable exit mapping; init hooksPath; add `--mode review`.
3. Update skills and both READMEs in the same commit.
4. Consumers: no yaml edit required if they already have `red_allowlist`. `cqb upgrade` for the engine copy.
5. Rollback: revert the kit tag; alias keeps old yaml readable either way.

## Open Questions

None that block this design. Operator language for the ambiguous-base prompt stays pt-BR (existing operator default).
