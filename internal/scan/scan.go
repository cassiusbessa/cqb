package scan

import (
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
)

type Result struct {
	Module            string   `json:"module"`
	GoFiles           int      `json:"go_files"`
	TestGoFiles       int      `json:"test_go_files"`
	TestDensity       float64  `json:"test_density"`
	E2ESuites         []string `json:"e2e_suites"`
	GeneratedPatterns []string `json:"generated_patterns"`
	ValidatorCalls    []string `json:"validator_calls"`
	HTTPHandlerHint   bool     `json:"http_handler_hint"`
}

func ModulePath(root string) string {
	b, err := os.ReadFile(filepath.Join(root, "go.mod"))
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "module ") {
			return strings.TrimSpace(strings.TrimPrefix(line, "module "))
		}
	}
	return ""
}

func Run(root string) (Result, error) {
	r := Result{
		Module:            ModulePath(root),
		E2ESuites:         []string{},
		GeneratedPatterns: []string{"*.sql.go", "models.go", "docs/"},
		ValidatorCalls:    []string{"Struct", "ValidateStruct"},
	}
	_ = filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		rel, _ := filepath.Rel(root, path)
		rel = filepath.ToSlash(rel)
		if d.IsDir() {
			base := d.Name()
			if base == ".git" || base == "vendor" || base == ".cqb" || base == "node_modules" {
				return filepath.SkipDir
			}
			return nil
		}
		if strings.HasSuffix(rel, ".go") {
			r.GoFiles++
			if strings.HasSuffix(rel, "_test.go") {
				r.TestGoFiles++
			}
			b, _ := os.ReadFile(path)
			if strings.Contains(string(b), "http.ResponseWriter") {
				r.HTTPHandlerHint = true
			}
		}
		if strings.HasSuffix(rel, "/globs.txt") && strings.Contains(rel, "/e2e/") {
			dir := filepath.ToSlash(filepath.Dir(rel))
			r.E2ESuites = append(r.E2ESuites, dir)
		}
		return nil
	})
	if r.GoFiles > 0 {
		r.TestDensity = float64(r.TestGoFiles) / float64(r.GoFiles)
	}
	return r, nil
}

// InferCatalogRoot returns the unique parent of e2e suite dirs (e.g.
// services/billing/internal/e2e), or empty if none / not unique.
func InferCatalogRoot(suites []string) string {
	seen := map[string]struct{}{}
	var parents []string
	for _, s := range suites {
		p := filepath.ToSlash(filepath.Dir(s))
		if p == "." || p == "" {
			continue
		}
		if _, ok := seen[p]; ok {
			continue
		}
		seen[p] = struct{}{}
		parents = append(parents, p)
	}
	if len(parents) == 1 {
		return parents[0]
	}
	return ""
}

func Write(root string, r Result) error {
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return err
	}
	dir := filepath.Join(root, ".cqb")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, "scan.json"), append(b, '\n'), 0o644)
}
