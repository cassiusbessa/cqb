package cqb

// KitVersion is the version recorded in consumer cqb.yaml on init/upgrade.
const KitVersion = "0.1.0"

// Pinned host tools installed by `cqb init` via `go install`.
const (
	GolangCILintVersion = "v2.4.0"
	GremlinsVersion     = "v0.5.1"

	GolangCILintInstall = "github.com/golangci/golangci-lint/v2/cmd/golangci-lint@" + GolangCILintVersion
	GremlinsInstall     = "github.com/go-gremlins/gremlins/cmd/gremlins@" + GremlinsVersion
)

// HookEnvFlag is the documented opt-in environment variable for the pre-push hook.
const HookEnvFlag = "CQB"
