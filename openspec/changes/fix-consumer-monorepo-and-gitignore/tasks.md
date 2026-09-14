## 1. Prefix-relative matching

- [x] 1.1 Add `module_rel(git_path, prefixes)` and match globs/testable/allowlist against git path **or** module-relative path, including directory includes (`internal/`), and verify a fixture `services/billing/internal/application/services/invoice_total.go` matches glob `internal/application/services/*invoice*` and include `internal/`
- [x] 1.2 Keep bundle `file` fields git-relative and verify the finding path still starts with `services/billing/` in the same fixture

## 2. E2E catalog and execution

- [x] 2.1 Resolve wildcard-free glob lines at `root/prefix/line` then `root/line`, and verify a literal `internal/db/queries/faturas_queries.sql` that exists only under `services/billing/` does **not** break the catalog
- [x] 2.2 If `catalog_root` is missing, try `{prefix}/internal/e2e`, and verify a tree with only the nested catalog is used
- [x] 2.3 When a suite is implied, run `go test -tags e2e -count=1 -timeout 8m` on that package; map exit 0 → green, non-zero → red, and verify with a tiny stub test tagged e2e in fixtures
- [x] 2.4 When a suite is implied and `docker` is not on PATH, set e2e `unavailable` (not green) and verify; hook `CQB=1` still exits 1 for that case

## 3. Coverprofile

- [x] 3.1 When allowlist production files are in the diff, run `go test -vet=off -coverprofile` into `.cqb/work/` and parse it, and verify missing `--coverprofile` is no longer yellow-by-default
- [x] 3.2 Pure allowlist helper without `Foo(` remains red and the baseline file is not rewritten, and verify both

## 4. Hunters

- [x] 4.1 Dedupe findings by hunter+file+line+message and verify a single `t.Fatal("short")` yields one `blind_assert`
- [x] 4.2 Replace Test-name `missing_boundary` with new-production numeric/`len` literal vs test mention; exempt HTTP status and time constants; verify `TestTotal_volume` alone does not fire

## 5. Init gitignore and scan

- [x] 5.1 `cqb init` upserts a `# cqb begin` / `# cqb end` block (`.quality/`, `.cqb/scan.json`, `.cqb/work/`, `*.coverprofile`, `.cqb/**/__pycache__/`) without ignoring engine/hooks/templates/`cqb.yaml`, and verify a temp dir with no gitignore then a second init (block appears once)
- [x] 5.2 New `cqb.yaml` may set `e2e.catalog_root` to `{prefix}/internal/e2e` when that dir exists; existing yaml is not overwritten, and verify both

## 6. Regression fixtures

- [x] 6.1 Python tests under invented `services/billing` cover glob match, literal SQL, unique hunter, cover invocation red, and `go test ./...` plus `python3 -m unittest discover -s engine/tests` pass
- [x] 6.2 README notes prefix-relative globs and gitignore; public-safety grep still clean
