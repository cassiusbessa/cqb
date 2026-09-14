---
name: cqb-setup
description: >-
  First-run interview for CQB. Installs the CLI if missing, runs cqb init,
  HALTs before writing strict paths (lista de rigor), suggests raising
  cyclomatic for HTTP-handler scans, renders the bundle-reader from cqb.yaml,
  never overwrites existing consumer skills or rules.
---

# /cqb-setup

## 1. Install and init

- If `cqb` is not on PATH: `go install github.com/cassiusbessa/cqb/cmd/cqb@<version>` then continue.
- If `.cqb/` is missing: run `cqb init` in the consumer module. Init vendors the engine, writes default `cqb.yaml` (ceilings 30/30/5, empty `strict_paths`), writes `scan.json`, writes the hook **file**, and sets local `core.hooksPath` only when that config is unset. Execution still needs `CQB=1`.
- Skipping the rest of this slash after init MUST leave a working non-blocking gate.

## 2. Read scan.json

Deterministic scan only: module path, `*_test.go` density, `internal/e2e/*/globs.txt`, generated-file patterns. Propose **strict-path** candidates (directories that already have an e2e suite). Do not infer the list from "packages that have tests" without a prompt.

## 3. HALT — lista de rigor (`strict_paths`)

Ask yes/no for each candidate (for example `internal/billing/`). **Write `strict_paths` only after explicit confirmation.** No confirmation → leave `strict_paths: []`. Cover and content hunters stay non-red.

## 4. Complexity ceilings

Defaults MUST stay golangci-lint **tool** defaults: cognitive 30, cyclomatic 30, nested-if 5.

If the scan looks like HTTP handlers with sequential `if err != nil`, **suggest raising cyclomatic** (more permissive, e.g. 35). MUST NOT silently lower ceilings to the docs "recommend 10".

## 5. Copy skills without overwrite

Copy kit templates into `.cursor/skills` and `.cursor/commands` only when the destination file does **not** exist. A pre-existing skill (HTTP endpoints, SQL, domain) MUST remain unchanged. Do not invent product/domain skills. The only new agent files are gate helpers (bundle reader and optional standing facts: test culture, language of user-facing strings).

Use `cqb setup-copy --dry-run` to preview. Use `cqb render-reader` to interpolate ceilings and strict paths from `cqb.yaml` into the bundle-reader skill. `prefix` is edited in `cqb.yaml`.

## 6. Hook still needs CQB=1

Init may already have set local `core.hooksPath`. Never export `CQB=1` in bashrc. Do not overwrite an existing `core.hooksPath` (husky, etc.) unless the human asks.
