# CQB

Local quality gate and code review ritual for Go services.

The gate measures **new code on the diff**, not the whole module. Yellow
never blocks git. Red is an allowlist you choose later (empty on first
install). Repository skills and rules stay in charge of domain; this kit
does not replace them.

## Status

Early scaffolding. The public surface will be:

- `cqb init` — install host tools and vendor the engine
- `/cqb-setup` — one Cursor session to write `cqb.yaml` (thresholds, red scope)
- `cqb run` — the gate
- `/cqb` — the review (same orchestrator as the hook)

## This repository

Keep it free of any employer or client source: no copied application
code, credentials, internal paths, or proprietary domain language.
See [CONTRIBUTING.md](CONTRIBUTING.md).
