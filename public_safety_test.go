package cqb_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

var forbidden = []string{
	"nf-service",
	"workspace-service",
	"crm-service",
	"MK-BACKEND",
	"mk_parametros",
	"erp-backend",
	"nf-transmission",
	"golangci.com/private",
}

func TestNoPrivateProductPaths(t *testing.T) {
	root := "."
	err := filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		rel := filepath.ToSlash(path)
		if info.IsDir() {
			switch info.Name() {
			case ".git", ".quality":
				return filepath.SkipDir
			}
			return nil
		}
		if strings.HasPrefix(rel, "openspec/") || strings.HasSuffix(rel, "public_safety_test.go") {
			return nil
		}
		if !strings.HasSuffix(rel, ".go") && !strings.HasSuffix(rel, ".py") &&
			!strings.HasSuffix(rel, ".md") && !strings.HasSuffix(rel, ".yml") &&
			!strings.HasSuffix(rel, ".yaml") && !strings.HasSuffix(rel, ".tmpl") &&
			!strings.HasSuffix(rel, "pre-push") {
			return nil
		}
		b, err := os.ReadFile(path)
		if err != nil {
			return nil
		}
		text := string(b)
		for _, f := range forbidden {
			if strings.Contains(text, f) {
				t.Errorf("%s contains private marker %q", rel, f)
			}
		}
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
}
