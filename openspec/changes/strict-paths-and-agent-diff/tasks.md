## 1. Config and naming

- [x] 1.1 Parse `strict_paths` in Go and Python yaml; keep `red_allowlist` as alias; if both keys exist `strict_paths` wins (including `[]`); new yaml from init writes `strict_paths: []` not the old key — verify `go test ./internal/config/...` and a Python test that loads each shape
- [x] 1.2 Thread the effective list through cover, hunters, and quick-test as “strict paths”; stop generating `red_allowlist` in comments/templates except a one-line deprecation — verify a fixture yaml with only the alias still reds an on-list hunter
- [x] 1.3 Update `openspec/config.yaml` constitution wording (empty strict paths; hook file may be attached; execution still `CQB=1`) and verify the file no longer calls the list an allowlist

## 2. Gate behavior

- [x] 2.1 Generate a coverprofile whenever the scoped diff has non-generated production `.go`, even if strict paths are empty; skip cover only with no such files — verify a Python test: empty list + new `internal/billing/normalize.go` → cover slot is not skip
- [x] 2.2 Paint cover/hunter/quick-test red only when the file matches strict paths; off-list stays yellow — verify empty list + missing invocation is yellow (exit 0) and on-list is red (exit 1)
- [x] 2.3 Remove the `--mode push` / hook mapping that exits 1 on e2e `unavailable`; keep failed e2e asserts and broken catalog as red — verify Python or CLI test: implied suite, no Docker, `--mode push` exits 0; failing `go test -tags e2e` still exits 1
- [x] 2.4 Do not rewrite the cover baseline on `cqb run` — verify the baseline file bytes are unchanged after a cover run

## 3. CLI review mode and init hook

- [x] 3.1 Add `cqb run --mode review` and `--base`; resolve upstream, else unique `main` xor `master`, else error asking for `--base`; diff = merge-base plus working tree — verify tests for unique `main`, both `main` and `master` without `--base` (no guessed diff), and `--base origin/develop`
- [x] 3.2 Leave default `cqb run`, `staged`, `push`, and `file-list` vs-HEAD behavior unchanged — verify default run still includes untracked against `HEAD`
- [x] 3.3 `cqb init` sets local `core.hooksPath` to `.cqb/hooks` when unset; if already set, leave it and print the attach recipe; never `--global`; hook still no-op without `CQB=1` — verify CLI tests for unset, `.husky` preserved, and push without the flag

## 4. Cursor skills

- [x] 4.1 `/cqb` gather runs `cqb run --mode review` (or default `cqb run` if the operator asked only for the working tree), waits for `.quality/last.json`, and interprets colors; delete copy that says the slash does not replace `cqb run` — verify `internal/cli` skill fixture tests
- [x] 4.2 On ambiguous-base error, the skill MUST stop and ask which ref, then re-run with `--base`; MUST NOT silently use `HEAD` — verify the skill text contains that ask
- [x] 4.3 `/cqb-setup` uses “strict paths” / “lista de rigor”, never “allowlist”; still does not write the list without confirmation — verify setup skill fixture tests

## 5. Docs

- [x] 5.1 Rewrite README.md and README.pt-BR.md in reading order (quick start, files, colors, checks, lista de rigor / strict paths, modes including `review`, Cursor, `cqb.yaml` keys, `globs.txt` as include-to-run, constitution in plain language); no “allowlist”; explain exactly-one e2e tree for `catalog_root` — verify `go test` readme tests and `TestNoPrivateProductPaths`
- [x] 5.2 Default `cqb.yaml` comments and bundle-reader template use strict paths and show that `prefix` is edited in `cqb.yaml` — verify render tests

## 6. Quality

- [x] 6.1 `gofmt` on touched Go; `go test ./...` and `python3 -m unittest discover -s engine/tests` pass
