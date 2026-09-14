# CQB

[Português (Brasil)](README.pt-BR.md)

CQB is a **local quality gate** for Go. It looks only at what you changed
in git, writes a report to `.quality/last.json`, and in Cursor `/cqb`
**runs the gate and explains that report**.

On first install it **does not block git push** for a weak unit test or
low coverage. That starts only after you name folders on the **strict
paths** list (explained below).

Needs Go 1.22+, `python3`, `git`, and `gofmt`/`go`.

---

## Quick start

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cd /path/to/your/repo          # git root
cqb init
cqb run
```

`cqb run` compares the files on disk to `HEAD` (including new untracked
files). It format-checks and builds the Go that changed. If those
changes overlap a journey-test (e2e) suite, it may run those tests —
they usually need Docker.

- Exit **0** most of the time: the report is for you (and `/cqb`) to read.
  Yellow never changes this exit code.
- Exit **1** only when some check is **red**: usually `gofmt`, `go vet`,
  `go build`, or e2e that ran and failed. A missing unit test **does not**
  fail git while strict paths are empty.

Do not point daily runs at `@latest`. Pin a tag; when you want to update:

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cqb upgrade
```

`upgrade` replaces the engine copy under `.cqb/` with the one inside
**this** binary.

---

## What `init` put on disk

```
your-repo/
  cqb.yaml              *your* settings (prefix, strict paths, ceilings…).
                        init creates it only if it is missing
  .cqb/
    engine/             copy of the (Python) engine that `cqb run` uses
    templates/          skill and hook templates
    hooks/pre-push      hook script (only works with CQB=1)
    scan.json           inventory (how many tests, e2e dirs)
    work/               scratch; gitignored
  .quality/             reports (`last.json`); gitignored
  .gitignore            `# cqb begin` … `# cqb end` block
