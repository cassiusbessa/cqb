# CQB

[Português (Brasil)](README.pt-BR.md)

CQB is a **local quality gate** for Go. It was built for the **agentic
Cursor** flow: in a session you ask for review, the agent runs the gate,
reads the report, and tells you what to fix.

The terminal (`cqb run`) and the git hook exist. The simplest path — and
the one the kit was made for — is the Cursor chat.

Needs Go 1.22+, `python3`, `git`, and `gofmt`/`go`.

---

## Quick start: a Cursor session

In the Cursor chat, a line starting with `/` starts an agent flow. CQB
ships two.

### First time in the repo: `/cqb-setup`

Open chat at the **git root** and type `/cqb-setup`. The agent installs
the CLI if needed, runs `cqb init`, and **asks** whether a suggested
folder should join the **strict-paths list** (next section). Without your
“yes”, the list stays empty: the gate keeps warning (yellow) and **does
not** block `git push` over a weak unit test.

The agent **does not know** your product and **does not pick** what
should block git.

### On every review: `/cqb`

Type `/cqb`. The agent compares your branch to the base (`main` or
`master`, usually), **runs the gate**, waits for the report
(`.quality/last.json`), and writes in Portuguese what to fix.

You do not need to run `cqb run` first. Do not paste the JSON into chat.

If git has both `main` **and** `master` and the branch has no *upstream*,
the agent **stops and asks** which ref to compare — it does not guess.

Kit skills are copied only if the destination file **does not already
exist** under your `.cursor/`. Your own domain rules still win on those
paths.

---

## Colors, exit 1, and what that does

The gate looks only at what changed in git. Each check gets a color on
the report. `/cqb` reads those colors. `cqb run` also becomes a process
exit code:

| Color | `cqb run` | Meaning |
|---|---|---|
| green | exit 0 | Ran and passed. |
| yellow | exit 0 | Note for review. **Never** makes the process exit 1. |
| red | **exit 1** | Blocker. |
| skip | exit 0 | Out of scope for this diff. Not a pass. |
| unavailable | exit 0 | A tool was missing (Docker, gremlins). Not a pass. |

**Exit 1** does two things — no extra leap:

1. `/cqb` treats the item as a blocker (“fix this now”);
2. if you pushed with the hook on (`CQB=1 git push`), **the push stops**.

Yellow still shows up in `/cqb` as a warning; git continues. Missing
Docker while a journey suite *should* have run stays `unavailable` and
**does not** become red by itself. A journey that ran and failed an
assert stays red.

On first install the **strict-paths list** (below) is empty: a missing
unit test **does not** exit 1. Broken `gofmt` / `go vet` / `go build`
**do** exit 1 even with an empty list.

---

## Strict paths (`strict_paths` in `cqb.yaml`)

This is **not** a skip / ignore list. Paths off it are still checked;
the warning just does not exit 1.

You **name the folders where a weak unit test or low coverage will exit
1** — so `/cqb` flags a blocker and, with `CQB=1`, the push stops. It is
not the set of everything you want tested.

```yaml
# in cqb.yaml
strict_paths: []                 # default: test/coverage warnings do not exit 1

strict_paths:
  - "internal/billing/**"        # in this folder, a weak test / low cover WILL exit 1
```

A **glob** is a path pattern. `internal/billing/**` = everything under
that folder (**including new files**). `*invoice*` = a path that contains
`invoice`. You do **not** list files one by one. Start empty; add only
the recorte the team wants as a blocker.

Do not paste `internal/` “to be safe”: then **every** new helper under
`internal/` will exit 1.

Still exit 1 **with an empty list**: hygiene (`gofmt`/`vet`/`build`) and
a journey test that **ran** and failed.

Putting a glob here **does not** start a journey test. That is a
different file, later, only if you have an e2e suite.

---

## Prefix (`prefix` in `cqb.yaml`)

If git shows `services/billing/internal/foo.go` but the Go module (and
the tests) say `internal/foo.go`, the git root is **not** the module. Set
the prefix **in `cqb.yaml`**:

```yaml
prefix: "services/billing"
```

Without that, the default `internal/` used by strict paths and quick
tests does not see `services/billing/internal/...`.

Several modules: most-specific path first, under `prefixes`.

Check with:

```bash
cqb run --mode file-list --files services/billing/internal/billing/normalize.go
```

