package cqb_test

import (
	"os"
	"strings"
	"testing"
)

func TestREADMEDocumentsSurface(t *testing.T) {
	b, err := os.ReadFile("README.md")
	if err != nil {
		t.Fatal(err)
	}
	text := string(b)
	for _, n := range []string{
		"go install",
		"cqb init",
		"/cqb-setup",
		"cqb run",
		"/cqb",
		"Quick start",
		"Glossary",
		"strict_paths",
		"skip / ignore list",
		".gitignore",
		"prefix",
		"services/billing",
		"unavailable",
		"globs.txt",
		"go test -tags e2e",
		"README.pt-BR.md",
		"yellow",
		"--mode review",
		"cqb.yaml",
	} {
		if !strings.Contains(text, n) {
			t.Errorf("README missing %q", n)
		}
	}
	if strings.Contains(text, "Allowlist") || strings.Contains(text, "allowlist:") {
		t.Error("README should not teach allowlist as the product name")
	}
}

func TestREADMEPortuguese(t *testing.T) {
	b, err := os.ReadFile("README.pt-BR.md")
	if err != nil {
		t.Fatal(err)
	}
	text := string(b)
	for _, n := range []string{
		"go install",
		"cqb init",
		"/cqb-setup",
		"Uso rápido",
		"Glossário",
		"lista de rigor",
		"strict_paths",
		"lista do que o CQB ignora",
		"prefix",
		"services/billing",
		"globs.txt",
		"README.md",
		"cqb.yaml",
		"--mode review",
	} {
		if !strings.Contains(text, n) {
			t.Errorf("README.pt-BR.md missing %q", n)
		}
	}
}
