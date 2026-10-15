//go:build linux && amd64

package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"runtime"
	"runtime/debug"
	"strconv"
	"syscall"
	"unsafe"

	"1cai/bsl-scan/internal/scanner"
)

const ownedProtocol = "rentgen-owned-scanner-linux-v1"

// This is a fixed scanner entry, not an arbitrary executable launcher.
func runOwned(args []string) bool {
	if len(args) == 0 || args[0] != "--owned-linux-v1" {
		return false
	}
	if err := ownedMain(args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "owned_scanner_failed")
		os.Exit(1)
	}
	return true
}

func ownedMain(args []string) error {
	if len(args) != 14 {
		return fmt.Errorf("options")
	}
	values := make([]uint64, len(args))
	for i, arg := range args {
		n, err := strconv.ParseUint(arg, 10, 63)
		if err != nil || strconv.FormatUint(n, 10) != arg || n == 0 {
			return fmt.Errorf("options")
		}
		values[i] = n
	}
	parent, root, coverage, hello, image := int(values[0]), int(values[1]), int(values[2]), int(values[3]), int(values[4])
	seen := map[int]bool{}
	for _, fd := range []int{root, coverage, hello, image} {
		if fd <= 2 || fd > 1<<20 || seen[fd] {
			return fmt.Errorf("fds")
		}
		seen[fd] = true
	}
	if values[5] > 120000 || values[6] > 64<<20 || values[7] > 1<<30 || values[8] > 100000 || values[9] > 200000 || values[10] > 128 || values[11] > 128<<20 || values[12] > 64<<20 || values[13] > 4<<30 {
		return fmt.Errorf("limits")
	}
	for _, fd := range []int{coverage, hello} {
		var info syscall.Stat_t
		if syscall.Fstat(fd, &info) != nil || info.Mode&syscall.S_IFMT != syscall.S_IFIFO {
			return fmt.Errorf("pipe")
		}
	}
	if err := scanner.OwnedPrivate(root, true); err != nil {
		return err
	}
	if err := syscall.Close(image); err != nil {
		return err
	}
	// PDEATHSIG belongs to a task. Keep this Go goroutine on that task for its
	// entire lifetime; the creating Python thread must also stay alive.
	runtime.LockOSThread()
	if err := ownedSetup(parent, values[5]); err != nil {
		return err
	}
	debug.SetMemoryLimit(int64(values[13])) // A soft Go GC target, never a hard RSS cap.
	handshake := os.NewFile(uintptr(hello), "owned-hello")
	if handshake == nil {
		return fmt.Errorf("hello")
	}
	_, err := fmt.Fprintf(handshake, "%s %d %d\n", ownedProtocol, os.Getpid(), parent)
	closeErr := handshake.Close()
	if err != nil || closeErr != nil {
		return fmt.Errorf("hello")
	}
	var gate [2]byte
	n, err := io.ReadFull(os.Stdin, gate[:1])
	if err != nil || n != 1 || gate[0] != 'G' {
		return fmt.Errorf("gate")
	}
	if err := os.Stdin.Close(); err != nil {
		return err
	}
	functions, report, err := scanner.ScanCallGraphOwned(root, scanner.OwnedLimits{
		MaxFile: int64(values[6]), MaxBytes: int64(values[7]), MaxFiles: int(values[8]), MaxEntries: int(values[9]), MaxDepth: int(values[10]),
	})
	if err != nil {
		return err
	}
	stdout := &ownedWriter{stream: os.Stdout, remaining: int64(values[11])}
	for _, record := range functions {
		if err := json.NewEncoder(stdout).Encode(record); err != nil {
			return err
		}
	}
	output := os.NewFile(uintptr(coverage), "owned-coverage")
	if output == nil {
		return fmt.Errorf("coverage")
	}
	writer := &ownedWriter{stream: output, remaining: int64(values[12])}
	_, err = io.WriteString(writer, "{\"format_version\":1,\"files\":[")
	for index, record := range report {
		if err != nil {
			break
		}
		if index > 0 {
			_, err = io.WriteString(writer, ",")
		}
		if err == nil {
			err = json.NewEncoder(writer).Encode(record)
		}
	}
	if err == nil {
		_, err = io.WriteString(writer, "]}\n")
	}
	closeErr = output.Close()
	if err != nil {
		return err
	}
	return closeErr
}

