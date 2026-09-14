## Purpose

Defines first-run install: host tools, vendored engine, optional `/cqb-setup` interview, `cqb.yaml`, and public-safe artifacts that never overwrite the consumer's own skills.

## ADDED Requirements

### Requirement: Host CLI via go install

The supported way to get the `cqb` binary onto the host MUST be `go install github.com/cassiusbessa/cqb/cmd/cqb@<version>` with a pinned version. `cqb init` MUST `go install` pinned `golangci-lint` and `gremlins` onto the host PATH. Init MUST NOT require cloning this repository next to the consumer.

#### Scenario: Init installs linters

- **WHEN** the operator runs `cqb init` in a Go module and the linters are missing
- **THEN** golangci-lint and gremlins are installed at the versions this kit pins and `cqb run` can find them on PATH

#### Scenario: No sidecar clone

- **WHEN** the operator has only the `cqb` binary and a Go repo
- **THEN** `cqb init` completes without a second git clone of the kit as a sibling directory

### Requirement: Vendor copy of the engine

`cqb init` MUST copy the engine and review step templates into the consumer (for example `.cqb/`) and record a kit version. Daily `cqb run` MUST use that copy, not `@latest` from the network. `cqb upgrade` MUST be an explicit command that refreshes the copy. Init MUST print how to opt into `core.hooksPath` and MUST NOT set that git config itself.

#### Scenario: Run uses the vendored copy

- **WHEN** the published kit later adds a stricter hunter and the consumer has not upgraded
- **THEN** `cqb run` in that consumer still behaves as the vendored version

#### Scenario: Hook stays opt-in

- **WHEN** `cqb init` finishes
- **THEN** `core.hooksPath` is unchanged and the printed command is the only way to attach the hook

### Requirement: Setup slash may call init

`/cqb-setup` MUST invoke `cqb init` when the CLI or vendored engine is missing (`go install` of `cqb` first if needed). It MUST then interview for `cqb.yaml`. Skipping `/cqb-setup` after init MUST leave a working gate: gofmt/vet/build red on the diff; complexity yellow at tool defaults; empty red allowlist; consumer skills untouched.

#### Scenario: Cursor-only first run

- **WHEN** the operator runs `/cqb-setup` and `cqb` is not on PATH
- **THEN** the session installs the CLI, runs init, then continues the interview

#### Scenario: Init without setup

- **WHEN** the operator runs only `cqb init` and never `/cqb-setup`
- **THEN** `cqb run` works in the non-blocking default (no cover red, no hunter red)

### Requirement: Interview does not invent a red allowlist

`/cqb-setup` MUST NOT write a red allowlist without an explicit human confirmation. It MAY propose candidates from a deterministic scan (directories that already have `*_test.go` or `internal/e2e/<suite>/globs.txt`) and MUST HALT for yes/no. Default complexity ceilings MUST be golangci-lint tool defaults (30 / 30 / 5). If the scan indicates HTTP handlers with sequential error checks, setup MUST **suggest raising cyclomatic** (more permissive) and MUST NOT silently lower ceilings to the golangci docs "recommend 10".

#### Scenario: HALT on allowlist

- **WHEN** the scan finds tests under `internal/billing/`
- **THEN** setup asks whether that path is the red allowlist and writes it only after confirmation

#### Scenario: Default ceilings are tool defaults

- **WHEN** the operator accepts defaults
- **THEN** `cqb.yaml` records cognitive 30, cyclomatic 30, nested-if 5

### Requirement: Generated helpers do not overwrite domain skills

Setup MAY render a bundle-reader skill from a template plus `cqb.yaml`, and MAY write a small number of standing facts (test culture, language of user-facing strings). It MUST NOT create product/domain skills (how to add an endpoint, how to write SQL, how to implement a business rule). It MUST NOT overwrite existing files under the consumer's skills or rules directories.

#### Scenario: Existing skill survives

- **WHEN** the consumer already has a skill for creating HTTP endpoints and `/cqb-setup` runs
- **THEN** that skill file is unchanged

#### Scenario: No domain skill invented

- **WHEN** setup finishes on a repo with no product skills
- **THEN** the only new agent files are gate helpers (bundle reader and optional facts), not an endpoint or persistence recipe

### Requirement: Public-safe kit sources

Files shipped in this GitHub repository MUST NOT contain private employer or client application source, credentials, internal product names, or ticket IDs. Tests and examples in the kit MUST use invented generic Go (for example `internal/billing`).

#### Scenario: Fixture is generic

- **WHEN** a unit test of the engine needs a sample Go file
- **THEN** the fixture lives under a made-up module path and MUST NOT copy a private service tree
