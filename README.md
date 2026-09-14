# CQB

[Português (Brasil)](README.pt-BR.md)

Local **quality gate** and **code-review ritual** for Go modules.

CQB measures **new code on the git diff**, not the whole tree. It writes a
JSON bundle (`.quality/last.json`) that a human or a Cursor slash (`/cqb`)
can read. Yellow never blocks git. **Red is an allowlist you name later**
(empty on first install): paths **on** that list may fail the push; paths
**off** it stay yellow. The consuming repo keeps its own skills, path-scoped
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
cd /path/to/your/git/root     # not necessarily the nested Go module; see prefix
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
**`prefix` and `red_allowlist` are still empty** — you (or `/cqb-setup` after
you say yes) fill those in. See [Manual configuration](#manual-configuration).

### Optional first-run interview

In Cursor, `/cqb-setup` installs the CLI if needed, runs `cqb init`, then
**proposes allowlist candidates** from `.cqb/scan.json` (e2e suite dirs, not
“every package that has a test”). It **HALTs** and asks yes/no per candidate.
No confirmation → `red_allowlist` stays `[]`. The agent **cannot** reliably
know which folder is the product’s hard recorte; it can only guess from the
scan. Skipping setup still leaves a working, non-blocking gate.

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

## Red allowlist (not an ignore list)

`red_allowlist` is the set of globs where hunters, quick-test, and cover are
**allowed to be red** (exit 1). It is **not** a skip list.

| Diff file | `red_allowlist` | Those checks | `cqb run` from them |
|---|---|---|---|
| any | `[]` (default after init) | yellow or cover `skip` | **0** (cannot fail git) |
| matches a glob, e.g. `internal/billing/**` | non-empty | **red** if they fire | **1** |
| does not match any glob | non-empty | yellow | **0** |

```yaml
# First install — hunters/cover cannot fail git:
red_allowlist: []

# Human named a recorte — only these paths can fail the push for
# missing TestFoo+Foo(, blind t.Fatal("x"), cover invocation, etc.:
red_allowlist:
  - "internal/billing/**"
  - "internal/application/services/*invoice*"
```

What is **not** gated by the allowlist (can still be red with an empty list):

- **lint** — `gofmt` / `go vet` / `go build` on the diff
- **e2e** — implied suite failed, or `globs.txt` catalog is broken

Empty list ≠ “ignore the repo”. Empty list = “do not treat any path as a
hard recorte yet.” Inferring `internal/` automatically would do the opposite:
the first run on a large module would go red everywhere. That is why setup
**HALTs**.

---

## Manual configuration

`cqb init` never asks questions. After it, **you** edit `cqb.yaml` (or confirm
candidates in `/cqb-setup`). Nothing below is filled in from your domain.

Work in the **git root** (where you ran `cqb init`). Paths in the bundle are
git-relative. Globs may be written **relative to `prefix`**.

### 1. `prefix` / `prefixes` — required in a monorepo

If the Go module is not the git root — git shows
`services/billing/internal/foo.go` but tests and `globs.txt` say
`internal/foo.go` — set the module directory:

```yaml
prefix: "services/billing"
```

Several modules: most-specific first.

```yaml
prefixes:
  - "services/billing/cmd/worker"
  - "services/billing"
```

Leave `prefix: ""` only when the git root **is** the module (`internal/` on
disk is `internal/` in `git diff`).

Without this, `testable: [internal/]` will not see
`services/billing/internal/...`, and e2e `globs.txt` lines like
`internal/db/queries/faturas_queries.sql` look “missing” at the repo root.

Check: `cqb run --mode file-list --files services/billing/internal/billing/normalize.go`
must **not** print `diff outside configured prefix` if that file is the work
you care about.

### 2. `red_allowlist` — leave empty until you mean it

Do not paste `internal/` “to be safe”. That makes **every** new helper under
`internal/` able to fail git.

How to choose a glob:

1. Look at `.cqb/scan.json` → `e2e_suites` (directories that already have
   `globs.txt`). Those are **candidates**, not a decision.
2. Open that suite’s `globs.txt`. The lines are what *implies e2e*, not
   automatically what should be red.
3. Pick the **smallest** set of paths you are willing to block a push for
   (the package you are actively hardening). Example:
   `internal/application/services/*invoice*`.
4. Write those strings in `red_allowlist`. With `prefix` set, you may omit
   `services/billing/`.
5. Run `cqb run` on a known-bad diff (new func, no `Foo(`). Confirm the
   slot is **red** only on that path, and **yellow** on a sibling outside
   the glob.

`/cqb-setup` will suggest candidates from the scan (typically e2e dirs /
`internal/billing/`-shaped paths). It **must ask yes/no**. It must **not**
write the list because “this package has tests”. If the suggestion is wrong,
answer no; the yaml stays `[]`.

To **clear** a recorte later: set `red_allowlist: []` again. Cover becomes
`skip`; hunters go back to yellow.

### 3. `testable.include` / `exclude` — who gets a quick-test hunter

Defaults: include `internal/`, exclude `internal/interface/` (HTTP adapters
often have no `TestHandleFoo` that calls `HandleFoo(`).

These globs decide **whether** the quick-test hunter runs (yellow or red).
They do **not** by themselves fail git. Red still needs the allowlist.

Adjust if your domain code does not live under `internal/`, or if you want
handlers included. Directory form `internal/` means that directory and
everything under it (after `prefix` is stripped).

### 4. `e2e.catalog_root` and `globs.txt`

Init may already set `catalog_root` to `services/billing/internal/e2e` when
that tree is unique. If suites live elsewhere, set it yourself (git-relative).

Each suite is a directory with `globs.txt`:

```
services/billing/internal/e2e/invoices/globs.txt
```

```
# comments and blank lines ok
internal/application/services/*invoice*
internal/db/queries/faturas_queries.sql
```

- Lines with `*` / `?` are fnmatch against the diff (git path **or**
  prefix-stripped).
- Lines **without** wildcards must exist as files: first
  `{git root}/{prefix}/{line}`, then `{git root}/{line}`. A missing SQL
  file marks the **catalog red** (broken), not “suite skipped”.
- If the diff matches any line, CQB runs
  `go test -tags e2e -count=1 -timeout 8m ./<suite-dir>` from the **git root**.
- Implied suite + no `docker` on `PATH` → e2e `unavailable`. `CQB=1 git push`
  then exits 1.

You must create `globs.txt` yourself; init does not invent suites.

### 5. `cover.baseline_path` and `io_floor`

Cover **does not run** while `red_allowlist` is empty (`skip`).

When the list is non-empty and the diff touches those production `.go` files,
CQB writes `.cqb/work/cover.out` (gitignored) and compares:

- I/O (file imports `database/sql`, `net/http`, or `os` by default): percent
  below `io_floor` (80) → red
- Pure helper: no `Foo(` in tests → red
- File in the JSON baseline whose percent **drops** → red

Default file: `.cqb/cover-baseline.json`. If you already maintain a baseline
elsewhere, point `cover.baseline_path` at it (git-relative). **Never** let
the hook rewrite that file. Raising the recorded percent is a separate,
intentional command in *your* repo (CQB does not rewrite the baseline on
`cqb run`).

Extend `io_imports` if your I/O is `pgx` / a house package, not `database/sql`.

### 6. `complexity` ceilings

Defaults are golangci-lint **tool** defaults: 30 / 30 / 5, delta 5. They are
**yellow only**, never red.

HTTP handlers with a chain of `if err != nil { return }` often exceed 30
cyclomatic while remaining readable. `/cqb-setup` may **suggest** raising
`cyclomatic` (e.g. 35). It will not lower them to “10” from blog posts, and
it will not change yaml unless you agree.

You edit:

```yaml
complexity:
  cognitive: 30
  cyclomatic: 35
  nested_if: 5
  delta: 5
```

### 7. Optional: extra hunters, operator language, hook

```yaml
extra_hunters: ["placebo_validator"]   # off unless listed
operator_language: "pt-BR"             # /cqb prose; hunter ids stay English
```

Hook (never done by init or setup unless you ask):

```bash
git config core.hooksPath .cqb/hooks
CQB=1 git push
```

Do not export `CQB=1` in bashrc.

### 8. What you do **not** configure

These keys are ignored if present: `yellow_blocks`, `whole_module`,
`always_on_hook`, `legacy_absolute_red`. They appear on the bundle as
`ignored_keys`. You cannot make yellow fail git via yaml.

---

## Constitution (not YAML)

| Rule | Meaning |
|---|---|
| Diff only | Never walk the whole module “to be sure”. |
| New vs legacy complexity | **New** functions: absolute cognitive / cyclomatic / nested-if. **Legacy**: delta only, and only yellow. |
| Yellow never fails git | Complexity over ceiling, hunters outside the allowlist, surviving mutants → exit **0**. |
| Empty red allowlist | Until a human names a scope (`/cqb-setup` HALT). Cover and content hunters stay non-red. |
| Agent ≠ git exit | `/cqb` reads the bundle; it does not decide `git push`. |
| Hook is opt-in | `git config core.hooksPath .cqb/hooks` then `CQB=1 git push`. Init never attaches it. |

---

## Colors and process exit

Each **slot** is one of: `green`, `yellow`, `red`, `skip`, `unavailable`.

| Color | Git | Meaning |
|---|---|---|
| green | 0 | Ran and passed. |
| yellow | 0 | Signal for review, not a push failure. |
| red | **1** | Allowlist (or hygiene / failed e2e). |
| skip | 0 | Out of scope. **Not a pass.** |
| unavailable | 0 normally | Tool missing (Docker, gremlins). **Not a pass.** Flagged push is stricter. |

`cqb run` exits **1** when `has_red` is true.

**Also exit 1:** `--mode push` when e2e is `unavailable` **and** a suite is
implied (typically Docker missing). Daily `cqb run` keeps `unavailable` and
exits 0.

---

## Slots

The bundle is `.quality/last.json` (`schema_version: 1`).

### `lint`

`gofmt -l`, `go vet`, `go build` on packages of the scoped `.go` files.
Any failure is **red** (not gated on the allowlist). golangci-lint is
installed for humans/`/cqb`; it is not a red slot in v0.1.

### `complexity`

- new function: cognitive **30**, cyclomatic **30**, nested-if **5** → yellow if over
- legacy: delta cognitive **5** → yellow if over; never red

### `test` / quick-test hunters

For **new** symbols on `testable.include` (minus `exclude`): `TestFoo` **and**
`Foo(` in package tests. HTTP handlers (`http.ResponseWriter`) are exempt.

- outside the allowlist → **yellow**
- on the allowlist → **red**

### `hunters` (content)

On `*_test.go` in the diff (red only if the file matches the allowlist):

| Hunter | What it flags |
|---|---|
| `blind_assert` | `t.Fatal("short")` / `t.Error("…")` with no `%` format verb |
| `compound_assert` | two asserts on one line, or `&&` inside an assert |
| `non_deterministic` | `time.Now` or `math/rand` in a test |
| `order_dependent` | package-level state mutated in tests without `t.Cleanup` |
| `duplicate_observable` | the same fatal/error literal on two lines |
| `missing_boundary` | **new production** comparison to a numeric / `len` literal that never appears in package tests. Indexes, HTTP status, `time.Duration` exempt. A test **name** without `Empty`/`Zero` is not enough. |
| `placebo_validator` | opt-in: `validator.Struct` without asserting the error |

Findings are unique on `(hunter, file, line, message)`.

### `e2e`

See [manual configuration §4](#4-e2ecatalog_root-and-globstxt). Pass → green.
Failed test → red. No glob match → skip. Docker missing while implied →
unavailable.

### `cover`

See [manual configuration §5](#5-coverbaseline_path-and-io_floor). Empty
allowlist → skip. Hook never rewrites the baseline.

### `mutation`

Gremlins when a **new** symbol has both `TestFoo` and `Foo(`. Missing binary →
unavailable. Survivors are **yellow**. No invoking test → skip.

---

## `cqb.yaml` (full skeleton)

```yaml
kit_version: "0.1.0"
prefix: ""                    # set in a monorepo, e.g. services/billing
operator_language: "pt-BR"
complexity:
  cognitive: 30
  cyclomatic: 30
  nested_if: 5
  delta: 5
red_allowlist: []             # empty = hunters/cover cannot be red
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

**Tunable:** everything in that file except constitution.
**Not tunable:** yellow-never-fails-git, empty-until-human allowlist, opt-in hook.

---

## `/cqb` review

Operator-facing language defaults to **pt-BR**. Do not paste raw JSON into chat.

1. **Gather** — unified diff. If it touches `prefix`, start `cqb run` in the
   background on `.quality/last.json`.
2. **Layers** (parallel) — unused branches / ignored errors; edges; wait for a
   bundle with `has_red`; consumer rules overlay (they win on style, they
   cannot turn a red slot green).
3. **Triage** — `patch` / `defer` / `decision_needed` / `rejected`.
4. **Present** — prose of colors first, then the review list.

Document-only diffs use editorial lenses in the same slash.

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

`cqb setup-copy` writes kit skills only if the destination **does not exist**.

---

## This repository

Public on purpose. No employer source, product paths, tickets, or credentials.
Tests use invented `internal/billing` and `services/billing` fixtures
(`github.com/example/billingapp`). See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
go test ./...
python3 -m unittest discover -s engine/tests
```
