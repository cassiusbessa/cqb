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
	} {
		if !strings.Contains(text, n) {
			t.Errorf("README missing %q", n)
		}
	}
}
