## Context

See proposal.md (Why). Consumer dogfood against a nested module showed v1 matching git paths only, resolving `globs.txt` literals at the repo root, skipping e2e execution, and yellowing cover when no profile was passed. `cqb init` did not touch `.gitignore`. Constitution is unchanged. Fixtures stay invented (`services/billing`).

## Goals / Non-Goals

**Goals:**

- One `rel_for_match(git_path)` used by testable, allowlist, e2e globs, and cover.
- Literal catalog paths exist if `root/prefix/line` or `root/line` exists.
- Implied e2e runs; coverprofile is produced by the orchestrator.
- Init gitignore block is idempotent and does not hide the vendored engine.

**Non-Goals:**

- Auto red allowlist.
- Changing yellow-never-fails-git.
- Parsing every `go.work` module as a separate CQB config in v1 of this fix (one prefix, or a list, remains the yaml).

## Decisions

### D1 — Strip prefix for matching, keep git paths in the bundle

Bundle `file` fields stay git-relative (`services/billing/...`) so humans and diffs agree. Matching uses `git_rel` **or** `module_rel`. Testable `internal/` means `module_rel == "internal" or module_rel.startswith("internal/")`.

**Rejected:** rewriting all globs at init (would fork the consumer's `globs.txt`). **Rejected:** requiring operators to duplicate `services/billing/` in every glob.

### D2 — Catalog root discovery

Engine: if `catalog_root` as written is missing, try `{prefix}/` + catalog_root and `{prefix}/internal/e2e`. Init: on **new** yaml only, set `e2e.catalog_root` when `{prefix}/internal/e2e` exists.

**Rejected:** always overwriting yaml on init (destroys operator edits).

### D3 — Execute e2e like hygiene, not “left to consumer”

Orchestrator runs `go test -tags e2e -count=1 -timeout 8m ./<package>` from the repo root, package path derived from the suite directory. Docker missing + implied → `unavailable`; `CQB=1` maps that to exit 1 (already the hook story for red/unavailable-with-implication).

**Rejected:** keeping yellow “execution left to the consumer” (that failed dogfood: false skip or false catalog red, never a real suite).

### D4 — Coverprofile from `go test -vet=off`

Packages = unique dirs of allowlist production files in the diff. `go test -vet=off -coverprofile <work> <pkgs>`. Work file under `.cqb/work/` (gitignored). Parse as today. No baseline rewrite.

**Rejected:** requiring the caller to pass `--coverprofile` (v1 yellow trap).

### D5 — Gitignore upsert, not a full-file rewrite

Markers `# cqb begin` / `# cqb end`. Replace inner lines on each init. Never ignore `.cqb/engine`, hooks, templates, `cqb.yaml`.

### D6 — Boundary hunter rewrite

Walk **new** production lines for comparisons to int/float/`len(` literals; skip status codes and duration constants; require the literal to appear in package `*_test.go`. Drop the Test-name Empty/Zero heuristic (it false-positived on `TestFoo_volume`).

## Risks / Trade-offs

- [E2e duration on every lote-like diff] → same as any real gate; still skip when no glob matches. Timeout 8m.
- [go test cover on a package with no tests fails] → treat as profile empty / 0% and apply pure-invocation red on allowlist (same outcome as “no call”).
- [Multiple prefixes] → strip the first matching prefix; document that overlapping prefixes should be listed most-specific first.
- [gitignore markers edited by a human] → next init restores the managed block only.

## Migration Plan

1. Engine + tests with `services/billing/...` fixtures (including a literal SQL path under the prefix).
2. CLI gitignore helper + init test (twice, no duplicate).
3. Consumers: `cqb upgrade` then `cqb init` to refresh ignore block; yaml catalog_root optional.
4. Rollback: revert this kit version; constitution unchanged.

## Open Questions

None. Operator language stays pt-BR default. Extra hunters still opt-in.
