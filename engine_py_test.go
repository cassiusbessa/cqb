package cqb_test

import (
	"os/exec"
	"testing"
)

func TestPythonGate(t *testing.T) {
	cmd := exec.Command("python3", "-m", "unittest", "discover", "-s", "engine/tests", "-v")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("python engine tests: %v\n%s", err, out)
	}
}
