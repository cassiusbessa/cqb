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
		"skip list",
		".gitignore",
		"prefix",
		"services/billing",
		"red_allowlist",
		"unavailable",
		"globs.txt",
		"go test -tags e2e",
		"README.pt-BR.md",
		"yellow",
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
		"Uso rápido",
		"Glossário",
		"lista do que o CQB ignora",
		"red_allowlist",
		"prefix",
		"services/billing",
		"globs.txt",
		"README.md",
	} {
		if !strings.Contains(text, n) {
			t.Errorf("README.pt-BR.md missing %q", n)
		}
	}
}
