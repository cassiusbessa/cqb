package main

import (
	"errors"
	"fmt"
	"os"

	"github.com/cassiusbessa/cqb/internal/cli"
)

func main() {
	if err := cli.Run(os.Args[1:]); err != nil {
		var ee *cli.ExitError
		if errors.As(err, &ee) {
			os.Exit(ee.Code)
		}
		fmt.Fprintf(os.Stderr, "cqb: %v\n", err)
		os.Exit(1)
	}
}
