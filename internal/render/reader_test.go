package render_test

import (
	"strings"
	"testing"

	"github.com/cassiusbessa/cqb/internal/config"
	"github.com/cassiusbessa/cqb/internal/render"
)

func TestBundleReaderInterpolatesCeilings(t *testing.T) {
	tmpl := "cog {{cognitive}} cyclo {{cyclomatic}} nest {{nested_if}} paths {{strict_paths}}"
	cfg := config.Config{
		Complexity:  config.Complexity{Cognitive: 30, Cyclomatic: 30, NestedIf: 5, Delta: 5},
		StrictPaths: nil,
	}
	out := render.BundleReader(tmpl, cfg)
	if !strings.Contains(out, "30") || !strings.Contains(out, "5") {
		t.Fatalf("expected 30/30/5 in %q", out)
	}
	if !strings.Contains(out, "empty") && !strings.Contains(out, "_empty_") {
		t.Fatalf("empty strict-paths prose missing: %q", out)
	}
}
