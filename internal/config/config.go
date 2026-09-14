package config

import (
	"fmt"
	"os"
	"strings"

	"gopkg.in/yaml.v3"
)

// IllegalKeys cannot invert the constitution; they are ignored if present.
var IllegalKeys = []string{
	"yellow_blocks",
	"yellow_blocks_git",
	"whole_module",
	"scan_whole_module",
	"always_on_hook",
	"legacy_absolute_red",
	"red_on_legacy_complexity",
}

type Complexity struct {
	Cognitive  int `yaml:"cognitive"`
	Cyclomatic int `yaml:"cyclomatic"`
	NestedIf   int `yaml:"nested_if"`
	Delta      int `yaml:"delta"`
}

type Testable struct {
	Include []string `yaml:"include"`
	Exclude []string `yaml:"exclude"`
}

type E2E struct {
	CatalogRoot string `yaml:"catalog_root"`
}

type Cover struct {
	IOFloor      int    `yaml:"io_floor"`
	BaselinePath string `yaml:"baseline_path"`
}

type Config struct {
	KitVersion       string     `yaml:"kit_version"`
	Prefix           any        `yaml:"prefix"`
	Prefixes         []string   `yaml:"prefixes"`
	OperatorLanguage string     `yaml:"operator_language"`
	Complexity       Complexity `yaml:"complexity"`
	StrictPaths      []string   `yaml:"strict_paths"`
	RedAllowlist     []string   `yaml:"red_allowlist"`
	Testable         Testable   `yaml:"testable"`
	IOImports        []string   `yaml:"io_imports"`
	ExtraHunters     []string   `yaml:"extra_hunters"`
	E2E              E2E        `yaml:"e2e"`
	Cover            Cover      `yaml:"cover"`
	IgnoredKeys      []string   `yaml:"-"`
}

func defaults() Config {
	return Config{
		KitVersion:       "0.1.0",
		OperatorLanguage: "pt-BR",
		Complexity:       Complexity{Cognitive: 30, Cyclomatic: 30, NestedIf: 5, Delta: 5},
		StrictPaths:      []string{},
		RedAllowlist:     []string{},
		Testable: Testable{
			Include: []string{"internal/"},
			Exclude: []string{"internal/interface/"},
		},
		IOImports:    []string{"database/sql", "net/http", "os"},
		ExtraHunters: []string{},
		E2E:          E2E{CatalogRoot: "internal/e2e"},
		Cover:        Cover{IOFloor: 80, BaselinePath: ".cqb/cover-baseline.json"},
	}
}

func Parse(text []byte) (Config, error) {
	cfg := defaults()
	raw := map[string]any{}
	if len(strings.TrimSpace(string(text))) > 0 {
		if err := yaml.Unmarshal(text, &raw); err != nil {
			return cfg, fmt.Errorf("parse yaml: %w", err)
		}
		if err := yaml.Unmarshal(text, &cfg); err != nil {
			return cfg, fmt.Errorf("parse yaml: %w", err)
		}
	}
	cfg.IgnoredKeys = collectIllegal(raw)
	applyStrictPaths(&cfg, raw)
	if cfg.Complexity.Cognitive == 0 {
		cfg.Complexity.Cognitive = 30
	}
	if cfg.Complexity.Cyclomatic == 0 {
		cfg.Complexity.Cyclomatic = 30
	}
	if cfg.Complexity.NestedIf == 0 {
		cfg.Complexity.NestedIf = 5
	}
	if cfg.Complexity.Delta == 0 {
		cfg.Complexity.Delta = 5
	}
	if cfg.StrictPaths == nil {
		cfg.StrictPaths = []string{}
	}
	if cfg.RedAllowlist == nil {
		cfg.RedAllowlist = []string{}
	}
	if cfg.ExtraHunters == nil {
		cfg.ExtraHunters = []string{}
	}
	return cfg, nil
}

func Load(path string) (Config, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return defaults(), nil
		}
		return Config{}, err
	}
	return Parse(b)
}

func applyStrictPaths(cfg *Config, raw map[string]any) {
	if _, ok := raw["strict_paths"]; ok {
		cfg.StrictPaths = stringSlice(raw["strict_paths"])
		return
	}
	if _, ok := raw["red_allowlist"]; ok {
		cfg.StrictPaths = stringSlice(raw["red_allowlist"])
	}
}

func stringSlice(v any) []string {
	switch t := v.(type) {
	case nil:
		return []string{}
	case []any:
		out := make([]string, 0, len(t))
		for _, x := range t {
			if s, ok := x.(string); ok {
				out = append(out, s)
			}
		}
		return out
	case []string:
		return t
	default:
		return []string{}
	}
}

func PrefixList(c Config) []string {
	var out []string
	switch v := c.Prefix.(type) {
	case string:
		if v != "" {
			out = append(out, v)
		}
	case []any:
		for _, x := range v {
			if s, ok := x.(string); ok && s != "" {
				out = append(out, s)
			}
		}
	}
	out = append(out, c.Prefixes...)
	return out
}

func collectIllegal(v any) []string {
	seen := map[string]bool{}
	var walk func(any)
	walk = func(node any) {
		m, ok := node.(map[string]any)
		if !ok {
			if arr, ok := node.([]any); ok {
				for _, it := range arr {
					walk(it)
				}
			}
			return
		}
		for k, child := range m {
			for _, ill := range IllegalKeys {
				if k == ill {
					seen[k] = true
				}
			}
			walk(child)
		}
	}
	walk(v)
	var out []string
	for _, k := range IllegalKeys {
		if seen[k] {
			out = append(out, k)
		}
	}
	return out
}
