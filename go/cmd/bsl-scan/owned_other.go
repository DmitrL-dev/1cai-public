//go:build !linux || !amd64

package main

import "os"

func runOwned(args []string) bool {
	if len(args) > 0 && args[0] == "--owned-linux-v1" {
		os.Exit(1)
	}
	return false
}
