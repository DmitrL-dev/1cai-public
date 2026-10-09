//go:build linux

package main

import (
	"runtime"
	"syscall"
	"unsafe"
)

const (
	prSetPdeathsig = 1
	prGetPdeathsig = 2
)

// installOwnership runs on the main goroutine's permanently locked OS thread.
// The only unsafe pointer is the kernel's fixed-size PR_GET_PDEATHSIG output.
// It deliberately neither enumerates nor closes runtime-owned descriptors.
func installOwnership(expectedParent int) bool {
	_, _, errno := syscall.RawSyscall6(syscall.SYS_PRCTL, prSetPdeathsig, uintptr(syscall.SIGKILL), 0, 0, 0, 0)
	if errno != 0 {
		return false
	}
	var installed int32
	_, _, errno = syscall.RawSyscall6(syscall.SYS_PRCTL, prGetPdeathsig, uintptr(unsafe.Pointer(&installed)), 0, 0, 0, 0)
	runtime.KeepAlive(&installed)
	if errno != 0 || installed != int32(syscall.SIGKILL) || syscall.Getppid() != expectedParent {
		return false
	}
	if err := syscall.Setrlimit(syscall.RLIMIT_CORE, &syscall.Rlimit{Cur: 0, Max: 0}); err != nil {
		return false
	}
	var limit syscall.Rlimit
	if err := syscall.Getrlimit(syscall.RLIMIT_CORE, &limit); err != nil || limit.Cur != 0 || limit.Max != 0 {
		return false
	}
	return true
}
