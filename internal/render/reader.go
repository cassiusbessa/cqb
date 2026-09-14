package render

import (
	"strings"

	"github.com/cassiusbessa/cqb/internal/config"
)

func BundleReader(tmpl string, cfg config.Config) string {
	allow := cfg.StrictPaths
	allowText := "_empty_ — no cover red, no hunter red until a human names strict paths."
	if len(allow) > 0 {
		allowText = strings.Join(allow, ", ")
	}
	r := strings.NewReplacer(
		"{{cognitive}}", itoa(cfg.Complexity.Cognitive),
		"{{cyclomatic}}", itoa(cfg.Complexity.Cyclomatic),
		"{{nested_if}}", itoa(cfg.Complexity.NestedIf),
		"{{delta}}", itoa(cfg.Complexity.Delta),
		"{{strict_paths}}", allowText,
		"{{red_allowlist}}", allowText,
	)
	return r.Replace(tmpl)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var neg bool
	if n < 0 {
		neg = true
		n = -n
	}
	var b [16]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}
