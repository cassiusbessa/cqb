## Purpose

Defines the local CQB quality gate: diff-scoped analysis, a color bundle, constitution that YAML cannot disable, and optional red allowlist for cover and content hunters.

## ADDED Requirements

### Requirement: Diff scope only

The gate MUST analyze only files and functions in the git diff for the requested mode (`uncommitted`, `staged`, `push` with SHAs, or a file list). It MUST NOT walk the whole module. Generated Go (`*.sql.go`, `models.go`, swagger `docs/`) MUST be excluded from metrics, quick tests, and mutation. A configured path prefix MUST bound the run; a diff that does not touch that prefix MUST skip the gate (even if a hook flag is set).

#### Scenario: Other prefix ignored

- **WHEN** the consumer prefix is `services/billing` and the diff touches only `services/auth/`
- **THEN** the gate does not run linters or tests and git is not blocked by CQB

#### Scenario: Does not scan the module

- **WHEN** the diff adds a new HTTP handler under the prefix
- **THEN** the bundle MUST NOT include complexity of untouched files in the same module

### Requirement: Bundle colors and git exit

The orchestrator MUST write a JSON bundle with the raw result of each slot. Each signal MUST be one of: red, yellow, skip, unavailable, green. The same orchestrator MUST serve the optional git hook and `/cqb`. An agent MUST NOT be the git exit code. The process MUST exit 0 when there is no red; MUST exit 1 when there is red. Yellow MUST NOT change the exit code.

#### Scenario: Same orchestrator

- **WHEN** the opt-in hook and `/cqb` run CQB on the same diff
- **THEN** tools, recut, and colors in the bundle match

#### Scenario: Agent does not release the push

- **WHEN** an LLM interprets the bundle
- **THEN** that interpretation does not change the hook exit; only the orchestrator decides red vs yellow vs skip

### Requirement: Constitution is not YAML

The following MUST hold even if `cqb.yaml` tries to say otherwise: whole-module scan is forbidden; absolute complexity applies only to **new** functions; a legacy function touched only in the body uses **delta** complexity (yellow if delta exceeds the configured delta ceiling); yellow never fails git; missing tests on legacy symbols outside the red allowlist MUST NOT be red; the pre-push hook MUST be no-op unless an explicit environment flag is set; the agent is not the git exit code. Keys that would invert this (whole-module scan, yellow-blocks, always-on hook, red on legacy absolute complexity) MUST be rejected or ignored so the constitution wins.

#### Scenario: YAML cannot make yellow fail git

- **WHEN** `cqb.yaml` contains a setting that would fail the process on yellow complexity
- **THEN** `cqb run` still exits 0 for that yellow and documents that the setting is not honored

#### Scenario: Legacy body change is delta

- **WHEN** the diff edits only the body of a pre-existing function and estimated cognitive complexity rises by 1
- **THEN** the bundle lists that function as delta (not the absolute historical complexity) and that axis is not red

### Requirement: Opt-in hook

Without the documented environment flag the pre-push hook MUST be no-op. With the flag, push MUST fail when gofmt/vet/build on the scoped packages fails; when an implied e2e suite fails by assertion; when Docker is missing **and** at least one e2e suite is implied; when the e2e catalog is broken; when a **red-allowlist** cover or content-hunter slot is red. With the flag, push MUST NOT fail solely for complexity over ceiling, missing quick tests **outside** the allowlist, or surviving mutants.

#### Scenario: Push without flag

- **WHEN** `git push` runs without the CQB environment flag
- **THEN** the hook does not run golangci, e2e, or Gremlins and the push proceeds

#### Scenario: Vet red with flag

- **WHEN** the flag is set and `go vet` on a touched package fails
- **THEN** the push is aborted and the bundle records the vet output

#### Scenario: Complexity yellow with flag

- **WHEN** the flag is set, vet/build pass, and a **new** function has cognitive complexity 31 with ceiling 30
- **THEN** the push is not aborted for that metric and the bundle marks yellow on that function

### Requirement: Complexity ceilings on new code

