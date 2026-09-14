# CQB

Local **quality gate** and **code-review ritual** for Go modules.

CQB measures **new code on the git diff**, not the whole tree. It writes a
JSON bundle (`.quality/last.json`) that a human or a Cursor slash (`/cqb`)
can read. Yellow never blocks git. Red is an **allowlist you name later**
(empty on first install). The consuming repo keeps its own skills, path-scoped
rules, and domain language — this kit does not replace them.

```
cqb init          → vendor engine, write cqb.yaml, gitignore, opt-in hook file
/cqb-setup        → optional interview; HALT before writing a red allowlist
cqb run           → gate on the diff (exit 1 only on red, plus one hook case)
/cqb              → review: gather → layers → triage → present
```

Pinned host tools (installed by `cqb init` if missing): **golangci-lint v2.4.0**,
**gremlins v0.5.1**. Daily `cqb run` uses the **vendored** copy under `.cqb/engine`,
never `@latest`.

---

## Install

Requires Go 1.22+, `python3`, `git`, and the usual `go`/`gofmt` toolchain.
E2E that implies Docker also needs `docker` on `PATH`.

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cd /path/to/your/go/module   # git root; see Nested modules below
cqb init
```

`cqb init` does **not** set `core.hooksPath`. It:

- copies the engine into `.cqb/engine/` and templates into `.cqb/templates/`
- writes `cqb.yaml` if missing (existing yaml is left alone)
- writes `.cqb/scan.json` (module path, `*_test.go` density, e2e suite dirs)
- upserts a managed block in `.gitignore` (`# cqb begin` … `# cqb end`):
  `.quality/`, `.cqb/scan.json`, `.cqb/work/`, `*.coverprofile`,
  `.cqb/**/__pycache__/` — **not** `.cqb/engine`, hooks, templates, or `cqb.yaml`
- writes `.cqb/hooks/pre-push` (opt-in)
- `go install`s the pinned linter/mutator when they are absent

On a **new** yaml, if the scan finds a single e2e catalog (for example
`services/billing/internal/e2e`), `e2e.catalog_root` is set to that path.

### Optional first-run interview

In Cursor, `/cqb-setup` installs the CLI if needed, runs `cqb init`, then asks
whether any path should become the red allowlist. **HALT** — no confirmation
means the list stays empty. Skipping setup still leaves a working,
non-blocking gate.

### Run

```bash
cqb run                                 # uncommitted (incl. untracked)
cqb run --mode staged
cqb run --mode file-list --files internal/billing/normalize.go
cqb run --mode push                     # what the hook calls
cqb run --output .quality/last.json     # default
```

