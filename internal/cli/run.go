package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	cqb "github.com/cassiusbessa/cqb"
	"github.com/cassiusbessa/cqb/internal/config"
	"github.com/cassiusbessa/cqb/internal/render"
	"github.com/cassiusbessa/cqb/internal/scan"
)

func Run(args []string) error {
	if len(args) == 0 || args[0] == "help" || args[0] == "-h" || args[0] == "--help" {
		fmt.Fprint(os.Stdout, HelpText())
		return nil
	}
	cmd := args[0]
	rest := args[1:]
	switch cmd {
	case "version":
		fmt.Fprintf(os.Stdout, "cqb %s\ngolangci-lint %s\ngremlins %s\n", cqb.KitVersion, cqb.GolangCILintVersion, cqb.GremlinsVersion)
		return nil
	case "init":
		return cmdInit(parseDir(rest))
	case "run":
		return cmdRun(rest)
	case "upgrade":
		return cmdUpgrade(parseDir(rest))
	case "render-reader":
		return cmdRenderReader(rest)
	case "setup-copy":
		return cmdSetupCopy(rest)
	default:
		return fmt.Errorf("unknown command %q\n\n%s", cmd, HelpText())
	}
}

func parseDir(args []string) string {
	dir := "."
	for i := 0; i < len(args); i++ {
		if args[i] == "--dir" && i+1 < len(args) {
			dir = args[i+1]
			i++
		}
	}
	abs, err := filepath.Abs(dir)
	if err != nil {
		return dir
	}
	return abs
}

func flag(args []string, name, fallback string) string {
	for i := 0; i < len(args); i++ {
		if args[i] == name && i+1 < len(args) {
			return args[i+1]
		}
		if strings.HasPrefix(args[i], name+"=") {
			return strings.TrimPrefix(args[i], name+"=")
		}
	}
	return fallback
}

func hasFlag(args []string, name string) bool {
	for _, a := range args {
		if a == name {
			return true
		}
	}
	return false
}

func cmdInit(dir string) error {
	if err := CopyEngine(dir); err != nil {
		return fmt.Errorf("vendor engine: %w", err)
	}
	if err := CopyTemplates(dir); err != nil {
		return fmt.Errorf("vendor templates: %w", err)
	}
	if err := CopyHook(dir); err != nil {
		return fmt.Errorf("hook file: %w", err)
	}
	res, err := scan.Run(dir)
	if err != nil {
		return err
	}
	yamlPath := filepath.Join(dir, "cqb.yaml")
	if _, err := os.Stat(yamlPath); os.IsNotExist(err) {
		b, err := DefaultYAML()
		if err != nil {
			return err
		}
		if root := catalogRootForNewYAML(dir, b, res); root != "" {
			b = bytes.Replace(b, []byte(`catalog_root: "internal/e2e"`), []byte(`catalog_root: "`+root+`"`), 1)
		}
		if err := os.WriteFile(yamlPath, b, 0o644); err != nil {
			return err
		}
	}
	if err := UpsertGitignore(dir); err != nil {
		return fmt.Errorf("gitignore: %w", err)
	}
	if err := scan.Write(dir, res); err != nil {
		return err
	}
	if err := ensureTools(); err != nil {
		fmt.Fprintf(os.Stderr, "cqb init: host tools: %v (continuing)\n", err)
	}
	fmt.Fprintf(os.Stdout, "cqb init: wrote .cqb/, cqb.yaml, .gitignore, .cqb/scan.json, .cqb/hooks/pre-push\n")
	attachLocalHooksPath(dir)
	fmt.Fprintf(os.Stdout, "pinned: golangci-lint %s  gremlins %s\n", cqb.GolangCILintVersion, cqb.GremlinsVersion)
	return nil
}

func attachLocalHooksPath(dir string) {
	get := exec.Command("git", "-C", dir, "config", "--local", "--get", "core.hooksPath")
	out, err := get.CombinedOutput()
	cur := strings.TrimSpace(string(out))
	if err == nil && cur != "" {
		if cur == ".cqb/hooks" {
			fmt.Fprintf(os.Stdout, "local core.hooksPath=.cqb/hooks (still no-op unless CQB=1 git push)\n")
			return
		}
		fmt.Fprintf(os.Stdout, "core.hooksPath is %s (left unchanged). To use CQB:\n  git config --local core.hooksPath .cqb/hooks\n  CQB=1 git push\n", cur)
		return
	}
	set := exec.Command("git", "-C", dir, "config", "--local", "core.hooksPath", ".cqb/hooks")
	if err := set.Run(); err != nil {
		fmt.Fprintf(os.Stdout, "hook is opt-in (could not set core.hooksPath here). To attach:\n  git config --local core.hooksPath .cqb/hooks\n  CQB=1 git push\n")
		return
	}
	fmt.Fprintf(os.Stdout, "set local core.hooksPath=.cqb/hooks (still no-op unless CQB=1 git push)\n")
}

