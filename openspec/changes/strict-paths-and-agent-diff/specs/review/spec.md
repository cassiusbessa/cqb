## ADDED Requirements

### Requirement: Slash runs the gate then interprets

When `/cqb` gathers a code diff that touches a configured prefix, it MUST invoke `cqb run` (same orchestrator as the CLI) and MUST interpret `.quality/last.json` in the operator-facing report. It MUST NOT tell the operator that `/cqb` does not replace `cqb run` for review. The CLI remains available for humans and for the hook. If the diff does not touch any prefix, gather MUST NOT start `cqb run`. Docker missing MUST NOT abort the review (`e2e: unavailable`); verification-gap MUST treat that as not executed.

#### Scenario: Review starts the orchestrator

- **WHEN** the operator invokes `/cqb` with Go changes under `prefix`
- **THEN** `cqb run` writes `.quality/last.json` and the user-visible message starts from that bundle’s colors, not from an empty report

#### Scenario: Operator need not type cqb run

- **WHEN** `/cqb` is used for a code review
- **THEN** the workflow does not require a prior manual `cqb run` in the terminal for the bundle to exist

### Requirement: Agentic compare base is explicit

Unless the operator asked for `uncommitted`, `staged`, `push`, or a file list, `/cqb` MUST call `cqb run --mode review` (merge-base against the resolved base). If that command fails because the base is ambiguous, `/cqb` MUST stop and ask which ref to compare; it MUST NOT silently diff the working tree against `HEAD`. After the operator names a base, it MUST re-run with `--base <ref>`.

#### Scenario: Unique default branch

- **WHEN** `/cqb` runs on a feature branch, the repo has `main` and not `master`, and no upstream is set
- **THEN** the gate analyzes the feature branch against `main`

#### Scenario: Ambiguous base asks

- **WHEN** `/cqb` runs and `cqb run --mode review` reports that `main` and `master` both exist
- **THEN** the agent asks the operator which ref to use and does not present a review of a guessed diff

#### Scenario: Operator asked for working tree

- **WHEN** the operator says to review only uncommitted files
- **THEN** `/cqb` uses default `cqb run` (working tree versus `HEAD`) instead of `--mode review`
