## Context

See proposal.md (Why). The repo today is scaffolding (README, contributing, public-safety rule). There is no CLI, engine, or `/cqb` yet. Specs: `gate`, `review`, `bootstrap`. Hosts are assumed to have Go and Python 3. This kit will be public; fixtures MUST be invented generic Go.

The flow is a **local synchronous CLI**. No database, tenant, or network service is required except optional Docker when an e2e suite is implied.

## Goals / Non-Goals

**Goals:**

- One Go CLI (`cqb`) that `init`s, `run`s, and `upgrade`s.
- Engine + review steps **vendored** into the consumer so a kit release cannot tighten a team without `cqb upgrade`.
- Constitution enforced in code (illegal YAML keys ignored).
- Cursor first-run (`/cqb-setup`) can call the CLI; CI/devcontainer can call `cqb init` with no agent.

**Non-Goals (design):**

- Rewriting hunters in Go for v1 (Python 3 remains the analysis runtime).
- Publishing to GitHub Actions as the gate.
- Auto-attaching `core.hooksPath`.
- Generating product/domain skills.

## Decisions

### D1 — Go CLI, embedded Python engine

`cmd/cqb` is a small Go module. `init` writes `.cqb/` from `go:embed` (orchestrator, Python lib, review step templates, bundle-reader template). `run` execs the vendored orchestrator with `python3`. Host tools (`golangci-lint`, `gremlins`) stay `go install` with versions in the CLI.

**Rejected:** all-Go hunters in v1 (months of port, no behavior win). **Rejected:** pip/npm as the user-facing install (Go teams already have `go install`). **Rejected:** clone-the-kit-beside-the-app as the consumption path.

### D2 — Copy, never `@latest`

Daily `cqb run` reads `.cqb/` and `cqb.yaml` in the consumer. The published module is only how you get new bits via `cqb upgrade`. Pin the kit version in `cqb.yaml`.

**Rejected:** submodule or `go.mod` replace pointing at HEAD (a hunter bump would hit every consumer on next run).

### D3 — Three host installs, one repo copy

| Where | What |
|---|---|
| PATH | `cqb`, `golangci-lint`, `gremlins` |
| Consumer git | `.cqb/` engine, `cqb.yaml`, optional hook **file** (not `core.hooksPath`) |

`/cqb-setup` MAY `go install` `cqb` then `cqb init` if either is missing.

### D4 — Constitution in the engine, tunables in YAML

`cqb.yaml` MAY set: `prefix`, complexity ceilings, delta ceiling, red allowlist (globs / name regexp), testable include/exclude, I/O import hints, enabled extra hunters, e2e catalog root, operator language.

The engine MUST ignore or refuse: whole-module scan, yellow-blocks, always-on hook, red on legacy absolute complexity, red on missing tests outside the allowlist.

Defaults: ceilings **30 / 30 / 5** (golangci-lint tool defaults). `/cqb-setup` **suggests raising cyclomatic** when the scan looks like HTTP handlers with sequential `if err != nil`. It MUST NOT default to the docs recommendation of 10.

### D5 — Empty red allowlist until a human says yes

Scan (`cqb init` writes `scan.json`: module path, `*_test.go` density, `internal/e2e/*/globs.txt`, generated-file patterns, validator-call names). `/cqb-setup` proposes allowlist candidates and **HALTs**. No confirmation → allowlist stays empty (cover/hunters not red).

**Rejected:** infer allowlist from “packages that have tests” with no prompt (false red on day one).

### D6 — `/cqb` owns the review; BMAD is not the product name

Review steps (gather, parallel layers, triage, present) live in the vendored templates as **CQB** skills/commands (`/cqb`, `/cqb-setup`). Lineage may be a stripped code-review orchestrator; the user-facing name is CQB only. Document-only targets share `/cqb`. Operator-facing prose defaults to **pt-BR**; hunter prompts stay English; `cqb.yaml` MAY override operator language.

Consumer glob rules and skills overlay kit examples on matching paths. Bundle colors are not overridable by a skill.

### D7 — Gate-helper generation from templates

`/cqb-setup` renders a bundle-reader skill from `cqb.yaml` (so prose cannot drift from colors). Standing facts: at most a few sentences (suite density, user-facing string language). Never overwrite existing consumer skill/rule files. Never emit endpoint/SQL/business recipes.

### D8 — Generic hunters on, extras opt-in

Always-on (still yellow outside allowlist): blind assert, compound assert, missing boundary, non-deterministic test, order-dependent test, duplicate observable literal. Named extras (e.g. placebo struct validator) default **off**; scan MAY suggest enabling if it sees a matching call.

## Risks / Trade-offs

- [Python 3 missing on the host] → `cqb run` slot `unavailable` with an install hint; vet/build can still run from the Go CLI.
- [Setup still writes a guessed allowlist] → HALT is required; empty default is tested.
- [Consumer YAML tries to freeze git on yellow] → engine ignores the key; documented in the bundle reason.
- [Upgrade surprise] → copy + pin; `cqb upgrade` shows a file diff.
- [Public leak of private source] → contributing rule + always-on Cursor rule; tests use `internal/billing` fixtures only.
- [pt-BR default on a public English repo] → docs in English; operator language is a yaml field defaulting to pt-BR for the first audience, overridable.

## Migration Plan

1. Implement CLI + embedded engine + `cqb.yaml` schema + constitution guards in **this** repository with generic fixtures.
2. Dogfood `cqb init` / `cqb run` against those fixtures (not against a private app tree).
3. Consumers adopt later with `go install` + `cqb init` + optional `/cqb-setup`. Rollback: delete `.cqb/` and `cqb.yaml`; git hook was never forced on.

No production data. No cutover of a named product in this change.

## Open Questions

None that block specs or tasks. Slash name for document-only remains `/cqb` (gather classifies). Exact extra-hunter YAML names can be listed as they are ported.