A **new** function (new file, or `func` line added in an existing file) MUST be measured for cognitive, cyclomatic, and nested-if complexity. Default ceilings MUST be the golangci-lint **tool** defaults (cognitive 30, cyclomatic 30, nested-if 5) unless `cqb.yaml` sets others. Exceeding a ceiling MUST be yellow, never red. `funlen` MUST NOT be part of v1.

#### Scenario: New function over cognitive ceiling

- **WHEN** the diff adds `func NormalizeInvoiceRef` with cognitive complexity 31 and the ceiling is 30
- **THEN** the bundle lists the function and yellow on that axis

#### Scenario: Sequential error checks under a raised cyclo ceiling

- **WHEN** `cqb.yaml` sets cyclomatic ceiling 35 and a new GET parses many query params with sequential `if err != nil`, cyclo 32 and cognitive 9
- **THEN** cyclo is under the ceiling (green on that axis) and the bundle MUST NOT treat the function as red for cyclo

### Requirement: Quick test and mutation on new testable symbols

A **new** symbol on a testable path (configured include prefixes; handlers that only parse query and call a service MUST NOT be required) MUST have a package test that **invokes** the symbol (`TestFoo` / `TestFoo_` alone MUST NOT suffice). Absence **outside** the red allowlist MUST be yellow. Absence **on** the allowlist MUST be red. If the test exists, mutation MAY run on that package; a surviving mutant MUST be yellow. Missing mutation tooling MUST be `unavailable`, never green. Mutation MUST NOT use e2e as the oracle and MUST NOT mutate `*_test.go`.

#### Scenario: New util without a calling test

- **WHEN** the diff adds `NormalizeX` under a testable include path without a test that calls `NormalizeX(`
- **THEN** the bundle marks yellow for missing quick test (outside the allowlist) and mutation does not run on that symbol

#### Scenario: Surviving mutant is yellow

- **WHEN** `NormalizeX` has a calling test and mutation reports a survivor in that function
- **THEN** the bundle marks yellow with file, line, and mutant kind; the flagged push does not abort for that alone

### Requirement: E2E catalog by suite directory

Each directory `internal/e2e/<suite>/` under the consumer prefix that the catalog uses MUST contain `globs.txt` (one production glob per line). The gate MUST run only suites whose glob matches the diff. Production code no suite claims MUST yield `e2e: skipped`. A suite directory without `globs.txt`, or a glob pointing at a missing path, MUST break the catalog (red with the hook flag). The gate MUST NOT hardcode a single suite name as the only e2e type.

#### Scenario: Diff with no matching suite

- **WHEN** the diff touches only a city-list GET and no `globs.txt` matches
- **THEN** e2e is skipped and the gate does not start Postgres

#### Scenario: Orphan suite directory

- **WHEN** `internal/e2e/invoices/` exists without `globs.txt` and the orchestrator runs
- **THEN** the catalog fails with a missing-glob message and e2e is not a silent skip

### Requirement: Red allowlist for cover and content hunters

Cover ratchet and content hunters (blind assert, compound assert, missing boundary case, placebo validator, duplicate observable message, non-deterministic test, order-dependent test) MUST be **red** only for production (or test) paths that match the consumer's red allowlist. Outside the allowlist those hunters MUST be yellow or skip. An **empty** allowlist MUST mean no cover red and no hunter red (hygiene gofmt/vet/build may still be red). The allowlist MUST be an explicit list or name pattern in `cqb.yaml`, never inferred silently from "this package has tests". Cover MUST use per-file statements on the allowlist, not module or mega-package percent. I/O vs pure classification MUST use configured import hints. Baseline MUST NOT be rewritten by the hook; a stale baseline (real cover higher than recorded) MUST be yellow.

#### Scenario: Empty allowlist

- **WHEN** `cqb.yaml` has no red allowlist and the diff adds a pure helper with no unit test
- **THEN** cover is skip and content hunters are not red; gofmt/vet/build still apply

#### Scenario: Allowlist I/O patch under floor

- **WHEN** the allowlist includes `internal/application/**/billing*` and an I/O file's new-line cover is below 80%
- **THEN** the cover slot is red and the flagged push aborts

#### Scenario: Hunter outside allowlist is yellow

- **WHEN** a new test uses `t.Fatal("short")` in a file outside the allowlist
- **THEN** the hunter slot is yellow and the flagged push does not abort for that finding
