package cqb

import "embed"

// Content is the vendored engine and Cursor/hook templates shipped in the binary.
//
//go:embed engine templates
var Content embed.FS
