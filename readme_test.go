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
		"opt-in",
		"Yellow never",
		".gitignore",
		"prefix",
		"services/billing",
		"red_allowlist",
		"unavailable",
		"Constitution",
		"globs.txt",
		"go test -tags e2e",
		"README.pt-BR.md",
		"not an ignore list",
		"Manual configuration",
		"HALT",
	} {
		if !strings.Contains(text, n) {
			t.Errorf("README missing %q", n)
		}
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
		"não é lista de ignore",
		"Configuração manual",
		"red_allowlist",
		"prefix",
		"services/billing",
		"HALT",
		"globs.txt",
	} {
		if !strings.Contains(text, n) {
			t.Errorf("README.pt-BR.md missing %q", n)
		}
	}
}