```

Git **should** track `cqb.yaml`, `.cqb/engine`, `.cqb/hooks`, and
`.cqb/templates`. Init **does not** ignore those. It ignores runtime junk:
`.quality/`, `scan.json`, `work/`, `*.coverprofile`.

`scan.json` is not configuration. It is a snapshot at init time.
`/cqb-setup` uses it to *suggest* folders; you decide.

**When does init set `e2e.catalog_root`?** It looks for directories that
already have journey tests. **Exactly one** (e.g.
`services/billing/internal/e2e`) → a **new** `cqb.yaml` records that path,
only so CQB knows where to look for suites. Zero, or two or more → it
leaves the field alone; it does not pick for you. That **does not** fill
strict paths or `prefix`.

If `core.hooksPath` was empty in this repository, init points local git
at `.cqb/hooks`. If you already had another value (husky, …), it does
not overwrite. Either way the hook **only runs CQB** when that push has
`CQB=1`.

---

## Colors in the report

Each section (lint, tests, e2e, coverage, …) gets a color:

| Color | Git | Meaning |
|---|---|---|
| green | continues | Ran and passed. |
| yellow | continues | Note for review. **Never** makes `cqb run` exit 1. |
| red | **stops** (`cqb run` exits 1) | CQB treats this as a blocker. |
| skip | continues | Out of scope for this diff. Not a pass. |
| unavailable | continues | A tool was missing (Docker, gremlins). Not a pass. |

`cqb run` exits 1 when **any** section is red — in the terminal, in
`--mode push`, and in the hook with `CQB=1`. Missing Docker while a
suite *should* have run stays `unavailable` and **does not** become red
by itself. E2e that ran and failed an assert, or a broken `globs.txt`,
stay red.

---

## What CQB checks

Only the **diff** (and, if you set `prefix` in `cqb.yaml`, only under
that directory). It never walks the whole module.

**Hygiene (lint)** — `gofmt`, `go vet`, `go build` on packages of the
`.go` files that changed. Failure → red, **even with empty strict paths**.

**Complexity** — **new** functions over the ceilings (cognitive 30,
cyclomatic 30, nested-if 5) are **yellow**. Old functions: only the
*increase* (delta 5) is yellow. Never red.

**Quick test** — for a **new** function `Foo` under a “testable” path
(default `internal/`, excluding `internal/interface/`): is there a
`TestFoo` **and** does the test body **call** `Foo(`? Missing test or
missing call → a warning. This is **not** coverage percent and **not**
the e2e `go test`. HTTP handlers (`http.ResponseWriter`) are skipped.
Empty strict paths → **yellow**; path on the list → **red**.

**Test-file checks (hunters)** — fragile patterns, for example:

- `t.Fatal("failed")` with no observed vs expected value
- two asserts on one line
- `time.Now` / `rand` in a test
- a **new production** comparison (`n > 10`, `len(x) == 0`) whose number
  never appears in the package tests

Empty list → yellow. On the list → red.

**E2e** — if the diff matches a suite’s `globs.txt`, CQB runs
`go test -tags e2e` in that directory. Pass → green. Failed assert → red.
No Docker while a suite was requested → `unavailable`. This is **not**
strict paths: implying Docker does not fail git for a missing `TestFoo`.

**Coverage** — percent of code hit by unit tests, on packages of
production `.go` in the diff. **Runs even when strict paths are empty**
(then the warning is yellow). It may turn red — and stop git — only on
paths that match the list. No production `.go` in the diff → `skip`.
CQB **does not** rewrite the baseline file on `cqb run`.

**Mutation** — optional (gremlins), only if the new function already has
an invoking test. Surviving mutant → yellow, never red in v0.1.

---

## Strict paths (`strict_paths`)

In `cqb.yaml` the key is `strict_paths` (the old name `red_allowlist` is
still read). It is not “permission” and **not** a skip / ignore list.

You **name the folders where a warning may stop the push**. It is not
the set of everything you want tested. It is not an exclusion list:
paths off the list are still checked; they just do not go red.

```yaml
# in cqb.yaml
strict_paths: []                 # default: test/coverage warnings do not stop git

strict_paths:
  - "internal/billing/**"        # in this folder, a weak test / low cover MAY exit 1
```

A **glob** is a path pattern. `internal/billing/**` = everything under
that folder. `*invoice*` = a path that contains `invoice`. You do **not**
have to list the whole module. Start empty; add only the recorte the
team wants as a blocker.

Do not paste `internal/` “to be safe”: then **every** new helper under
`internal/` can fail git.

Still red **with an empty list**: hygiene (`gofmt`/`vet`/`build`) and e2e
that ran and failed (or a broken `globs.txt` catalog).

**Do not confuse this with e2e `globs.txt`.** That file answers “should
we **run** this journey suite?” Strict paths answer “on this path, may a
unit-test / coverage warning **block the push**?” The strings can match;
the questions do not.

---

## `cqb run` modes

CQB never scans the whole tree. `--mode` picks **which diff**.

| Command | What is in scope |
|---|---|
| `cqb run` | Changed or new since `HEAD` (includes untracked). Daily terminal use. |
| `cqb run --mode staged` | Only `git add` (the next commit). |
| `cqb run --mode push` | Diff vs upstream (`git push`). What the hook calls. |
| `cqb run --mode review` | Commits since merge-base of the base branch **plus** the working tree. What `/cqb` calls. |
| `cqb run --mode file-list --files a.go,b.go` | Only those paths. Handy to debug one file. |

`--mode review` picks the base as: tracking upstream if it exists;
otherwise `main` **or** `master` if only one of those exists. If both
exist (or neither), the command **stops and asks** for `--base <ref>` —
it does not guess. `/cqb` asks you the same question.

`--output` (default `.quality/last.json`) is only where the report is written.

---

## Cursor commands

In the Cursor chat, a line starting with `/` starts an agent flow. CQB
ships two.

**`/cqb`** — code review. Picks the diff (`--mode review`, unless you
asked only for the working tree), **runs `cqb run`**, waits for
`.quality/last.json`, and writes in Portuguese what to fix. You do not
need to run the CLI first. Do not paste the JSON into chat.

**`/cqb-setup`** — guided first config. Installs the CLI if needed, runs
`cqb init`, reads `scan.json`, and **asks** whether a suggested folder
(usually one that already has an e2e suite) should join strict paths.
Without your “yes”, the list stays empty: the gate keeps warning (yellow)
and does not block push over unit tests. The agent **does not know** your
product and **does not pick** the folder that should block the push.

Kit skills are copied only if the destination file **does not already
exist** under your `.cursor/`. Your own domain rules still win on those
paths.

---

## The `cqb.yaml` file

All configuration lives **in this file** at the git root (or the path you
pass to `cqb run`). It is not an environment variable.

If git shows `services/billing/internal/foo.go` but tests and `globs.txt`
say `internal/foo.go`, the Go module is not the git root. Set the prefix
**in `cqb.yaml`**:

```yaml
prefix: "services/billing"
```

Without that, the default `internal/` does not see
`services/billing/internal/...`.

Several modules: most-specific path first, under `prefixes`.

Check with:

```bash
cqb run --mode file-list --files services/billing/internal/billing/normalize.go
```

It must not say the diff is outside the prefix, if that is the code you care about.

---

## E2e (`globs.txt`) and ceilings — when you get there

Each suite is a directory with a `globs.txt`. That file lists what
**should trigger** the suite if it appears in the diff — not what to
skip. Example `services/billing/internal/e2e/invoices/globs.txt`:

```
internal/application/services/*invoice*
internal/db/queries/faturas_queries.sql
```

A line with `*` matches the diff (git path or with `prefix` stripped). A
line **without** `*` must exist as a file (`prefix/line` or at repo root).
Missing SQL → catalog **red**.

Init **does not** invent suites. You (or the team) write `globs.txt`.

Coverage baseline default: `.cqb/cover-baseline.json`. If you already
keep another JSON, set `cover.baseline_path` in `cqb.yaml`. Imports that
count as I/O (80% floor when the path is on strict paths):
`database/sql`, `net/http`, `os` — extend via `io_imports`.

Complexity ceilings are **yellow only**. HTTP handlers with many
`if err != nil` often want `cyclomatic` 35; `/cqb-setup` may *suggest*
that and **will not** write yaml unless you agree.

---

## Git hook

After `init`, if the repository had no `core.hooksPath`, local git
already points at `.cqb/hooks`. The script **does nothing** until:

```bash
CQB=1 git push          # runs `cqb run --mode push`
git push                # without CQB, the push proceeds
```

Do not export `CQB=1` in bashrc: every push would wait on the gate.
Yaml **cannot** turn the hook on by itself.

---

## What yaml cannot undo

`cqb.yaml` tunes ceilings, prefix, strict paths, e2e catalog. It
**cannot**:

- scan the whole module “to be sure”
- make yellow fail git
- require `CQB=1` on every teammate’s push
- paint test/coverage red off the strict-paths list

Keys such as `yellow_blocks` are ignored (`ignored_keys` on the report).
That is intentional: the team does not freeze git on a complexity ceiling.

---

## Architecture

```
cqb (Go binary) ──embeds──► Python engine + templates
        cqb init     copies that into .cqb/ in your repo
        cqb run      python3 .cqb/engine/orchestrator.py
        cqb upgrade  replaces that copy from the current binary
```

`golangci-lint` and `gremlins` land on `PATH` at init; in v0.1 CQB’s red
lint slot is only gofmt/vet/build. golangci is for you or for `/cqb`.

---

## Glossary

| Term | Meaning here |
|---|---|
| Report | JSON file `.quality/last.json` with a color per check. |
| Slot | One section of that report (lint, test, e2e, cover, …). |
| Strict paths (`strict_paths`) | Globs where a test/coverage warning **may** turn red and stop git. Not an ignore list. Old yaml `red_allowlist` is the same field. |
| Glob | Path pattern (`internal/billing/**`, `*invoice*`). |
| Prefix (`prefix`) | Go module directory, **in `cqb.yaml`**, when it is not the git root. |
| Quick test | “Does new `Foo` have `TestFoo` that calls `Foo(`?” Not e2e, not %. |
| Hunter | Automatic check on a `*_test.go` or a new production line. |
| Coverage | Percent of code hit by unit tests (`go test -cover`). |
| E2e | Journey test (`go test -tags e2e`), usually with Docker. |
| `globs.txt` | List that **triggers** e2e, not what turns unit tests red. |
| Scan (`scan.json`) | Inventory written at init; not the strict-paths list. |
| Hook | Pre-push script; only analyzes when `CQB=1`. |
| Engine | Python under `.cqb/engine` that builds the report. |
| `/cqb`, `/cqb-setup` | Commands in the **Cursor chat**. `/cqb` runs the gate and interprets it. |
| Skip / unavailable | Did not run / tool missing. Do not read as green. |

---

## This repository

Public on purpose. Invented examples: `internal/billing`,
`services/billing` (`github.com/example/billingapp`). See
[CONTRIBUTING.md](CONTRIBUTING.md).

```bash
go test ./...
python3 -m unittest discover -s engine/tests
```
