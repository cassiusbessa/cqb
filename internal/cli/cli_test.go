package cli_test

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	cqb "github.com/cassiusbessa/cqb"
	"github.com/cassiusbessa/cqb/internal/cli"
	"github.com/cassiusbessa/cqb/internal/config"
	"github.com/cassiusbessa/cqb/internal/render"
)

func capture(t *testing.T, fn func() error) (string, error) {
	t.Helper()
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w
	err := fn()
	_ = w.Close()
	os.Stdout = old
	var buf bytes.Buffer
	_, _ = io.Copy(&buf, r)
	return buf.String(), err
}

func TestHelpAndPins(t *testing.T) {
	out, err := capture(t, func() error { return cli.Run(nil) })
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(out, cqb.GolangCILintVersion) || !strings.Contains(out, cqb.GremlinsVersion) {
		t.Fatalf("pins missing from help:\n%s", out)
	}
	if !strings.Contains(out, cqb.GolangCILintInstall) {
		t.Fatalf("install path missing:\n%s", out)
	}
}

func TestEmbedHasPlaceholders(t *testing.T) {
	if _, err := cqb.Content.ReadFile("engine/orchestrator.py"); err != nil {
		t.Fatal(err)
	}
	if _, err := cqb.Content.ReadFile("templates/review/cqb/SKILL.md"); err != nil {
		t.Fatal(err)
	}
	if _, err := cqb.Content.ReadFile("templates/hook/pre-push"); err != nil {
		t.Fatal(err)
	}
	if _, err := cqb.Content.ReadFile("templates/review/bundle-reader/SKILL.md.tmpl"); err != nil {
		t.Fatal(err)
	}
	setup, err := cqb.Content.ReadFile("templates/review/cqb-setup/SKILL.md")
	if err != nil {
		t.Fatal(err)
	}
	s := string(setup)
	if !strings.Contains(s, "HALT") || !strings.Contains(s, "raising cyclomatic") {
		t.Fatal("cqb-setup skill must HALT on strict paths and suggest raising cyclo")
	}
	if strings.Contains(s, "Allowlist") || strings.Contains(s, "allowlist:") {
		t.Fatal("cqb-setup must not teach allowlist as the product name")
	}
	if !strings.Contains(s, "strict_paths") && !strings.Contains(s, "lista de rigor") {
		t.Fatal("cqb-setup must name strict paths / lista de rigor")
	}
}

func git(t *testing.T, dir string, args ...string) {
	t.Helper()
	cmd := exec.Command("git", args...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), "GIT_AUTHOR_NAME=cqb", "GIT_AUTHOR_EMAIL=cqb@example.com",
		"GIT_COMMITTER_NAME=cqb", "GIT_COMMITTER_EMAIL=cqb@example.com")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("git %v: %v\n%s", args, err, out)
	}
}

