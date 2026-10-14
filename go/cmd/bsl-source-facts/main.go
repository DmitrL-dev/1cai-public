// bsl-source-facts is a Linux-owned, bytes-only, one-shot lexical observer.
// It intentionally shares no scanner modes or extraction code with bsl-scan.
package main

import (
	"os"
	"runtime"
	"runtime/debug"
	"strconv"
	"time"

	"1cai/bsl-scan/internal/sourcefacts"
)

func main() { os.Exit(run(os.Args[1:])) }

func run(args []string) (status int) {
	// Never unlock: Linux parent-death ownership belongs to this OS thread.
	// run returns only to main's immediate os.Exit, not a goroutine pool.
	runtime.LockOSThread()
	defer func() {
		if recover() != nil {
			status = 2
		}
	}()
	debug.SetTraceback("none")
	parent, ok := parentPID(args)
	if !ok || !installOwnership(parent) {
		return 2
	}
	runtime.GOMAXPROCS(1)
	// This is a runtime-compatible soft target, not an OS memory sandbox.
	// Go reserves substantial virtual address space; RLIMIT_AS is not used.
	debug.SetMemoryLimit(64 << 20)
	// Covers blocked stdin/stdout and pure parse work as a second bound. The
	// owner must still enforce its earlier deadline and confirm termination/reap.
	timer := time.AfterFunc(10*time.Second, func() { os.Exit(2) })
	defer timer.Stop()
	return sourcefacts.Serve(os.Stdin, os.Stdout)
}

func parentPID(args []string) (int, bool) {
	if len(args) != 2 || args[0] != "--parent-pid" {
		return 0, false
	}
	s := args[1]
	if s == "" || s[0] < '1' || s[0] > '9' {
		return 0, false
	}
	for i := 1; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return 0, false
		}
	}
	n, err := strconv.ParseUint(s, 10, 31)
	return int(n), err == nil && n > 1
}
