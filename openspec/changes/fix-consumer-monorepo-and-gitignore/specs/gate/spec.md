## Purpose

Tightens the CQB gate so a nested Go module under git (prefix) matches catalogs and testable paths the module already uses, runs implied e2e, and produces cover itself.

## ADDED Requirements

### Requirement: Prefix-relative path matching

When `cqb.yaml` lists a prefix (or prefixes), the gate MUST match testable includes, red allowlist globs, and e2e `globs.txt` patterns against both the git-relative path and the path with the matching prefix stripped. Directory includes such as `internal/` MUST match any module-relative path under that directory (not only fnmatch of the glob string). A diff file outside every prefix MUST still skip the gate.

#### Scenario: Nested module glob

- **WHEN** prefix is `services/billing` and `globs.txt` contains `internal/application/services/*invoice*`
- **THEN** git path `services/billing/internal/application/services/invoice_total.go` implies that suite

#### Scenario: Testable include still `internal/`

- **WHEN** prefix is `services/billing` and testable include is `internal/` and the diff adds `services/billing/internal/domain/ref.go`
- **THEN** the file is testable (quick-test hunters apply)

#### Scenario: Prefix still skips others

- **WHEN** prefix is `services/billing` and the diff touches only `services/auth/foo.go`
- **THEN** the gate skips (diff outside configured prefix)

### Requirement: Catalog literals resolve under prefix

A `globs.txt` line with no wildcard MUST be considered present if the path exists at `prefix/line` or at repo-root `line`. Catalog scan MUST look for `internal/e2e/<suite>/` under the prefix when that directory exists. A glob that exists only after stripping prefix MUST NOT mark the catalog broken.

#### Scenario: Shared SQL path relative to the module

- **WHEN** `globs.txt` lists `internal/infrastructure/database/postgres/sqlc/queries/faturas_queries.sql` and the file exists at `services/billing/internal/infrastructure/.../faturas_queries.sql`
- **THEN** the catalog is not red for a missing glob path

#### Scenario: Catalog lives under prefix

- **WHEN** prefix is `services/billing` and `services/billing/internal/e2e/invoices/globs.txt` exists and the repo has no top-level `internal/e2e`
- **THEN** the gate uses the prefixed catalog directory

### Requirement: Implied e2e is executed

When at least one suite is implied and the catalog is valid, `cqb run` MUST invoke `go test -tags e2e -count=1` on that suite package. Pass MUST be green. A failing assertion MUST be red. If Docker is missing while a suite is implied, the slot MUST be `unavailable` (not green); with the opt-in hook flag the process MUST still exit 1 in that case. No implied suite remains skip. The gate MUST NOT report catalog-broken solely because execution was left to the human.

#### Scenario: Implied suite passes

- **WHEN** the diff matches `internal/e2e/invoices/globs.txt` and `go test -tags e2e` of that package exits 0
- **THEN** the e2e slot is green and lists the suite

#### Scenario: Docker missing with implication

- **WHEN** a suite is implied and `docker` is not on PATH
- **THEN** e2e is `unavailable` with reason Docker, and `CQB=1` push fails

### Requirement: Coverprofile is generated for the allowlist

When the red allowlist is non-empty and the diff includes allowlist production `.go` files, `cqb run` MUST run `go test -vet=off -coverprofile` on the packages of those files and feed the profile into the cover slot. Absence of an external `--coverprofile` flag MUST NOT by itself make cover yellow. Empty allowlist remains skip. The run MUST NOT rewrite the baseline file.

#### Scenario: Pure helper on allowlist without invocation

- **WHEN** allowlist matches `internal/application/services/*invoice*` and the diff adds a pure function with no test that calls it
- **THEN** cover is red for missing invocation (after generating a profile, or with total 0 if tests were not run because none exist)

#### Scenario: Hook does not rewrite baseline

- **WHEN** cover runs with a stale baseline
- **THEN** the baseline file on disk is unchanged

### Requirement: Hunter findings are unique and boundary is production-based

Content hunters MUST emit at most one finding per hunter, file, line, and message. `missing_boundary` MUST NOT fire only because a `Test*` name lacks Empty/Zero/Max. It MUST fire when a **new** production line compares against a numeric or `len` literal and no test in the package mentions that exact value (index, HTTP status, and time constants remain exempt as in v1 spirit).

#### Scenario: Blind assert not duplicated

- **WHEN** `t.Fatal("short")` appears once in a `_test.go` on the allowlist
- **THEN** the bundle lists one `blind_assert` finding for that line

#### Scenario: Test name without Empty is not enough

- **WHEN** a test file's only `Test*` is `TestTotal_volume` and production has no new numeric comparison
- **THEN** `missing_boundary` does not fire