func writeBillingApp(t *testing.T, dir, body string) {
	t.Helper()
	pkg := filepath.Join(dir, "internal", "billing")
	if err := os.MkdirAll(pkg, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "go.mod"), []byte("module github.com/example/billingapp\n\ngo 1.22\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(pkg, "normalize.go"), []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestInitGitignoreIdempotent(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	writeBillingApp(t, dir, "package billing\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	gi := filepath.Join(dir, ".gitignore")
	first, err := os.ReadFile(gi)
	if err != nil {
		t.Fatal(err)
	}
	text := string(first)
	for _, n := range []string{"# cqb begin", "# cqb end", ".quality/", ".cqb/scan.json", ".cqb/work/", "*.coverprofile", ".cqb/**/__pycache__/"} {
		if !strings.Contains(text, n) {
			t.Fatalf("gitignore missing %q:\n%s", n, text)
		}
	}
	if strings.Contains(text, ".cqb/engine") {
		t.Fatalf("must not ignore engine:\n%s", text)
	}
	for _, line := range strings.Split(text, "\n") {
		trim := strings.TrimSpace(line)
		if trim == "cqb.yaml" || strings.HasPrefix(trim, "cqb.yaml ") {
			t.Fatalf("must not ignore cqb.yaml:\n%s", text)
		}
	}
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	second, err := os.ReadFile(gi)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Count(string(second), "# cqb begin") != 1 {
		t.Fatalf("duplicate cqb ignore block:\n%s", second)
	}
}

func TestInitNestedCatalogRoot(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	suite := filepath.Join(dir, "services", "billing", "internal", "e2e", "invoices")
	if err := os.MkdirAll(suite, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(suite, "globs.txt"), []byte("internal/application/**\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	writeBillingApp(t, dir, "package billing\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(filepath.Join(dir, "cqb.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(b), "services/billing/internal/e2e") {
		t.Fatalf("new yaml should point catalog at nested e2e:\n%s", b)
	}
}

func TestInitKeepsExistingCatalogRoot(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	suite := filepath.Join(dir, "services", "billing", "internal", "e2e", "invoices")
	if err := os.MkdirAll(suite, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(suite, "globs.txt"), []byte("internal/application/**\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	orig := "kit_version: \"0.1.0\"\ne2e:\n  catalog_root: \"internal/e2e\"\nprefix: \"services/billing\"\n"
	if err := os.WriteFile(filepath.Join(dir, "cqb.yaml"), []byte(orig), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(filepath.Join(dir, "cqb.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(b), `catalog_root: "internal/e2e"`) {
		t.Fatalf("existing catalog_root overwritten:\n%s", b)
	}
}

func TestInitSetsHooksPathWhenUnset(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	writeBillingApp(t, dir, "package billing\n\nfunc NormalizeX(s string) string { return s }\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	for _, p := range []string{
		filepath.Join(dir, ".cqb", "engine", "orchestrator.py"),
		filepath.Join(dir, "cqb.yaml"),
		filepath.Join(dir, ".cqb", "scan.json"),
		filepath.Join(dir, ".cqb", "hooks", "pre-push"),
	} {
		if _, err := os.Stat(p); err != nil {
			t.Fatalf("missing %s: %v", p, err)
		}
	}
	yml, err := os.ReadFile(filepath.Join(dir, "cqb.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(yml, []byte("strict_paths:")) {
		t.Fatalf("new yaml must write strict_paths, got:\n%s", yml)
	}
	if bytes.Contains(yml, []byte("red_allowlist:")) {
		t.Fatalf("new yaml must not write red_allowlist:\n%s", yml)
	}
	hook, err := os.ReadFile(filepath.Join(dir, ".cqb", "hooks", "pre-push"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(hook, []byte("cqb run --mode push")) {
		t.Fatalf("hook must call cqb run --mode push:\n%s", hook)
	}
	got, err := exec.Command("git", "-C", dir, "config", "--local", "--get", "core.hooksPath").CombinedOutput()
	if err != nil {
		t.Fatalf("hooksPath: %v %s", err, got)
	}
	if strings.TrimSpace(string(got)) != ".cqb/hooks" {
		t.Fatalf("expected local hooksPath .cqb/hooks, got %q", got)
	}
}

func TestInitPreservesExistingHooksPath(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	writeBillingApp(t, dir, "package billing\n")
	if out, err := exec.Command("git", "-C", dir, "config", "--local", "core.hooksPath", ".husky").CombinedOutput(); err != nil {
		t.Fatalf("set husky: %v %s", err, out)
	}
	out, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) })
	if err != nil {
		t.Fatal(err)
	}
	got, err := exec.Command("git", "-C", dir, "config", "--local", "--get", "core.hooksPath").CombinedOutput()
	if err != nil {
		t.Fatal(err)
	}
	if strings.TrimSpace(string(got)) != ".husky" {
		t.Fatalf("must not overwrite hooksPath, got %q", got)
	}
	if !strings.Contains(out, ".husky") {
		t.Fatalf("stdout should mention existing path:\n%s", out)
	}
}

func TestUpgradeReplacesStaleFile(t *testing.T) {
	dir := t.TempDir()
	writeBillingApp(t, dir, "package billing\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	stale := filepath.Join(dir, ".cqb", "engine", "STALE_OLD")
	if err := os.WriteFile(stale, []byte("old"), 0o644); err != nil {
		t.Fatal(err)
	}
	gone := filepath.Join(dir, ".cqb", "engine", "orchestrator.py")
	if err := os.WriteFile(gone, []byte("# dummy old orchestrator\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := capture(t, func() error { return cli.Run([]string{"upgrade", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(gone)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Equal(b, []byte("# dummy old orchestrator\n")) {
		t.Fatal("orchestrator was not replaced")
	}
	if !bytes.Contains(b, []byte("CQB orchestrator")) {
		t.Fatalf("upgraded orchestrator unexpected: %s", b[:min(80, len(b))])
	}
}

func TestSetupCopyDoesNotOverwrite(t *testing.T) {
	dir := t.TempDir()
	existing := filepath.Join(dir, ".cursor", "skills", "cqb", "SKILL.md")
	if err := os.MkdirAll(filepath.Dir(existing), 0o755); err != nil {
		t.Fatal(err)
	}
	orig := []byte("# keep me\n")
	if err := os.WriteFile(existing, orig, 0o644); err != nil {
		t.Fatal(err)
	}
	acts, err := cli.SetupCopy(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	var sawSkip bool
	for _, a := range acts {
		if a.Dest == ".cursor/skills/cqb/SKILL.md" && a.Action == "skip" {
			sawSkip = true
		}
	}
	if !sawSkip {
		t.Fatalf("dry-run should skip existing skill, got %+v", acts)
	}
	acts, err = cli.SetupCopy(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(existing)
	if !bytes.Equal(got, orig) {
		t.Fatalf("existing skill overwritten")
	}
	_ = acts
}

func TestRenderReaderMentionsCeilings(t *testing.T) {
	dir := t.TempDir()
	writeBillingApp(t, dir, "package billing\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	cfg, err := config.Load(filepath.Join(dir, "cqb.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	tmpl, err := cli.ReaderTemplate()
	if err != nil {
		t.Fatal(err)
	}
	body := render.BundleReader(string(tmpl), cfg)
	if !strings.Contains(body, "30") || !strings.Contains(body, "**30**") {
		t.Fatalf("rendered reader missing 30/30/5:\n%s", body)
	}
}

func TestRunYellowOnlyExitZero(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	ladder := "package billing\n\nfunc NormalizeInvoiceRef(s string) string {\n"
	for i := 0; i < 31; i++ {
		ladder += "\tif s == \"" + itoa(i) + "\" {\n\t\treturn s\n\t}\n"
	}
	ladder += "\treturn s\n}\n"
	writeBillingApp(t, dir, ladder)
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	err := cli.Run([]string{"run", "--dir", dir, "--mode", "file-list", "--files", "internal/billing/normalize.go", "--output", ".quality/last.json"})
	if err != nil {
		var ee *cli.ExitError
		if errors.As(err, &ee) && ee.Code != 0 {
			t.Fatalf("yellow-only must exit 0, got %d", ee.Code)
		}
		if err != nil && ee == nil {
			t.Fatal(err)
		}
	}
	raw, err := os.ReadFile(filepath.Join(dir, ".quality", "last.json"))
	if err != nil {
		t.Fatal(err)
	}
	var doc map[string]any
	if err := json.Unmarshal(raw, &doc); err != nil {
		t.Fatal(err)
	}
	if doc["has_red"] == true {
		t.Fatalf("has_red true on yellow fixture: %s", raw)
	}
}

func TestHookOptIn(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	writeBillingApp(t, dir, "package billing\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	hook := filepath.Join(dir, ".cqb", "hooks", "pre-push")
	cmd := exec.Command("sh", hook)
	cmd.Dir = dir
	cmd.Env = []string{"PATH=" + dir + "/bin:/usr/bin:/bin", "HOME=" + dir}
	if err := cmd.Run(); err != nil {
		t.Fatalf("hook without CQB must no-op: %v", err)
	}
	bin := filepath.Join(dir, "bin")
	if err := os.MkdirAll(bin, 0o755); err != nil {
		t.Fatal(err)
	}
	marker := filepath.Join(dir, "hook-ran")
	script := "#!/bin/sh\necho ran > " + marker + "\n"
	if err := os.WriteFile(filepath.Join(bin, "cqb"), []byte(script), 0o755); err != nil {
		t.Fatal(err)
	}
	cmd = exec.Command("sh", hook)
	cmd.Dir = dir
	cmd.Env = []string{"PATH=" + bin + ":/usr/bin:/bin", "HOME=" + dir, "CQB=1"}
	if err := cmd.Run(); err != nil {
		t.Fatalf("hook with CQB=1: %v", err)
	}
	if _, err := os.Stat(marker); err != nil {
		t.Fatal("hook with CQB=1 did not call cqb run")
	}
}

func TestReviewBaseUniqueMain(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init", "-b", "main")
	writeBillingApp(t, dir, "package billing\n")
	git(t, dir, "add", "-A")
	git(t, dir, "commit", "-m", "init")
	got, err := cli.ResolveReviewBase(dir, "")
	if err != nil {
		t.Fatal(err)
	}
	if got != "main" {
		t.Fatalf("got %q want main", got)
	}
}

func TestReviewBaseAmbiguous(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init", "-b", "main")
	writeBillingApp(t, dir, "package billing\n")
	git(t, dir, "add", "-A")
	git(t, dir, "commit", "-m", "init")
	git(t, dir, "branch", "master")
	_, err := cli.ResolveReviewBase(dir, "")
	if err == nil || !strings.Contains(err.Error(), "--base") {
		t.Fatalf("expected ambiguous --base error, got %v", err)
	}
}

func TestReviewBaseExplicit(t *testing.T) {
	got, err := cli.ResolveReviewBase(".", "origin/develop")
	if err != nil {
		t.Fatal(err)
	}
	if got != "origin/develop" {
		t.Fatalf("got %q", got)
	}
}

func TestDefaultRunIncludesUntracked(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init", "-b", "main")
	writeBillingApp(t, dir, "package billing\n\nfunc Ok() {}\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	git(t, dir, "add", "-A")
	git(t, dir, "commit", "-m", "init")
	extra := filepath.Join(dir, "internal", "billing", "extra.go")
	if err := os.WriteFile(extra, []byte("package billing\n\nfunc Extra() {}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	err := cli.Run([]string{"run", "--dir", dir, "--output", ".quality/last.json"})
	if err != nil {
		var ee *cli.ExitError
		if errors.As(err, &ee) && ee.Code != 0 {
			t.Fatalf("untracked helper should not fail git with empty strict_paths, code %d", ee.Code)
		} else if ee == nil {
			t.Fatal(err)
		}
	}
	raw, err := os.ReadFile(filepath.Join(dir, ".quality", "last.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(raw, []byte("extra.go")) && !bytes.Contains(raw, []byte("Extra")) {
		t.Fatalf("default run should see untracked extra.go:\n%s", raw)
	}
}

func TestTemplatesCopyIntoFixtureCursor(t *testing.T) {
	dir := t.TempDir()
	acts, err := cli.SetupCopy(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	if len(acts) == 0 {
		t.Fatal("no copy actions")
	}
	p := filepath.Join(dir, ".cursor", "skills", "cqb", "SKILL.md")
	b, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	text := strings.ToLower(string(b))
	if !strings.Contains(text, "gather") || !strings.Contains(text, "verification-gap") {
		t.Fatalf("skill missing gather/verification-gap")
	}
	if !strings.Contains(text, "skip") || !strings.Contains(text, "unavailable") {
		t.Fatalf("skill must say skip/unavailable is not a pass")
	}
	if !strings.Contains(text, ".quality/last.json") {
		t.Fatal("missing last.json wait")
	}
	if !strings.Contains(string(b), "--mode review") {
		t.Fatal("skill must run cqb run --mode review")
	}
	if !strings.Contains(strings.ToLower(string(b)), "--base") {
		t.Fatal("skill must ask for --base when the base is ambiguous")
	}
	if strings.Contains(strings.ToLower(string(b)), "does not replace") {
		t.Fatal("skill must not say the slash does not replace cqb run")
	}
}

func TestDogfoodSkipYellowRed(t *testing.T) {
	dir := t.TempDir()
	git(t, dir, "init")
	writeBillingApp(t, dir, "package billing\n\nfunc Ok() {}\n")
	if _, err := capture(t, func() error { return cli.Run([]string{"init", "--dir", dir}) }); err != nil {
		t.Fatal(err)
	}
	yml := filepath.Join(dir, "cqb.yaml")
	b, err := os.ReadFile(yml)
	if err != nil {
		t.Fatal(err)
	}
	text := strings.Replace(string(b), `prefix: ""`, `prefix: "internal/billing"`, 1)
	if err := os.WriteFile(yml, []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}

	err = cli.Run([]string{"run", "--dir", dir, "--mode", "file-list", "--files", "internal/other/x.go", "--output", ".quality/skip.json"})
	if err != nil {
		t.Fatalf("skip must exit 0: %v", err)
	}
	raw, _ := os.ReadFile(filepath.Join(dir, ".quality", "skip.json"))
	if !bytes.Contains(raw, []byte(`"skipped": true`)) {
		t.Fatalf("expected skip bundle: %s", raw)
	}

	ladder := "package billing\n\nfunc NormalizeInvoiceRef(s string) string {\n"
	for i := 0; i < 31; i++ {
		ladder += "\tif s == \"" + itoa(i) + "\" {\n\t\treturn s\n\t}\n"
	}
	ladder += "\treturn s\n}\n"
	if err := os.WriteFile(filepath.Join(dir, "internal", "billing", "normalize.go"), []byte(ladder), 0o644); err != nil {
		t.Fatal(err)
	}
	err = cli.Run([]string{"run", "--dir", dir, "--mode", "file-list", "--files", "internal/billing/normalize.go", "--output", ".quality/yellow.json"})
	if err != nil {
		var ee *cli.ExitError
		if errors.As(err, &ee) && ee.Code != 0 {
			t.Fatalf("yellow must exit 0, code %d", ee.Code)
		} else if ee == nil {
			t.Fatal(err)
		}
	}
	raw, _ = os.ReadFile(filepath.Join(dir, ".quality", "yellow.json"))
	if bytes.Contains(raw, []byte(`"has_red": true`)) {
		t.Fatalf("empty strict_paths hunters must not be red: %s", raw)
	}

	bad := "package billing\n\nfunc Broken() {\n\tx := 1\n}\n"
	if err := os.WriteFile(filepath.Join(dir, "internal", "billing", "normalize.go"), []byte(bad), 0o644); err != nil {
		t.Fatal(err)
	}
	err = cli.Run([]string{"run", "--dir", dir, "--mode", "file-list", "--files", "internal/billing/normalize.go", "--output", ".quality/red.json"})
	var ee *cli.ExitError
	if !errors.As(err, &ee) || ee.Code != 1 {
		t.Fatalf("unused var must be red exit 1, err=%v", err)
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [8]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}
