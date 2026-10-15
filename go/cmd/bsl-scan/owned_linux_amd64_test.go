//go:build linux && amd64

package main

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"sync"
	"syscall"
	"testing"
)

func TestOwnedFilterNativeHelper(t *testing.T) {
	if os.Getenv("RENTGEN_OWNED_FILTER_HELPER") != "1" {
		return
	}
	runtime.LockOSThread()
	if err := ownedSetup(os.Getppid(), 3000); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	for _, number := range []uintptr{syscall.SYS_FORK, syscall.SYS_VFORK, syscall.SYS_CLONE, syscall.SYS_EXECVE, 322, syscall.SYS_UNSHARE, 308} {
		_, _, err := syscall.RawSyscall6(number, 0, 0, 0, 0, 0, 0)
		if err != syscall.EPERM {
			fmt.Fprintf(os.Stderr, "syscall %d: %v", number, err)
			os.Exit(3)
		}
	}
	_, _, err := syscall.RawSyscall6(435, 0, 0, 0, 0, 0, 0)
	if err != syscall.ENOSYS {
		os.Exit(4)
	}
	// Force runtime thread creation after TSYNC; threads are allowed, processes aren't.
	var ready, done sync.WaitGroup
	ready.Add(32)
	done.Add(32)
	release := make(chan bool)
	for i := 0; i < 32; i++ {
		go func() { runtime.LockOSThread(); ready.Done(); <-release; done.Done() }()
	}
	ready.Wait()
	close(release)
	done.Wait()
	fmt.Print("owned-filter-ok")
	os.Exit(0)
}

func TestOwnedNativeFilterRejectsAllIndependentProcessCreation(t *testing.T) {
	command := exec.Command(os.Args[0], "-test.run=^TestOwnedFilterNativeHelper$")
	command.Env = append(os.Environ(), "RENTGEN_OWNED_FILTER_HELPER=1")
	output, err := command.CombinedOutput()
	if err != nil || string(output) != "owned-filter-ok" {
		t.Fatalf("filter: %v %s", err, output)
	}
}
