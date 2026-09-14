# bootstrap Specification

## Purpose

Defines first-run install: host tools, vendored engine, optional `/cqb-setup` interview, `cqb.yaml`, and public-safe artifacts that never overwrite the consumer's own skills.

## Requirements

### Requirement: Init attaches local hooksPath when unset

`cqb init` MUST set repository-local `core.hooksPath` to `.cqb/hooks` when that git config is empty in the current repository. When `core.hooksPath` is already set to a different value, init MUST leave it unchanged and MUST print how to attach `.cqb/hooks` by hand. Init MUST NOT write global git config. The hook script MUST remain a no-op unless the environment flag `CQB=1` is set. Yaml MUST NOT be able to make the hook always-on.

#### Scenario: Fresh repo after init

- **WHEN** `cqb init` runs in a git repository where `core.hooksPath` is unset
- **THEN** `git config --local --get core.hooksPath` is `.cqb/hooks` and `git push` without `CQB=1` does not run the gate

#### Scenario: Existing hooksPath preserved

- **WHEN** the repository already has `core.hooksPath` set to `.husky`
- **THEN** after `cqb init` that value is still `.husky` and stdout explains how to use `.cqb/hooks`

#### Scenario: Flag still required

- **WHEN** init has set `core.hooksPath` to `.cqb/hooks` and the operator runs `git push` without `CQB=1`
- **THEN** the hook does not run golangci, e2e, or Gremlins and the push proceeds

### Requirement: Setup interviews for strict paths

`/cqb-setup` MUST describe the list as strict paths (pt-BR: lista de rigor). It MUST NOT write `strict_paths` (or the `red_allowlist` alias) without an explicit human confirmation. Without confirmation the list MUST stay empty. It MUST NOT use “allowlist” in new operator-facing copy. Candidates MUST still come from the scan (directories that already have an e2e suite), not from every package that has a test.

#### Scenario: No confirmation leaves an empty list

- **WHEN** setup proposes `internal/e2e/invoices` as a strict-path candidate and the operator does not confirm
- **THEN** `cqb.yaml` has an empty `strict_paths` list and `cqb run` still works without cover/hunter red

#### Scenario: Confirmation writes the glob

- **WHEN** the operator confirms a proposed directory `internal/billing`
- **THEN** `cqb.yaml` contains that path under `strict_paths`

### Requirement: Catalog root only when exactly one e2e tree

When `cqb init` writes a **new** `cqb.yaml`, if the scan finds **exactly one** directory that already holds e2e `globs.txt` files, init MAY set `e2e.catalog_root` to that directory so the engine knows where to look for suites. If the scan finds zero or more than one such directory, init MUST NOT pick a catalog root on the operator’s behalf (leave default/empty). This MUST NOT write `strict_paths` or `prefix`. Existing yaml MUST NOT be overwritten.

#### Scenario: Single e2e tree

- **WHEN** init writes a new yaml and the only e2e tree is `services/billing/internal/e2e`
- **THEN** `e2e.catalog_root` in that yaml points at `services/billing/internal/e2e`

#### Scenario: Two e2e trees

- **WHEN** init writes a new yaml and both `services/billing/internal/e2e` and `services/auth/internal/e2e` exist
- **THEN** init does not invent a catalog root that would hide one of the trees