type ownedWriter struct {
	stream    io.Writer
	remaining int64
}

func (w *ownedWriter) Write(raw []byte) (int, error) {
	if int64(len(raw)) > w.remaining {
		return 0, fmt.Errorf("output_limit")
	}
	n, err := w.stream.Write(raw)
	w.remaining -= int64(n)
	return n, err
}

func ownedSetup(parent int, milliseconds uint64) error {
	prctl := func(option, argument uintptr) error {
		_, _, code := syscall.RawSyscall6(syscall.SYS_PRCTL, option, argument, 0, 0, 0, 0)
		if code != 0 {
			return code
		}
		return nil
	}
	if err := prctl(1, uintptr(syscall.SIGKILL)); err != nil {
		return err
	} // PR_SET_PDEATHSIG
	if parent <= 1 || syscall.Getppid() != parent {
		return fmt.Errorf("parent")
	}
	if err := prctl(38, 1); err != nil {
		return err
	} // PR_SET_NO_NEW_PRIVS
	if err := prctl(4, 0); err != nil {
		return err
	} // PR_SET_DUMPABLE
	if err := ownedTimer(milliseconds); err != nil {
		return err
	}
	program := ownedFilter()
	filter := syscall.SockFprog{Len: uint16(len(program)), Filter: &program[0]}
	// seccomp(SECCOMP_SET_MODE_FILTER, TSYNC, ...): positive TID is failure too.
	result, _, code := syscall.RawSyscall(317, 1, 1, uintptr(unsafe.Pointer(&filter)))
	runtime.KeepAlive(program)
	if code != 0 {
		return code
	}
	if result != 0 {
		return fmt.Errorf("tsync")
	}
	if syscall.Getppid() != parent {
		return fmt.Errorf("parent")
	}
	return nil
}

// Linux/amd64 UAPI sigevent is 64 bytes; sigval at 0, signo at 8, notify at 12.
// Kernel monotonic SIGKILL remains effective while Go or a pipe syscall blocks.
func ownedTimer(milliseconds uint64) error {
	if milliseconds == 0 || milliseconds > 120000 {
		return fmt.Errorf("deadline")
	}
	event := struct {
		Value   uint64
		Signal  int32
		Notify  int32
		Padding [48]byte
	}{Signal: int32(syscall.SIGKILL)}
	var identifier int32
	_, _, code := syscall.RawSyscall(222, 1, uintptr(unsafe.Pointer(&event)), uintptr(unsafe.Pointer(&identifier))) // CLOCK_MONOTONIC, SIGEV_SIGNAL
	if code != 0 {
		return code
	}
	timer := struct {
		Interval syscall.Timespec
		Value    syscall.Timespec
	}{Value: syscall.NsecToTimespec(int64(milliseconds) * 1000000)}
	_, _, code = syscall.RawSyscall6(223, uintptr(identifier), 0, uintptr(unsafe.Pointer(&timer)), 0, 0, 0)
	if code != 0 {
		return code
	}
	return nil
}

func ownedFilter() []syscall.SockFilter {
	const deny = 0x00050000 | uint32(syscall.EPERM)
	program := []syscall.SockFilter{
		{Code: 0x20, K: 4}, {Code: 0x15, Jt: 1, K: 0xc000003e}, {Code: 0x06, K: 0x80000000},
		{Code: 0x20, K: 0}, {Code: 0x45, Jf: 1, K: 0x40000000}, {Code: 0x06, K: 0x80000000},
		{Code: 0x15, Jf: 4, K: syscall.SYS_CLONE}, {Code: 0x20, K: 16},
		{Code: 0x45, Jt: 1, K: syscall.CLONE_THREAD}, {Code: 0x06, K: deny}, {Code: 0x06, K: 0x7fff0000},
		{Code: 0x15, Jf: 1, K: 435}, {Code: 0x06, K: 0x00050000 | uint32(syscall.ENOSYS)}, // clone3 -> safe clone fallback
	}
	for _, number := range []uint32{syscall.SYS_FORK, syscall.SYS_VFORK, syscall.SYS_EXECVE, 322, syscall.SYS_UNSHARE, 308} {
		program = append(program, syscall.SockFilter{Code: 0x15, Jf: 1, K: number}, syscall.SockFilter{Code: 0x06, K: deny})
	}
	return append(program, syscall.SockFilter{Code: 0x06, K: 0x7fff0000})
}
