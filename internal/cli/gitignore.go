package cli

import (
	"os"
	"path/filepath"
	"strings"
)

const (
	gitignoreBegin = "# cqb begin"
	gitignoreEnd   = "# cqb end"
)

// GitignoreManagedBlock is the idempotent ignore region written by init.
func GitignoreManagedBlock() string {
	return strings.Join([]string{
		gitignoreBegin,
		".quality/",
		".cqb/scan.json",
		".cqb/work/",
		"*.coverprofile",
		".cqb/**/__pycache__/",
		gitignoreEnd,
	}, "\n")
}

func UpsertGitignore(dir string) error {
	path := filepath.Join(dir, ".gitignore")
	existing := ""
	if b, err := os.ReadFile(path); err == nil {
		existing = string(b)
	} else if !os.IsNotExist(err) {
		return err
	}
	return os.WriteFile(path, []byte(upsertGitignoreText(existing)), 0o644)
}

func upsertGitignoreText(existing string) string {
	block := GitignoreManagedBlock()
	begin := strings.Index(existing, gitignoreBegin)
	end := strings.Index(existing, gitignoreEnd)
	if begin >= 0 && end >= begin {
		end += len(gitignoreEnd)
		prefix := strings.TrimRight(existing[:begin], "\n")
		suffix := strings.TrimLeft(existing[end:], "\n")
		var b strings.Builder
		if prefix != "" {
			b.WriteString(prefix)
			b.WriteString("\n\n")
		}
		b.WriteString(block)
		b.WriteString("\n")
		if suffix != "" {
			b.WriteString(suffix)
			if !strings.HasSuffix(suffix, "\n") {
				b.WriteString("\n")
			}
		}
		return b.String()
	}
	if strings.TrimSpace(existing) == "" {
		return block + "\n"
	}
	return strings.TrimRight(existing, "\n") + "\n\n" + block + "\n"
}
