## Why

Operators cannot tell what CQB will do from the current words and defaults. “Allowlist” sounds like permission, but putting a path there makes the gate *stricter*. Coverage does not even run until that list is filled, so people think they must enumerate the whole module. Daily `cqb run` and `CQB=1 git push` disagree when Docker is missing. `/cqb` is written as if it were not the gate, and in agentic review it compares against `HEAD` instead of the branch the review is about.

## What Changes

- **Rename the list (BREAKING for docs; yaml is aliased).** The user-facing name is **strict paths** (pt-BR: **lista de rigor**). The yaml key is `strict_paths`. `red_allowlist` remains a read-only alias for one minor line so existing files keep working. Docs MUST NOT call it an allowlist. It is still **not** an ignore list: paths *on* it may turn hunter / quick-test / cover findings **red** (exit 1); paths *off* it stay yellow or non-blocking.
- **Coverage without filling the list.** Cover MUST run when the diff includes production `.go` under the configured prefix. An empty `strict_paths` MUST NOT skip cover. Cover / hunters / quick-test MAY be **red** only when the file matches `strict_paths`. Empty list still cannot fail git for those slots (hygiene and failed e2e asserts still can).
- **Same colors in every mode.** Implied e2e with Docker missing stays `unavailable` (not green, not a pass). **`cqb run` MUST NOT exit 1 solely because that slot is `unavailable`**, including `--mode push` and `CQB=1`. Failed e2e asserts and a broken `globs.txt` catalog stay red. This **removes** the v1/fix special case that made the hook stricter than a normal run.
- **Init attaches the hook file, still flag-gated.** `cqb init` MUST set **local** `core.hooksPath` to `.cqb/hooks` when that config is unset. If `core.hooksPath` is already set to something else, init MUST NOT overwrite it and MUST print how to attach. The hook remains a no-op unless `CQB=1`. Yaml still cannot turn the hook always-on. Do not export `CQB=1` in bashrc.
- **`/cqb` is the agentic gate.** On a code diff that touches a prefix, `/cqb` MUST run `cqb run` (or the same orchestrator) and then interpret `.quality/last.json`. It replaces the need for the operator to type `cqb run` during review. The CLI remains for humans and for the hook.
- **Agentic comparison base.** When `/cqb` (or `cqb run --mode review`) builds the diff, it MUST compare the current branch to a resolved base (tracking upstream, else a unique `main`/`master`), not silently “working tree vs `HEAD`”. If the base is ambiguous, it MUST stop and ask — it MUST NOT guess. Human CLI defaults (`cqb run` / `staged` / `push` / `file-list`) stay as they are, including uncommitted files vs `HEAD` for the default run.
- **Docs.** Both READMEs (and setup/review skills) follow reading order: what it is, quick start, files on disk, colors, checks, **lista de rigor**, run modes, Cursor, then yaml knobs. Explain *when* init fills `e2e.catalog_root` (exactly one journey-test directory), that `prefix` is edited **in `cqb.yaml`**, that `globs.txt` is “run this suite if the diff matches” (you list what you *want* implied, not what to exclude), and what constitution means in plain language.

## Non-goals

- Making yellow fail git, scanning the whole module, or inferring `strict_paths` from “this package has tests”.
- Always-on hook (`CQB=1` still required per push). Overwriting an existing `core.hooksPath`.
- GitHub Actions / CI as the gate.
- Changing hunter *rules* (blind assert, boundary, etc.) except how colors map to `strict_paths`.
- Rewriting the engine in Go.
- A cutover of any private consumer service.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `gate`: `strict_paths` (alias `red_allowlist`); cover runs with an empty list but cannot be red off-list; `unavailable` e2e never exits 1 by itself; `--mode review` comparison base.
- `bootstrap`: init sets local `core.hooksPath` when unset; scan/`e2e.catalog_root` wording; setup interview uses strict paths, not allowlist.
- `review`: `/cqb` always runs the gate then interprets; disambiguates the compare base; does not tell operators that the slash “does not replace” `cqb run`.

## Impact

- Engine (`engine/cqb/*.py`, orchestrator exit mapping), CLI (`cqb init`, `cqb run` modes), default `cqb.yaml` comments, Python/Go tests, Cursor skills (`/cqb`, `/cqb-setup`), both READMEs, `readme_test.go`.
- Existing `cqb.yaml` with `red_allowlist` keeps the same list under the alias.
- Hook: new clones get local `hooksPath` after init; `git push` without `CQB=1` is still a no-op. Teams that already set `hooksPath` are left alone.
- Constitution wording: empty **strict paths** (not “empty allowlist”); hook **file** may be attached, execution still opt-in via `CQB=1`.
