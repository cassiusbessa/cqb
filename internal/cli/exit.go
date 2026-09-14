package cli

import "fmt"

// ExitError is a process exit code from `cqb run`.
// Code 1 when the bundle has red, or on --mode push when implied e2e is unavailable.
type ExitError struct {
	Code int
}

func (e *ExitError) Error() string {
	return fmt.Sprintf("exit %d", e.Code)
}
