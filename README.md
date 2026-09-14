# CQB

[Português (Brasil)](README.pt-BR.md)

CQB is a **local quality gate** for Go. It looks only at what you changed
in git, writes a **report** to `.quality/last.json`, and — if you want —
a Cursor chat command (`/cqb`) reads that report during review.

On first install it **does not block git push** for a weak unit test or
missing coverage. That starts only after you name specific paths (the
*allowlist* — explained below).

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

- Exit **0** most of the time: the report is for you (and `/cqb`) to read,
  not to freeze git.
- Exit **1** up front only if `gofmt`, `go vet`, or `go build` failed, or
  an e2e suite that *should* run broke. A missing unit test **does not**
  fail git at this stage.

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
  cqb.yaml              *your* settings (prefix, allowlist, ceilings…).
                        init creates it only if it is missing
  .cqb/
    engine/             copy of the (Python) engine that `cqb run` uses
    templates/          skill and hook templates
    hooks/pre-push      hook script; **not** attached to git yet
    scan.json           automatic inventory (how many tests, e2e dirs)
    work/               scratch (cover profiles); gitignored
  .quality/             reports (`last.json`); gitignored
  .gitignore            init appends a `# cqb begin` … `# cqb end` block
```

Git **should** track `cqb.yaml`, `.cqb/engine`, `.cqb/hooks`, and
`.cqb/templates`. Init **does not** ignore those. It ignores runtime junk:
`.quality/`, `scan.json`, `work/`, `*.coverprofile`.

`scan.json` is not configuration. It is a snapshot at init time (Go
module path, `*_test.go` density, directories that already have an e2e
`globs.txt`). `/cqb-setup` uses it to *suggest* folders; you decide.

Sometimes the scan finds **one** directory that already has journey
tests (e2e), for example `services/billing/internal/e2e`. A brand-new
`cqb.yaml` records that path as `e2e.catalog_root` — only so CQB knows
where to look for suites. That **does not** pick folders that block
push. Monorepo `prefix` and the allowlist **stay empty** until you fill
them in — see [When git root ≠ Go module](#when-git-root--go-module) and
[Allowlist](#allowlist-where-yellow-may-become-red).

---

## Colors in the report

Each section of the report (lint, tests, e2e, coverage, …) gets a color:

| Color | Git | Meaning |
|---|---|---|
| green | continues | Ran and passed. |
| yellow | continues | Note for review. **Never** makes `cqb run` exit 1. |
| red | **stops** (`cqb run` exits 1) | CQB treats this as a blocker. |
| skip | continues | Out of scope for this diff. Not a pass. |
| unavailable | continues day-to-day | A tool was missing (Docker, gremlins). Not a pass. |

`cqb run` exits 1 when **any** section is red.

Hook exception (optional, end of this guide): if you attach the hook and
run `CQB=1 git push`, e2e `unavailable` while a suite *should* have run
also exits 1 — usually Docker not on `PATH`.

---

## What CQB checks

Only the **diff** (and, if you set it, only under `prefix`). It never
walks the whole module “to be sure”.

**Hygiene (lint)** — `gofmt`, `go vet`, `go build` on packages of the
`.go` files that changed. Failure → red, **even with an empty allowlist**.

**Complexity** — **new** functions over the ceilings (cognitive 30,
cyclomatic 30, nested-if 5) are **yellow**. Old functions: only the
*increase* (delta 5) is yellow. Never red.

**Quick test** — for a **new** function `Foo` under a “testable” path
(default `internal/`, excluding `internal/interface/`): is there a
`TestFoo` **and** does the test body **call** `Foo(`? Missing name or
missing call → a warning. This is **not** coverage percent and **not**
the e2e `go test`. HTTP handlers (`http.ResponseWriter`) are skipped.
Empty allowlist → **yellow**; on the allowlist → **red**.

**Test-file checks (hunters)** — fragile patterns, for example:

- `t.Fatal("failed")` with no observed vs expected value
- two asserts on one line
- `time.Now` / `rand` in a test
- a **new production** comparison (`n > 10`, `len(x) == 0`) whose number
  never appears in the package tests

Empty allowlist → yellow. On the allowlist → red.

**E2e** — if the diff matches a suite’s `globs.txt`, CQB runs
`go test -tags e2e` in that directory. Pass → green. Failed assert → red.
No Docker while a suite was implied → `unavailable`. This is **not** the
allowlist: implying Docker does not fail git for a missing `TestFoo`.

**Coverage (cover)** — percent of statements hit by unit tests, **only**
when the allowlist is non-empty **and** the diff touches matching
production `.go`. Empty allowlist → this section is `skip` (does not even
run). A pure helper with no `Foo(` in tests → red. A file that talks to
the DB/HTTP below 80% → red. CQB **does not** rewrite the baseline file
on `cqb run`.

**Mutation** — optional (gremlins), only if the new function already has
an invoking test. Surviving mutant → yellow, never red in v0.1.

---

## Allowlist: where yellow may become red

`red_allowlist` in `cqb.yaml` is a list of **path patterns** (globs). It
is **not** a skip list / ignore list.

- Path **inside** a glob → quick test, hunters, and coverage **may** turn
  red and `cqb run` **may exit 1**.
- Path **outside**, or list `[]` → the same warnings stay yellow (or
  coverage `skip`) and **do not** fail git.

```yaml
red_allowlist: []          # default after init: none of that is red

red_allowlist:
  - "internal/billing/**"  # from now on, a weak test *in this folder* may block push
```

Do not paste `internal/` “to be safe”: then **every** new helper under
`internal/` can fail git.

The allowlist is **not** “coverage percent only”. Coverage is one
warning. On those paths, these can also turn red: a new function with no
test that calls it; `t.Fatal` that does not show got vs want; the other
hunters in the section above.

Still red **with an empty list**: hygiene (`gofmt`/`vet`/`build`) and e2e
that ran and failed (or a broken `globs.txt` catalog).

**Do not confuse this with e2e `globs.txt`.** That file only answers
“should we run the integration suite?” The allowlist answers “on this
path, may a unit-test warning block the push?” The strings can match;
the questions do not.

---

## `cqb run` modes

CQB never scans the whole tree. `--mode` picks **which diff**.

| Command | What is in scope |
|---|---|
| `cqb run` | Changed or new since `HEAD` (includes untracked). Daily driver. |
| `cqb run --mode staged` | Only `git add` (the next commit). |
| `cqb run --mode push` | Diff vs upstream (`git push`). What the hook calls. |
| `cqb run --mode file-list --files a.go,b.go` | Only those paths. Handy to debug one file. |

`--output` (default `.quality/last.json`) is only where the report is written.

---

## Cursor commands (optional)

In the Cursor chat, a line starting with `/` starts an agent flow. CQB
ships two. Neither replaces `cqb run` in the terminal.

**`/cqb-setup`** — guided first config. Installs the CLI if needed, runs
`cqb init`, reads `scan.json`, and **asks** whether a suggested folder
(usually one that already has an e2e suite) should join the allowlist.
Without your “yes”, the list stays empty: the gate keeps warning (yellow)
and does not block push over unit tests. The agent **does not know** your
product; it will not guess “the important folder”. If the suggestion is
wrong, say no.

**`/cqb`** — code review. Builds a unified diff, starts `cqb run` in the
background if the diff touches `prefix`, waits for `.quality/last.json`,
and writes what to fix. Do not paste the JSON into chat. Operator prose
defaults to pt-BR.

Kit skills are copied only if the destination file **does not already
exist** under your `.cursor/`. Your own domain rules still win on those
paths.

---

## When git root ≠ Go module

If git shows `services/billing/internal/foo.go` but tests and `globs.txt`
say `internal/foo.go`, tell CQB where the module lives:

```yaml
prefix: "services/billing"
```

Without that, the default `internal/` does not see
`services/billing/internal/...`.

Several modules: most-specific path first, under `prefixes`.

Check:  
`cqb run --mode file-list --files services/billing/internal/billing/normalize.go`  
must not say the diff is outside the prefix, if that is the code you care about.

---

## E2e (`globs.txt`) and coverage — when you get there

Each suite is a directory with `globs.txt`, for example
`services/billing/internal/e2e/invoices/globs.txt`:

```
internal/application/services/*invoice*
internal/db/queries/faturas_queries.sql
```

A line with `*` matches the diff (git path or with `prefix` stripped). A
line **without** `*` must exist as a file (`prefix/line` or at repo root).
Missing SQL → catalog **red**.

Init **does not** invent suites. You (or the team) write `globs.txt`.

Coverage runs only with a non-empty allowlist. Default baseline:
`.cqb/cover-baseline.json`. If you already keep another JSON, set
`cover.baseline_path`. Imports that count as I/O (80% floor):
`database/sql`, `net/http`, `os` — extend via `io_imports`.

Complexity ceilings are **yellow only**. HTTP handlers with many
`if err != nil` often want `cyclomatic` 35; `/cqb-setup` may *suggest*
that, and will not write yaml unless you agree.

---

## Git hook (opt-in)

Init **writes** `.cqb/hooks/pre-push` and **does not** attach it. To attach:

```bash
git config core.hooksPath .cqb/hooks
CQB=1 git push          # then it runs `cqb run --mode push`
git push                # without CQB the script is a no-op
```

Do not export `CQB=1` in bashrc: every push would wait on the gate.

---

## Constitution (yaml cannot undo this)

`cqb.yaml` tunes ceilings, prefix, allowlist, e2e catalog. It **cannot**
scan the whole module, make yellow fail git, or attach the hook by itself.
Keys such as `yellow_blocks` are ignored (`ignored_keys` on the report).

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
| Report / bundle | JSON file `.quality/last.json` with a color per check. |
| Slot | One section of that report (lint, test, e2e, cover, …). |
| Allowlist (`red_allowlist`) | Path globs where a test/coverage warning **may** turn red and stop git. Not an ignore list. |
| Glob | Path pattern (`internal/billing/**`, `*invoice*`). |
| Prefix (`prefix`) | Go module directory when it is not the git root. |
| Quick test | “Does new `Foo` have `TestFoo` that calls `Foo(`?” Not e2e, not %. |
| Hunter | Automatic check on a `*_test.go` or a new production line. |
| Cover / coverage | Percent of code hit by unit tests (`go test -cover`). |
| E2e | Journey test (`go test -tags e2e`), usually with Docker. |
| `globs.txt` | List that decides whether e2e **runs**, not whether unit tests are red. |
| Scan (`scan.json`) | Inventory written at init; not the allowlist. |
| Opt-in hook | Pre-push script that runs the gate only when `CQB=1`. |
| Engine | Python under `.cqb/engine` that actually builds the report. |
| `/cqb`, `/cqb-setup` | Commands in the **Cursor chat**, not the terminal. |
| Consumer | The Go repository that installed CQB. |
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
