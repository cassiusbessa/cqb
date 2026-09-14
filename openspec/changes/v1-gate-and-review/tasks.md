## 1. Go module and embed layout

- [x] 1.1 Add `go.mod` for `github.com/cassiusbessa/cqb` (Go 1.22+) and `cmd/cqb/main.go` that prints help, and verify `go build ./cmd/cqb` succeeds
- [x] 1.2 Create embeddable trees `engine/` (orchestrator + Python lib) and `templates/` (review steps, bundle-reader, hook sample) with a tiny placeholder each, and verify `go:embed` compiles from `cmd/cqb`

## 2. cqb.yaml and constitution

- [x] 2.1 Define `cqb.yaml` schema (prefix, ceilings default 30/30/5, delta ceiling, empty red allowlist, testable includes, extra hunters off) and verify a fixture yaml parses
- [x] 2.2 Reject or ignore illegal keys (`yellow_blocks`, whole-module scan, always-on hook, legacy absolute complexity as red) and verify a unit test that those keys do not fail git on yellow
- [x] 2.3 Implement prefix skip: diff outside prefix writes skip bundle and exit 0, and verify with a synthetic file list

## 3. Gate engine

- [x] 3.1 Collect diff-scoped files (uncommitted / staged / file-list), exclude generated Go, and verify tests on invented `internal/billing` fixtures
- [x] 3.2 Assemble the JSON bundle (schema_version, has_red, lint/test/e2e/cover/hunters colors) and verify yellow does not set `has_red`
- [x] 3.3 Measure new-function complexity and legacy delta; over-ceiling is yellow; and verify a new func at 31/30 is yellow and a +1 delta on a legacy body is not red
- [x] 3.4 Quick-test hunter: `TestFoo` plus invocation `Foo(` on testable includes; missing outside allowlist is yellow, on allowlist is red; and verify both cases
- [x] 3.5 Content hunters (blind assert, compound, boundary, non-deterministic, order-dependent, duplicate observable) red only on allowlist otherwise yellow, and verify `t.Fatal("x")` outside allowlist is yellow
- [x] 3.6 E2E catalog: `internal/e2e/<suite>/globs.txt`; missing glob is catalog red; no match is skip; and verify with a fake suite dir
- [x] 3.7 Cover slot on allowlist (I/O patch floor 80%, pure needs invocation, ratchet, stale baseline yellow, hook does not rewrite baseline) and verify empty allowlist skips cover
- [x] 3.8 Mutation: read machine JSON; survivors yellow; missing tool `unavailable` never green; and verify a fixture JSON

## 4. CLI: init, run, upgrade, hook file

- [x] 4.1 `cqb init` writes `.cqb/`, default `cqb.yaml`, `scan.json`, hook **file** without setting `core.hooksPath`, and verify a temp Go module after init contains those files and `git config core.hooksPath` is unchanged
- [x] 4.2 `cqb init` `go install`s pinned golangci-lint and gremlins when missing, and verify the version strings in help/output match the pin (skip network if tools already present)
- [x] 4.3 `cqb run` modes (uncommitted, staged, file-list) exec the vendored engine, exit 1 only on red, and verify yellow-only fixture exits 0
- [x] 4.4 `cqb upgrade` refreshes `.cqb/` from the current binary embed and bumps the pin, and verify a dummy old file is replaced
- [x] 4.5 Opt-in hook script: no-op without the env flag; with flag calls `cqb run` in push mode, and verify both behaviors in a fake git dir

## 5. Cursor: /cqb and /cqb-setup

- [x] 5.1 Vendor `/cqb` skill+command (gather → layers → triage → present; start `cqb run` when the diff hits prefix; document-only uses editorial lenses) and verify the templates exist under `templates/` and copy into a fixture consumer `.cursor/`
- [x] 5.2 Verification-gap waits on `.quality/last.json` + running flag; skip/unavailable is not a pass; overlay consumer glob rules; and verify the step text states that
- [x] 5.3 `/cqb-setup` skill: install CLI if missing, call `cqb init`, HALT for red allowlist, suggest raising cyclo for HTTP-handler scan, do not overwrite existing skills, render bundle-reader from yaml, and verify a fixture with a pre-existing skill file is unchanged after a dry-run of the copy rules
- [x] 5.4 Bundle-reader template interpolates ceilings and allowlist from `cqb.yaml` so prose cannot drift, and verify a rendered fixture mentions 30/30/5 when those are the yaml values

## 6. Public safety and docs

- [x] 6.1 Engine tests use only invented `internal/billing` (or similar) fixtures; grep the repo for private product/service paths and credentials and verify none
- [x] 6.2 README documents `go install`, `cqb init`, `/cqb-setup`, `cqb run`, `/cqb`, constitution, and that the hook is opt-in, and verify `go build ./cmd/cqb` still succeeds
- [x] 6.3 Dogfood: `cqb init` then `cqb run` in a temp generic module with a small diff, and verify skip/yellow/red behave as spec (empty allowlist, no red from hunters)
