package config_test

import (
	"testing"

	"github.com/cassiusbessa/cqb/internal/config"
)

func TestParseDefaults(t *testing.T) {
	cfg, err := config.Parse([]byte(`
kit_version: "0.1.0"
complexity:
  cognitive: 30
  cyclomatic: 30
  nested_if: 5
  delta: 5
strict_paths: []
extra_hunters: []
`))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Complexity.Cognitive != 30 || cfg.Complexity.Cyclomatic != 30 || cfg.Complexity.NestedIf != 5 {
		t.Fatalf("ceilings: %+v", cfg.Complexity)
	}
	if len(cfg.StrictPaths) != 0 {
		t.Fatalf("strict paths should be empty, got %v", cfg.StrictPaths)
	}
}

func TestIllegalKeysCollectedNotHonored(t *testing.T) {
	cfg, err := config.Parse([]byte(`
yellow_blocks: true
whole_module: true
always_on_hook: true
legacy_absolute_red: true
complexity:
  cognitive: 30
`))
	if err != nil {
		t.Fatal(err)
	}
	if len(cfg.IgnoredKeys) < 4 {
		t.Fatalf("expected illegal keys ignored, got %v", cfg.IgnoredKeys)
	}
}

func TestRedAllowlistKeyIsIgnored(t *testing.T) {
	cfg, err := config.Parse([]byte(`
red_allowlist:
  - "internal/billing/**"
`))
	if err != nil {
		t.Fatal(err)
	}
	if len(cfg.StrictPaths) != 0 {
		t.Fatalf("red_allowlist must not load into StrictPaths, got %v", cfg.StrictPaths)
	}
}

func TestStrictPathsKey(t *testing.T) {
	cfg, err := config.Parse([]byte(`
strict_paths:
  - "internal/billing/**"
`))
	if err != nil {
		t.Fatal(err)
	}
	if len(cfg.StrictPaths) != 1 || cfg.StrictPaths[0] != "internal/billing/**" {
		t.Fatalf("strict_paths: %v", cfg.StrictPaths)
	}
}
