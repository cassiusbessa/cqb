## Why

A nested Go module (`services/billing` under a git root) makes CQB v1 miss testable paths, treat a valid e2e `globs.txt` as a broken catalog, skip cover, and leave `.cqb/` / `.quality/` untracked. The kit must match globs the way the module writes them, actually run implied e2e, generate a coverprofile, and keep git clean after `cqb init`.

## What Changes

- **Prefix-relative matching:** git paths are compared to `cqb.yaml` `prefix` / `prefixes`; globs, testable includes, and catalog literals also match the path with that prefix stripped (so `internal/application/**` works when git shows `services/billing/internal/application/...`).
- **E2E catalog:** literal glob lines resolve under the prefix first, then the repo root. A missing catalog dir is skip, not a silent pass. **BREAKING vs v1:** an implied suite is **executed** (`go test -tags e2e`); pass is green, assert fail is red, Docker missing is `unavailable` (flagged push still treats implied+no-Docker as red, same hygiene as vet).
- **Cover:** when the red allowlist has production files in the diff, `cqb run` generates a coverprofile for those packages; missing profile is no longer a yellow cop-out. Hook still MUST NOT rewrite the baseline.
- **Hunters:** one finding per `(hunter, file, line, message)`; `missing_boundary` flags a numeric/`len` comparison in **new production lines** without a test at that value — not “Test name lacks Empty/Zero”.
- **`cqb init` upserts `.gitignore`** with a managed block: `.quality/`, `.cqb/scan.json`, `.cqb/work/`, `*.coverprofile`, `__pycache__` under `.cqb/`. It does **not** ignore vendored `.cqb/engine` or `cqb.yaml`.

## Non-goals

- Changing constitution (diff-only, yellow never fails git, empty allowlist, opt-in hook).
- Generating domain skills or overwriting consumer rules.
- GitHub Actions as the gate.
- Rewriting hunters in Go.
- Auto-setting `core.hooksPath`.
- Inferring a red allowlist without `/cqb-setup` HALT.

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `gate`: prefix-relative matching, e2e execution, coverprofile generation, hunter uniqueness and boundary semantics.
- `bootstrap`: `.gitignore` upsert on init; scan/defaults locate `internal/e2e` under prefix when present.

## Impact

- Engine (`engine/cqb/*.py`, orchestrator), CLI `cqb init` / `cqb run`, default `cqb.yaml` comments, Python fixtures under invented `services/billing/`.
- Consumers with a nested module keep the same `globs.txt` they already write relative to the module.
- Init is a bit more opinionated about gitignore; existing ignore lines are left intact (block is appended or refreshed in place).
