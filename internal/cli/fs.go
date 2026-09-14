package cli

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	cqb "github.com/cassiusbessa/cqb"
)

func copyFS(dstRoot, prefix string) error {
	return fs.WalkDir(cqb.Content, prefix, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel := strings.TrimPrefix(p, prefix)
		rel = strings.TrimPrefix(rel, "/")
		target := filepath.Join(dstRoot, filepath.FromSlash(rel))
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		b, err := fs.ReadFile(cqb.Content, p)
		if err != nil {
			return err
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return err
		}
		mode := os.FileMode(0o644)
		if strings.Contains(p, "hook/") || strings.HasSuffix(p, "pre-push") {
			mode = 0o755
		}
		return os.WriteFile(target, b, mode)
	})
}

func CopyEngine(consumerRoot string) error {
	dst := filepath.Join(consumerRoot, ".cqb", "engine")
	if err := os.MkdirAll(dst, 0o755); err != nil {
		return err
	}
	return copyFS(dst, "engine")
}

func CopyHook(consumerRoot string) error {
	dst := filepath.Join(consumerRoot, ".cqb", "hooks")
	if err := os.MkdirAll(dst, 0o755); err != nil {
		return err
	}
	b, err := fs.ReadFile(cqb.Content, "templates/hook/pre-push")
	if err != nil {
		return err
	}
	target := filepath.Join(dst, "pre-push")
	return os.WriteFile(target, b, 0o755)
}

func CopyTemplates(consumerRoot string) error {
	dst := filepath.Join(consumerRoot, ".cqb", "templates")
	if err := os.MkdirAll(dst, 0o755); err != nil {
		return err
	}
	return copyFS(dst, "templates")
}

type CopyAction struct {
	Dest   string
	Action string // "write" | "skip"
}

func skillMappings() [][2]string {
	return [][2]string{
		{"templates/review/cqb/SKILL.md", ".cursor/skills/cqb/SKILL.md"},
		{"templates/review/cqb-setup/SKILL.md", ".cursor/skills/cqb-setup/SKILL.md"},
		{"templates/review/commands/cqb.md", ".cursor/commands/cqb.md"},
		{"templates/review/commands/cqb-setup.md", ".cursor/commands/cqb-setup.md"},
	}
}

func SetupCopy(consumerRoot string, dryRun bool) ([]CopyAction, error) {
	var acts []CopyAction
	for _, pair := range skillMappings() {
		src, destRel := pair[0], pair[1]
		dest := filepath.Join(consumerRoot, filepath.FromSlash(destRel))
		if _, err := os.Stat(dest); err == nil {
			acts = append(acts, CopyAction{Dest: destRel, Action: "skip"})
			continue
		}
		acts = append(acts, CopyAction{Dest: destRel, Action: "write"})
		if dryRun {
			continue
		}
		b, err := fs.ReadFile(cqb.Content, src)
		if err != nil {
			return acts, err
		}
		if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
			return acts, err
		}
		if err := os.WriteFile(dest, b, 0o644); err != nil {
			return acts, err
		}
	}
	return acts, nil
}

func DefaultYAML() ([]byte, error) {
	return fs.ReadFile(cqb.Content, "templates/cqb.yaml.default")
}

func ReaderTemplate() ([]byte, error) {
	return fs.ReadFile(cqb.Content, "templates/review/bundle-reader/SKILL.md.tmpl")
}

func WriteReader(consumerRoot string, body string) error {
	dest := filepath.Join(consumerRoot, ".cursor", "skills", "cqb-bundle-reader", "SKILL.md")
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return err
	}
	return os.WriteFile(dest, []byte(body), 0o644)
}

func HelpText() string {
	return fmt.Sprintf(`cqb — local quality gate and code-review kit (%s)

Usage:
  cqb help
  cqb version
  cqb init [--dir PATH]
  cqb run [--dir PATH] [--mode uncommitted|staged|file-list|push] [--files a.go,b.go] [--output PATH]
  cqb upgrade [--dir PATH]
  cqb render-reader [--dir PATH] [--out PATH]
  cqb setup-copy [--dir PATH] [--dry-run]

Pinned host tools (go install on init if missing):
  golangci-lint %s
    %s
  gremlins %s
    %s

Opt-in hook: git config core.hooksPath .cqb/hooks
  then CQB=1 git push
  Init never sets core.hooksPath. Yellow never fails git.
`, cqb.KitVersion, cqb.GolangCILintVersion, cqb.GolangCILintInstall, cqb.GremlinsVersion, cqb.GremlinsInstall)
}
