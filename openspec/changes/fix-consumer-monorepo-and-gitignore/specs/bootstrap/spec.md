## Purpose

Makes `cqb init` keep the consumer git tree free of runtime junk and discover nested module catalogs without forcing the operator to hand-edit every path.

## ADDED Requirements

### Requirement: Init upserts a managed gitignore block

`cqb init` MUST ensure the consumer `.gitignore` contains a clearly delimited CQB block listing at least: `.quality/`, `.cqb/scan.json`, `.cqb/work/`, `*.coverprofile`, and `.cqb/**/__pycache__/`. If the file does not exist, init MUST create it. If the block already exists, init MUST replace that block in place (idempotent). Init MUST NOT add `.cqb/engine`, `.cqb/hooks`, `.cqb/templates`, or `cqb.yaml` to the ignore list. Existing unrelated ignore lines MUST be preserved.

#### Scenario: Fresh repo

- **WHEN** `cqb init` runs in a directory with no `.gitignore`
- **THEN** a `.gitignore` exists that ignores `.quality/` and `.cqb/scan.json` and does not ignore `cqb.yaml`

#### Scenario: Second init does not duplicate

- **WHEN** `cqb init` runs twice
- **THEN** the CQB ignore block appears once

#### Scenario: Engine stays commitable

- **WHEN** init finishes
- **THEN** `.cqb/engine/orchestrator.py` is not matched by the CQB ignore block

### Requirement: Scan and defaults find nested e2e

`cqb init` scan MUST record e2e suite directories relative to the git root. When exactly one configured prefix exists and `{prefix}/internal/e2e` exists, a newly written `cqb.yaml` MAY set `e2e.catalog_root` to that path; if `cqb.yaml` already exists, init MUST NOT overwrite the operator's catalog_root. Matching in the engine still MUST work if catalog_root stays `internal/e2e` thanks to prefix-relative lookup.

#### Scenario: Nested catalog on first yaml

- **WHEN** init writes a new `cqb.yaml` and `services/billing/internal/e2e` exists and prefix is `services/billing`
- **THEN** `e2e.catalog_root` in that yaml points at `services/billing/internal/e2e` or the engine still finds that tree via prefix
