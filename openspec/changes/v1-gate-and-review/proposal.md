## Why

Go teams that want a local quality gate plus an adversarial code-review slash today either bolt together one-off scripts or copy a private setup they cannot publish. CQB should be that ritual as a **generic, public kit**: look forward on the diff, never freeze day-to-day git, and leave each consuming repo's own skills and rules in charge of domain.

## What Changes

- Ship a **CLI** (`cqb`) installable with `go install github.com/cassiusbessa/cqb/cmd/cqb@<version>`.
- `cqb init` vendors the engine into the consuming repo, installs host tools (`golangci-lint`, `gremlins`) at pinned versions, and does **not** enable a git hook by itself.
- `/cqb-setup` (Cursor) may call `cqb init` if the CLI is missing, then interviews for `cqb.yaml` (complexity thresholds, optional red allowlist). Skipping setup still leaves a working gate in the non-blocking default.
- `cqb run` produces a color bundle (red / yellow / skip / unavailable / green). Yellow never exits 1. The agent never owns the git exit code.
- `/cqb` is the code-review slash (gather → parallel layers → triage → present). It starts `cqb run` in the background when the diff touches a configured prefix. Document-only targets use editorial lenses in the same slash.
- Complexity ceilings are YAML (install-time defaults = golangci-lint **tool** defaults 30 / 30 / 5). Setup **suggests raising cyclomatic** for HTTP-handler style. Constitution (diff-only, new funcs, yellow, empty red allowlist, opt-in hook) is **not** YAML.
- Engine is **copied** into the consumer (pin + `cqb upgrade`), not referenced at `@latest`.

## Non-goals

- Non-Go languages.
- GitHub Actions / CI as the gate (this kit is local).
- Always-on pre-push hook, `yellow_blocks`, whole-module scan, or red on legacy complexity / missing tests outside an allowlist.
- Generating product/domain skills (HTTP recipes, SQL, business rules). Setup only renders **gate-helper** artifacts (bundle reader, thin standing facts) and never overwrites existing consumer skills or rules.
- Migrating any specific existing service onto CQB in this change (consumers adopt later).
- Mutation score percentages or `funlen`.
- A plugin marketplace. Extra hunters are named enablement in YAML, default off except the generic Go testing hunters.

## Capabilities

### New Capabilities

- `gate`: orchestrator, bundle colors, constitution, cover/hunters on an optional red allowlist, opt-in hook.
- `review`: `/cqb` gather → layers → triage → present; overlay of consumer rules; verification-gap reads the bundle.
- `bootstrap`: `cqb init`, `/cqb-setup`, `cqb.yaml`, host tools, vendor copy, public-safe install.

### Modified Capabilities

- (none; this repo has no main specs yet)

## Impact

- New Go module `github.com/cassiusbessa/cqb` (CLI + vendored engine files + Cursor skill/command templates).
- Consumer repos gain `.cqb/` (vendored engine), `cqb.yaml`, optional hook snippet, generated bundle-reader skill. Their existing `.cursor/skills` and glob rules stay authoritative on matching paths.
- Host PATH: `cqb`, `golangci-lint`, `gremlins` via `go install` with pinned versions.
- This repository remains free of private application source; tests use invented generic Go fixtures.