It must not say the diff is outside the prefix, if that is the code you care about.

---

## What `init` put on disk

`/cqb-setup` already ran this. In a terminal: `cqb init` at the git root.

```
your-repo/
  cqb.yaml              *your* settings (prefix, strict paths, ceilings…).
                        init creates it only if it is missing
  .cqb/
    engine/             copy of the (Python) engine that `cqb run` uses
    templates/          skill and hook templates
    hooks/pre-push      hook script (only works with CQB=1)
    scan.json           inventory at init time (not configuration)
    work/               scratch; gitignored
  .quality/             reports (`last.json`); gitignored
  .gitignore            `# cqb begin` … `# cqb end` block
```

Git **should** track `cqb.yaml`, `.cqb/engine`, `.cqb/hooks`, and
`.cqb/templates`. Init **does not** ignore those. It ignores runtime junk:
`.quality/`, `scan.json`, `work/`, `*.coverprofile`.

`scan.json` is a snapshot. `/cqb-setup` uses it to *suggest* folders for
the strict-paths list; you decide.

**When init records journey tests.** It looks for directories that
already have e2e suites. **Exactly one** (e.g.
`services/billing/internal/e2e`) → a **new** `cqb.yaml` sets
`e2e.catalog_root` to that path, only so the engine knows **where to look
for suites**. Zero, or two or more → it does not pick for you. That
**does not** fill strict paths or `prefix`.

**Hook.** If `core.hooksPath` was empty in this repository, init points
**local** git at `.cqb/hooks`. If you already had another value (husky,
…), it does not overwrite. Either way the hook **only runs CQB** with:

```bash
CQB=1 git push          # runs `cqb run --mode push`; exit 1 cancels the push
git push                # without CQB, the push proceeds
```

Do not export `CQB=1` in bashrc: every push would wait on the gate.
Yaml **cannot** turn the hook on by itself.

---

## What CQB checks

Only the **diff** (and, with `prefix`, only under that directory). It
never walks the whole module.

**Hygiene (lint)** — `gofmt`, `go vet`, `go build` on packages of the
`.go` files that changed. Failure → red, **even with empty strict paths**.

**Complexity** — **new** functions over the ceilings (cognitive 30,
cyclomatic 30, nested-if 5) are **yellow**. Old functions: only the
*increase* (delta 5) is yellow. Never red. HTTP handlers with many
`if err != nil` often want `cyclomatic` 35; `/cqb-setup` may *suggest*
that and **will not** write yaml unless you agree.

**Quick test** — for a **new** function `Foo` under a “testable” path
(default `internal/`, excluding `internal/interface/`): is there a
`TestFoo` **and** does the test body **call** `Foo(`? Missing test or
missing call → a warning. This is **not** coverage percent and **not**
the journey `go test`. HTTP handlers (`http.ResponseWriter`) are skipped.
Empty strict paths → **yellow**; path on the list → **red** (exit 1).

**Test-file checks (hunters)** — fragile patterns, for example:

- `t.Fatal("failed")` with no observed vs expected value
- two asserts on one line
- `time.Now` / `rand` in a test
- a **new production** comparison (`n > 10`, `len(x) == 0`) whose number
  never appears in the package tests

Empty list → yellow. On the list → red (exit 1).

**Journey tests (e2e)** — if the diff overlaps a suite’s recorte, CQB
runs `go test -tags e2e` in that directory (usually needs Docker). Pass →
green. Failed assert → red (exit 1). No Docker while a suite was
requested → `unavailable` (does not exit 1). This is **not** strict
paths: missing Docker does **not** fail git for a missing `TestFoo`. How
the suite recorte is declared: next section.

**Coverage** — percent of code hit by unit tests, on packages of
production `.go` in the diff. **Runs even when strict paths are empty**
(then the warning is yellow). It exits 1 only on paths that match the
list. No production `.go` in the diff → `skip`. CQB **does not** rewrite
the baseline file on `cqb run`.

**Mutation** — extra tool (`gremlins`), **not** the same slot as quick
test. It only tries to mutate if the new function **already has**
`TestFoo` that calls `Foo(`. Without that call, mutation is `skip`; the
missing test is the quick-test slot (yellow or red from strict paths).
No `gremlins` on `PATH` → `unavailable`, never red. A surviving mutant →
**yellow**, never red in v0.1.

---

## Journey tests: one folder pattern per suite, not an inventory

You **do not need** this for `/cqb` to work. It only matters if the team
already has (or will add) `go test -tags e2e`.

Two **different** places, two questions:

| Where | Question |
|---|---|
| `strict_paths` in `cqb.yaml` | On this path, does a unit-test / coverage warning **exit 1**? |
| `globs.txt` inside the suite directory | Should we **run** this journey if the diff matches? |

Putting a glob only in `cqb.yaml` **does not** start e2e. The strings can
match; the questions do not.

Each suite is a directory under `e2e.catalog_root` (set at init, or you
fill it). That directory has a `globs.txt`. Write **one folder pattern**,
not every new file:

```
# services/billing/internal/e2e/invoices/globs.txt
internal/billing/**
```

A new `.go` file or a new folder under `internal/billing/` already
matches. You **do not** edit `globs.txt` on every implementation. Touch
it when a **new suite** appears or production code lives in a
**different tree**.

A line **with** `*` or `**` matches the diff (git path or with `prefix`
stripped). A line **without** `*` pins a file that must exist
(`prefix/line` or at repo root); missing → catalog **red**. Prefer the
folder pattern.

Init **does not** invent suites. You (or the team) create the directory
and `globs.txt`.

---

## Coverage: baseline and I/O

Default baseline: `.cqb/cover-baseline.json`. If you already keep another
JSON, set `cover.baseline_path` in `cqb.yaml`. Imports that count as I/O
(80% floor when the path is on strict paths): `database/sql`, `net/http`,
`os` — extend via `io_imports`.

---

## In a terminal (besides Cursor)

Daily work can be `/cqb` only. These commands are for a manual install,
debugging, and the hook.

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cd /path/to/your/repo          # git root
cqb init
cqb run
```

`cqb run` compares the files on disk to `HEAD` (including new untracked
files).

Do not point daily runs at `@latest`. Pin a tag; when you want to update:

```bash
go install github.com/cassiusbessa/cqb/cmd/cqb@v0.1.0
cqb upgrade
```

`upgrade` replaces the engine copy under `.cqb/` with the one inside
**this** binary.

`--mode` picks **which diff** (never the whole tree):

| Command | What is in scope |
|---|---|
| `cqb run` | Changed or new since `HEAD` (includes untracked). Daily terminal use. |
| `cqb run --mode staged` | Only `git add` (the next commit). |
| `cqb run --mode push` | Diff vs upstream (`git push`). What the hook calls. |
| `cqb run --mode review` | Commits since merge-base of the base branch **plus** the working tree. What `/cqb` calls, unless you asked only for the working tree. |
| `cqb run --mode file-list --files a.go,b.go` | Only those paths. Handy to debug one file. |

`--mode review` picks the base as: tracking upstream if it exists;
otherwise `main` **or** `master` if only one of those exists. If both
exist (or neither), the command **stops and asks** for `--base <ref>`.
`/cqb` asks you the same question.

`--output` (default `.quality/last.json`) is only where the report is written.

---

## What yaml cannot undo

`cqb.yaml` tunes ceilings, prefix, strict paths, e2e catalog. It
**cannot**:

- scan the whole module “to be sure”
- make yellow exit 1
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
Gremlins only feeds the mutation slot, and even then it does not exit 1.

---

## Glossary

| Term | Meaning here |
|---|---|
| Report | JSON file `.quality/last.json` with a color per check. |
| Slot | One section of that report (lint, test, e2e, cover, …). |
| Strict paths (`strict_paths`) | Globs where a test/coverage warning **exits 1** (alerts `/cqb` and, with `CQB=1`, stops the push). Not a skip / ignore list. |
| Glob | Path pattern (`internal/billing/**`, `*invoice*`). Covers a new matching file; not an inventory. |
| Prefix (`prefix`) | Go module directory, **in `cqb.yaml`**, when it is not the git root. |
| Quick test | “Does new `Foo` have `TestFoo` that calls `Foo(`?” Not e2e, not %. |
| Hunter | Automatic check on a `*_test.go` or a new production line. |
| Coverage | Percent of code hit by unit tests (`go test -cover`). |
| E2e | Journey test (`go test -tags e2e`), usually with Docker. |
| `globs.txt` | Pattern that **triggers** the journey; not the strict-paths list. |
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