### Upgrade

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0   # or a newer tag
cqb upgrade     # refresh .cqb/ from *this* binary; bump kit_version in yaml
```

Do not point daily runs at `@latest`. Pin a tag; upgrade on purpose.

---

## Constitution (not YAML)

These cannot be inverted by `cqb.yaml`. Illegal keys such as `yellow_blocks`,
`whole_module`, or `always_on_hook` are **ignored** and listed on the bundle
as `ignored_keys`.

| Rule | Meaning |
|---|---|
| Diff only | Never walk the whole module “to be sure”. |
| New vs legacy complexity | **New** functions: absolute cognitive / cyclomatic / nested-if. **Legacy**: delta only, and only yellow. |
| Yellow never fails git | Complexity over ceiling, hunters outside the allowlist, surviving mutants → exit **0**. |
| Empty red allowlist | Until a human names a scope (`/cqb-setup` HALT). Cover and content hunters stay non-red. |
| Agent ≠ git exit | `/cqb` reads the bundle; it does not decide `git push`. |
| Hook is opt-in | `git config core.hooksPath .cqb/hooks` then `CQB=1 git push`. No flag → the hook is a no-op. Init never attaches it. |

---

## Colors and process exit

Each **slot** is one of: `green`, `yellow`, `red`, `skip`, `unavailable`.

| Color | Git | Meaning |
|---|---|---|
| green | 0 | Ran and passed. |
| yellow | 0 | Signal for review, not a push failure. |
| red | **1** | Allowlist (or hygiene) failure. |
| skip | 0 | Out of scope (empty allowlist, no glob match, diff outside `prefix`). **Not a pass.** |
| unavailable | 0 normally | Tool missing (Docker, gremlins). **Not a pass.** Flagged push is stricter — see below. |

`cqb run` exits **1** when `has_red` is true.

**Also exit 1:** `--mode push` (the opt-in hook) when e2e is `unavailable` **and** at least one suite is implied (typically Docker missing). Same idea as “hygiene would have been red if it could run.” Daily `cqb run` without `--mode push` keeps that slot `unavailable` and exits 0.

`skip` / `unavailable` must not be summarized as green in `/cqb`.

---

## Slots

The bundle is `.quality/last.json` (`schema_version: 1`). Slots:

### `lint`

`gofmt -l`, `go vet`, `go build` on packages of the scoped `.go` files.
Any failure is **red** (hygiene is not gated on the allowlist). golangci-lint
is installed as a host tool for humans/`/cqb`; it is not a red slot in v0.1.

### `complexity`

Per-function metrics on production `.go` in the diff. Defaults match
golangci-lint **tool** defaults, not “clean code 10”:

- new function: cognitive **30**, cyclomatic **30**, nested-if **5** → yellow if over
- legacy: delta cognitive **5** → yellow if over; never red

HTTP `if err != nil` chains often want a **higher** cyclomatic ceiling.
`/cqb-setup` may suggest that; it will not raise it silently.

### `test` / quick-test hunters

For **new** symbols on `testable.include` (minus `exclude`), CQB wants
`TestFoo` **and** a call `Foo(` in the package tests. HTTP handlers
(`http.ResponseWriter`) are exempt.

- outside the allowlist → **yellow**
- on the allowlist → **red** (also reflected on the `test` slot)

### `hunters` (content)

On `*_test.go` in the diff (red only if the file matches the allowlist):

| Hunter | What it flags |
|---|---|
| `blind_assert` | `t.Fatal("short")` / `t.Error("…")` with no format verb — no observed vs expected |
| `compound_assert` | two asserts on one line, or `&&` inside an assert |
| `non_deterministic` | `time.Now` or `math/rand` in a test |
| `order_dependent` | package-level state mutated in tests without `t.Cleanup` |
| `duplicate_observable` | the same fatal/error literal on two lines |
| `missing_boundary` | **new production** line compares to a numeric / `len` literal that never appears in package tests. Slice indexes, HTTP status, and `time.Duration` constants are exempt. A test **name** without `Empty`/`Zero` is not enough. |
| `placebo_validator` | opt-in (`extra_hunters: [placebo_validator]`): `validator.Struct` without asserting the error |

Findings are unique on `(hunter, file, line, message)`.

### `e2e`

Catalog under `e2e.catalog_root` (or `{prefix}/internal/e2e` if that is
where the tree lives). Each suite is `internal/e2e/<name>/globs.txt`.

- Wildcard-free glob lines must exist at `prefix/line` **or** repo-root `line`.
- If the diff matches a suite’s globs, that suite is **implied**.
- Implied + catalog valid → CQB runs `go test -tags e2e -count=1 -timeout 8m ./<suite>`.
  Pass → green. Failed assertion → **red**.
- Implied + `docker` not on `PATH` → `unavailable` (not green).
- No match → `skip`. Broken catalog (missing `globs.txt` or missing literal path) → **red**.

A typical `globs.txt` (module-relative; git may show `services/billing/...`):

```
internal/application/services/*invoice*
internal/db/queries/faturas_queries.sql
```

### `cover`

Runs only when `red_allowlist` is non-empty **and** the diff includes
allowlist production `.go` files. CQB generates a profile with
`go test -vet=off -coverprofile` into `.cqb/work/` (gitignored). You do
not pass `--coverprofile`. The run **never** rewrites the baseline file.

- I/O files (imports in `io_imports`, default `database/sql`, `net/http`, `os`):
  patch below `cover.io_floor` (default 80%) → **red**
- Pure helpers: new symbol with no invoking test → **red**
- File in the baseline whose cover **drops** → **red**
- Cover **higher** than baseline → yellow (stale baseline); refresh with a
  separate, explicit process — not the hook
- Empty allowlist → `skip`

Default baseline path: `.cqb/cover-baseline.json`. Point `cover.baseline_path`
at an existing file if the module already has one.

### `mutation`

Gremlins when a **new** symbol has both `TestFoo` and `Foo(`. Missing binary →
`unavailable`. Survivors are **yellow** (never red in v0.1). No invoking test →
`skip`.

---

## `cqb.yaml`

```yaml
kit_version: "0.1.0"
prefix: ""                    # or services/billing ; prefixes: most-specific first
operator_language: "pt-BR"    # /cqb prose; hunter ids stay English
complexity:
  cognitive: 30
  cyclomatic: 30
  nested_if: 5
  delta: 5
red_allowlist: []             # globs; empty until a human says otherwise
testable:
  include: ["internal/"]
  exclude: ["internal/interface/"]
io_imports: ["database/sql", "net/http", "os"]
extra_hunters: []
e2e:
  catalog_root: "internal/e2e"
cover:
  io_floor: 80
  baseline_path: ".cqb/cover-baseline.json"
```

**Tunable:** ceilings, allowlist, testable globs, catalog root, I/O floor,
baseline path, extra hunters, operator language, prefix(es).

**Not tunable:** constitution (table above).

---

## Nested modules (monorepo)

Git paths are often `services/billing/internal/...` while the module’s own
`globs.txt` and tests say `internal/...`. Set:

```yaml
prefix: "services/billing"
```

Matching uses the git path **or** the path with that prefix stripped.
`testable.include: internal/` means `module_rel == "internal"` or
`module_rel` starts with `internal/`. Bundle `file` fields stay
**git-relative** (`services/billing/...`) so they still match `git diff`.

Overlapping prefixes: list **most-specific first**.

A diff that does not touch any configured prefix → whole bundle `skip`
(`diff outside configured prefix`), exit 0.

---

## Opt-in hook

```bash
git config core.hooksPath .cqb/hooks
CQB=1 git push          # runs: cqb run --mode push
git push                # hook no-ops unless CQB is set
```

Never export `CQB=1` in your shell rc. That would make every push wait on
the gate and surprise the rest of the team.

---

## `/cqb` review

Operator-facing language defaults to **pt-BR**. Do not paste raw JSON into
chat.

1. **Gather** — unified diff. If it touches `prefix`, start `cqb run` in the
   background on `.quality/last.json`.
2. **Layers** (parallel) — unused branches / ignored errors; edges; verification
   wait for a bundle with `has_red`; consumer rules overlay (they win on
   style, they cannot turn a red slot green).
3. **Triage** — `patch` / `defer` / `decision_needed` / `rejected`.
4. **Present** — prose of colors first, then the review list.

Document-only diffs use editorial lenses in the same slash (no fake Go
hunters on markdown).

---

## Architecture

```
cqb (Go) ──embed──► engine/*.py + templates/
                │
                ├─ cqb init     copy into consumer .cqb/
                ├─ cqb run      python3 .cqb/engine/orchestrator.py
                └─ cqb upgrade  replace vendored engine from this binary
```

| Piece | Where | Role |
|---|---|---|
| CLI | `cmd/cqb`, `internal/cli` | init / run / upgrade / setup-copy / render-reader |
| Engine | `engine/orchestrator.py`, `engine/cqb/*.py` | diff, slots, hunters |
| Templates | `templates/` | default yaml, hook, Cursor skills |
| Host tools | `PATH` | gofmt, go, python3, docker (e2e), golangci-lint, gremlins |

The consumer is the source of domain truth. `cqb setup-copy` writes kit
skills only if the destination **does not exist**; it will not overwrite
`.cursor/skills` you already maintain.

---

## This repository

Public on purpose. No employer source, product paths, tickets, or credentials.
Tests use invented `internal/billing` and `services/billing` fixtures
(`github.com/example/billingapp`). See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
go test ./...
python3 -m unittest discover -s engine/tests
```
