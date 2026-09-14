## ADDED Requirements

### Requirement: Strict paths, not an allowlist

The consumer yaml MUST treat `strict_paths` as the list of path globs where quick-test, content-hunter, and cover findings MAY be red (process exit 1). Paths that do not match, or an empty list, MUST keep those findings yellow or otherwise non-blocking. The list MUST NOT be an ignore list and MUST NOT be inferred from test-file density. The parser MUST still read `red_allowlist` as an alias for the same list; if both keys are present, `strict_paths` MUST win. Operator-facing text in this kit MUST call the list “strict paths” (pt-BR: “lista de rigor”), not “allowlist”.

#### Scenario: Empty list cannot red cover or hunters

- **WHEN** `cqb.yaml` has `strict_paths: []` and the diff adds a pure helper with no unit test plus a `t.Fatal("short")` in a new test
- **THEN** cover and hunter slots are not red; gofmt/vet/build still apply

#### Scenario: Alias still loads

- **WHEN** `cqb.yaml` has only `red_allowlist: ["internal/billing/**"]` and no `strict_paths` key
- **THEN** the gate treats that glob as the strict-paths list

#### Scenario: Strict key wins

- **WHEN** `cqb.yaml` has `red_allowlist: ["internal/billing/**"]` and `strict_paths: []`
- **THEN** the effective list is empty

#### Scenario: On-list hunter may be red

- **WHEN** `strict_paths` includes `internal/billing/**` and a new test under that path uses `t.Fatal("short")`
- **THEN** the hunter slot is red and `cqb run` exits 1

### Requirement: Cover runs without filling strict paths

When the in-scope diff includes non-generated production `.go` files, the gate MUST run unit-test coverage for those packages even if `strict_paths` is empty. Cover MUST be `skip` only when no such production Go is in scope. A cover finding that would be red for a file matching `strict_paths` MUST be yellow when that file does not match. The run MUST NOT rewrite the baseline file.

#### Scenario: Empty list still produces cover

- **WHEN** `strict_paths` is empty and the diff adds `internal/billing/normalize.go`
- **THEN** the cover slot is not `skip` and a missing invocation is yellow, not red

#### Scenario: Matching path may red cover

- **WHEN** `strict_paths` includes `internal/billing/**` and the diff adds a pure helper there with no calling test
- **THEN** cover is red after generating a profile (or total 0 if no tests exist)

#### Scenario: Hook still does not rewrite baseline

- **WHEN** cover runs with a stale baseline
- **THEN** the baseline file on disk is unchanged

### Requirement: Unavailable e2e never fails the process by itself

When at least one e2e suite is implied and Docker (or the runner) is missing, the e2e slot MUST be `unavailable` (not green, not a pass). The process MUST exit 0 for that reason in every mode, including `push`. A failing e2e assertion or a broken `globs.txt` catalog MUST still be red and MUST exit 1.

#### Scenario: Daily run with Docker missing

- **WHEN** a suite is implied, `docker` is not on PATH, and the operator runs `cqb run`
- **THEN** e2e is `unavailable` and the process exits 0 unless some other slot is red

#### Scenario: Push mode matches daily

- **WHEN** the same implied suite and missing Docker, and the operator runs `cqb run --mode push` or the hook with `CQB=1`
- **THEN** e2e is `unavailable` and that slot does not by itself make the process exit 1

#### Scenario: Failed e2e assert still red

- **WHEN** a suite is implied, Docker is present, and `go test -tags e2e` fails an assertion
- **THEN** e2e is red and the process exits 1

### Requirement: Review mode comparison base

`cqb run --mode review` MUST compare the current branch to a resolved base ref: the upstream tracking branch if configured; otherwise `main` if that ref exists and `master` does not; otherwise `master` if that ref exists and `main` does not. The analyzed set MUST be the merge-base of that ref and `HEAD`, plus the working tree versus `HEAD` (including untracked). If both `main` and `master` exist and there is no upstream, or if no candidate ref exists, the command MUST fail with a message asking for `--base <ref>` and MUST NOT guess. Default `cqb run` (working tree versus `HEAD`, including untracked) MUST stay unchanged. `staged`, `push`, and `file-list` MUST stay unchanged.

#### Scenario: Unique main

- **WHEN** the repo has `main`, no `master`, no upstream, and the operator runs `cqb run --mode review`
- **THEN** the analyzed diff is the current branch against `main` (merge-base)

#### Scenario: Ambiguous mains

- **WHEN** the repo has both `main` and `master`, the current branch tracks neither, and the operator runs `cqb run --mode review` without `--base`
- **THEN** the process does not analyze a guessed diff and the message tells the operator to pass `--base`

#### Scenario: Explicit base

- **WHEN** the operator runs `cqb run --mode review --base origin/develop`
- **THEN** the analyzed diff uses that ref as the base

#### Scenario: Default CLI still vs HEAD

- **WHEN** the operator runs `cqb run` with uncommitted files
- **THEN** those files are in scope against `HEAD` and `--mode review` was not implied