func catalogRootForNewYAML(dir string, yamlBytes []byte, res scan.Result) string {
	cfg, err := config.Parse(yamlBytes)
	if err == nil {
		prefixes := config.PrefixList(cfg)
		if len(prefixes) == 1 {
			cand := filepath.Join(dir, filepath.FromSlash(prefixes[0]), "internal", "e2e")
			if info, err := os.Stat(cand); err == nil && info.IsDir() {
				return filepath.ToSlash(filepath.Join(prefixes[0], "internal", "e2e"))
			}
		}
	}
	return scan.InferCatalogRoot(res.E2ESuites)
}

func ensureTools() error {
	var first error
	for _, t := range []struct{ bin, spec string }{
		{"golangci-lint", cqb.GolangCILintInstall},
		{"gremlins", cqb.GremlinsInstall},
	} {
		if _, err := exec.LookPath(t.bin); err == nil {
			continue
		}
		cmd := exec.Command("go", "install", t.spec)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
		if err := cmd.Run(); err != nil && first == nil {
			first = fmt.Errorf("go install %s: %w", t.spec, err)
		}
	}
	return first
}

func cmdUpgrade(dir string) error {
	dummyMarker := filepath.Join(dir, ".cqb", "engine", "STALE")
	_ = dummyMarker
	if err := CopyEngine(dir); err != nil {
		return err
	}
	if err := CopyTemplates(dir); err != nil {
		return err
	}
	if err := CopyHook(dir); err != nil {
		return err
	}
	if err := UpsertGitignore(dir); err != nil {
		return fmt.Errorf("gitignore: %w", err)
	}
	yamlPath := filepath.Join(dir, "cqb.yaml")
	b, err := os.ReadFile(yamlPath)
	if err == nil {
		text := string(b)
		if strings.Contains(text, "kit_version:") {
			// bump pin to current kit
			lines := strings.Split(text, "\n")
			for i, ln := range lines {
				if strings.HasPrefix(strings.TrimSpace(ln), "kit_version:") {
					indent := ln[:len(ln)-len(strings.TrimLeft(ln, " \t"))]
					lines[i] = indent + `kit_version: "` + cqb.KitVersion + `"`
				}
			}
			_ = os.WriteFile(yamlPath, []byte(strings.Join(lines, "\n")), 0o644)
		}
	}
	fmt.Fprintf(os.Stdout, "cqb upgrade: refreshed .cqb/ to kit %s\n", cqb.KitVersion)
	return nil
}

func cmdRenderReader(args []string) error {
	dir := parseDir(args)
	cfg, err := config.Load(filepath.Join(dir, "cqb.yaml"))
	if err != nil {
		return err
	}
	tmpl, err := ReaderTemplate()
	if err != nil {
		return err
	}
	body := render.BundleReader(string(tmpl), cfg)
	out := flag(args, "--out", "")
	if out == "" {
		if err := WriteReader(dir, body); err != nil {
			return err
		}
		fmt.Fprintln(os.Stdout, ".cursor/skills/cqb-bundle-reader/SKILL.md")
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(out), 0o755); err != nil {
		return err
	}
	return os.WriteFile(out, []byte(body), 0o644)
}

func cmdSetupCopy(args []string) error {
	dir := parseDir(args)
	dry := hasFlag(args, "--dry-run")
	acts, err := SetupCopy(dir, dry)
	if err != nil {
		return err
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	return enc.Encode(acts)
}

func cmdRun(args []string) error {
	dir := parseDir(args)
	mode := flag(args, "--mode", "uncommitted")
	files := flag(args, "--files", "")
	output := flag(args, "--output", ".quality/last.json")
	python, err := exec.LookPath("python3")
	if err != nil {
		return fmt.Errorf("python3 is required for the gate engine: %w", err)
	}
	engine := filepath.Join(dir, ".cqb", "engine", "orchestrator.py")
	if _, err := os.Stat(engine); err != nil {
		return fmt.Errorf("vendored engine missing (%s); run cqb init", engine)
	}
	cmdArgs := []string{engine, "--root", dir, "--mode", mode, "--output", output}
	if mode == "review" {
		base, err := ResolveReviewBase(dir, flag(args, "--base", ""))
		if err != nil {
			return err
		}
		cmdArgs = append(cmdArgs, "--base", base)
	}
	if files != "" {
		cmdArgs = append(cmdArgs, "--files", files)
	}
	if cp := flag(args, "--coverprofile", ""); cp != "" {
		cmdArgs = append(cmdArgs, "--coverprofile", cp)
	}
	if mj := flag(args, "--mutation-json", ""); mj != "" {
		cmdArgs = append(cmdArgs, "--mutation-json", mj)
	}
	cmd := exec.Command(python, cmdArgs...)
	cmd.Stdout = nil
	cmd.Stderr = os.Stderr
	cmd.Dir = dir
	err = cmd.Run()
	if err == nil {
		return nil
	}
	if ee, ok := err.(*exec.ExitError); ok {
		return &ExitError{Code: ee.ExitCode()}
	}
	return err
}
