---
name: cqb-setup
description: >-
  First-run interview for CQB. Installs the CLI if missing, runs cqb init,
  HALTs before writing a red allowlist, suggests raising cyclomatic for
  HTTP-handler scans, renders the bundle-reader from cqb.yaml, never
  overwrites existing consumer skills or rules.
---

# /cqb-setup

## 1. Install and init

- If `cqb` is not on PATH: `go install github.com/cassiusbessa/cqb/cmd/cqb@<version>` then continue.
- If `.cqb/` is missing: run `cqb init` in the consumer module. Init vendors the engine, writes default `cqb.yaml` (ceilings 30/30/5, empty red allowlist), writes `scan.json`, writes the hook **file**, and MUST NOT set `git config core.hooksPath`.
- Skipping the rest of this slash after init MUST leave a working non-blocking gate.

## 2. Read scan.json

Deterministic scan only: module path, `*_test.go` density, `internal/e2e/*/globs.txt`, generated-file patterns. Propose red-allowlist **candidates**. Do not infer the allowlist from "packages that have tests" without a prompt.

## 3. HALT — red allowlist

Ask yes/no for each candidate (for example `internal/billing/`). **Write the allowlist only after explicit confirmation.** No confirmation → leave `red_allowlist: []`. Cover and content hunters stay non-red.

## 4. Complexity ceilings

Defaults MUST stay golangci-lint **tool** defaults: cognitive 30, cyclomatic 30, nested-if 5.

If the scan looks like HTTP handlers with sequential `if err != nil`, **suggest raising cyclomatic** (more permissive, e.g. 35). MUST NOT silently lower ceilings to the docs "recommend 10".

## 5. Copy skills without overwrite

Copy kit templates into `.cursor/skills` and `.cursor/commands` only when the destination file does **not** exist. A pre-existing skill (HTTP endpoints, SQL, domain) MUST remain unchanged. Do not invent product/domain skills. The only new agent files are gate helpers (bundle reader and optional standing facts: test culture, language of user-facing strings).

Use `cqb setup-copy --dry-run` to preview. Use `cqb render-reader` to interpolate ceilings and allowlist from `cqb.yaml` into the bundle-reader skill.

## 6. Hook stays opt-in

Print how to attach: `git config core.hooksPath .cqb/hooks` and `CQB=1`. Never run that `git config` from this slash unless the human asks.
