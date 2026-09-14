## Purpose

Defines the `/cqb` Cursor ritual: gather a diff, run review layers in parallel, triage, present in Portuguese to the operator, overlay consumer rules, and read the quality bundle without treating skip or unavailable as a pass.

## ADDED Requirements

### Requirement: Single slash for code and documents

`/cqb` MUST be the user-facing review command. For a code diff it MUST run gather → parallel layers → triage → present. For a document-only target (proposal or spec with no code diff) it MUST run editorial structure and prose lenses instead of code hunters. It MUST NOT install or run sprint/story BMAD modules.

#### Scenario: Code diff

- **WHEN** the operator invokes `/cqb` with uncommitted Go changes
- **THEN** the workflow gathers a unified diff file, launches code layers, triages, and presents patch / defer / decision_needed / rejected

#### Scenario: Document only

- **WHEN** the operator invokes `/cqb` on a spec markdown with no code diff
- **THEN** the workflow runs document lenses and MUST NOT invent code triage on prose

### Requirement: Review starts the same gate

After writing the diff file, if the diff touches a prefix listed in `cqb.yaml`, gather MUST start `cqb run` in the **same diff mode**, in the background, writing the bundle to `.quality/last.json`. Blind and edge layers MAY start without waiting for the bundle. The verification-gap layer MUST wait until the bundle is valid JSON with `has_red` and the running flag is gone. Docker missing MUST NOT abort the review (`e2e: unavailable`). If the diff does not touch a configured prefix, `{quality_bundle}` MUST stay empty.

#### Scenario: Review without Docker with an implied e2e suite

- **WHEN** `/cqb` runs on a diff that implies an e2e suite and Docker is down
- **THEN** the review continues, the bundle records Docker unavailable, and verification-gap treats e2e as not executed (not as passed)

#### Scenario: Diff outside every prefix

- **WHEN** the diff does not touch any `cqb.yaml` prefix
- **THEN** gather does not start `cqb run` and verification-gap does not wait on a bundle

### Requirement: Consumer rules overlay kit examples

Path-scoped rules and skills already in the consuming repository MUST take precedence over kit examples for matching paths (how to write tests, how to structure a handler, domain language). The kit MUST NOT overwrite those files during review. Triage MUST defer findings whose fix is to edit agent-context files (AGENTS.md, rules, other specs) and MUST defer issues the loaded OpenSpec pack already accepted (non-goal or explicit risk) unless this change enlarged the hole. Bundle **colors** stay the machine plus `cqb.yaml`; a rule MUST NOT silently invert a red slot.

#### Scenario: Glob rule wins on that path

- **WHEN** a consumer rule whose glob matches `internal/interface/**` says sequential `if err != nil` is the house style and a hunter asks to split the function to lower cyclo
- **THEN** triage rejects or defers that finding in favor of the matching rule

#### Scenario: Rule does not turn red into green

- **WHEN** a content hunter is red on the allowlist and a consumer skill says "do not worry about blind asserts"
- **THEN** the bundle slot remains red; the skill MUST NOT be treated as changing the git exit

### Requirement: Presentation order and language

The operator-facing report MUST start with a prose summary of the bundle (colors and why each flagged function failed), then the unified review report. The operator language MUST be Portuguese (pt-BR). Hunter prompts MAY stay in English. The raw JSON bundle MUST NOT be pasted in full into the chat.

#### Scenario: Bundle before triage list

- **WHEN** `/cqb` finishes with a quality bundle
- **THEN** the user-visible message starts with colors and each yellow/red function with the reason, and only then lists patch / defer / rejected

### Requirement: Missing tests on new symbols are not automatic defer

A missing `Test<Symbol>` that invokes a **new** symbol on a configured testable path MUST NOT be classified as `defer` only because the repo "has almost no suite". Outside the red allowlist that signal is yellow in the bundle; on the allowlist it is red. Legacy missing tests remain eligible for `defer`.

#### Scenario: New domain function without a calling test

- **WHEN** the diff adds a function under a testable include path with no invoking test and `/cqb` triages
- **THEN** the missing quick-test finding is not `defer` solely due to a thin suite
