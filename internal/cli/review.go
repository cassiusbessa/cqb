package cli

import (
	"fmt"
	"os/exec"
	"strings"
)

// ResolveReviewBase picks the merge-base ref for --mode review.
// Order: explicit --base, tracking upstream, unique main xor master.
func ResolveReviewBase(dir, explicit string) (string, error) {
	if s := strings.TrimSpace(explicit); s != "" {
		return s, nil
	}
	if up, ok := gitOutput(dir, "rev-parse", "--abbrev-ref", "@{upstream}"); ok && up != "" && up != "@{upstream}" {
		return up, nil
	}
	hasMain := gitRefExists(dir, "refs/heads/main") || gitRefExists(dir, "refs/remotes/origin/main")
	hasMaster := gitRefExists(dir, "refs/heads/master") || gitRefExists(dir, "refs/remotes/origin/master")
	if hasMain && hasMaster {
		return "", fmt.Errorf("review base is ambiguous (main and master both exist); pass --base <ref>")
	}
	if hasMain {
		if gitRefExists(dir, "refs/heads/main") {
			return "main", nil
		}
		return "origin/main", nil
	}
	if hasMaster {
		if gitRefExists(dir, "refs/heads/master") {
			return "master", nil
		}
		return "origin/master", nil
	}
	return "", fmt.Errorf("could not resolve review base; pass --base <ref>")
}

func gitRefExists(dir, ref string) bool {
	cmd := exec.Command("git", "-C", dir, "show-ref", "--verify", "--quiet", ref)
	return cmd.Run() == nil
}

func gitOutput(dir string, args ...string) (string, bool) {
	cmd := exec.Command("git", append([]string{"-C", dir}, args...)...)
	out, err := cmd.Output()
	if err != nil {
		return "", false
	}
	return strings.TrimSpace(string(out)), true
}
