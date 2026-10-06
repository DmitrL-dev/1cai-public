//go:build linux

package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	"1cai/bsl-scan/internal/sourcefacts"
)

// Helpers execute this test binary, never a compiler or an external source
// program. Source bytes travel only over the controlled stdin pipe.
func helperCommand(ctx context.Context, mode string, args ...string) *exec.Cmd {
	argv := []string{"-test.run=^TestProcessHelper$", "--"}
	argv = append(argv, args...)
	cmd := exec.CommandContext(ctx, os.Args[0], argv...)
	cmd.Env = append(os.Environ(), "RENTGEN_SOURCE_FACT_TEST_HELPER="+mode)
	return cmd
}

func TestProcessHelper(t *testing.T) {
	mode := os.Getenv("RENTGEN_SOURCE_FACT_TEST_HELPER")
	if mode == "" {
		return
	}
	switch mode {
	case "scanner":
		for i, a := range os.Args {
			if a == "--" {
				os.Exit(run(os.Args[i+1:]))
			}
		}
		os.Exit(2)
	case "owner":
		parentDeathOwner()
	case "supervisor":
		parentDeathSupervisor()
	default:
		os.Exit(2)
	}
}

func readFrame(in io.Reader) ([]byte, error) {
	var prefix [4]byte
	if _, err := io.ReadFull(in, prefix[:]); err != nil {
		return nil, err
	}
	n := binary.LittleEndian.Uint32(prefix[:])
	if n > sourcefacts.MaxResponseBytes {
		return nil, fmt.Errorf("oversize")
	}
	raw := make([]byte, n)
	_, err := io.ReadFull(in, raw)
	return raw, err
}
func framed(raw []byte) []byte {
	out := make([]byte, 4+len(raw))
	binary.LittleEndian.PutUint32(out, uint32(len(raw)))
	copy(out[4:], raw)
	return out
}
func validRequest() []byte {
	source := []byte("Procedure Caller()\nR.Target();\nEndProcedure\nProcedure Target() Export\nEndProcedure")
	sum := sha256.Sum256(source)
	start := bytes.Index(source, []byte("R.Target"))
	raw, _ := json.Marshal(map[string]any{
		"protocol":  sourcefacts.Protocol,
		"caller":    map[string]any{"entry_id": 0, "size_bytes": len(source), "raw_sha256": hex.EncodeToString(sum[:]), "data_base64": base64.StdEncoding.EncodeToString(source)},
		"candidate": map[string]any{"kind": "same_as_caller"},
		"selection": map[string]any{"start": start, "end": start + len("R.Target")},
	})
	return raw
}

func TestOwnershipHandshakeAndEOF(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	cmd := helperCommand(ctx, "scanner", "--parent-pid", strconv.Itoa(os.Getpid()))
	in, err := cmd.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	out, err := cmd.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() {
		if cmd.ProcessState == nil {
			_ = cmd.Process.Kill()
			_ = cmd.Wait()
		}
	}()
	hello, err := readFrame(out)
	if err != nil || string(hello) != sourcefacts.Hello {
		t.Fatal("ownership hello failed")
	}
	if _, err := in.Write(framed(validRequest())); err != nil {
		t.Fatal(err)
	}
	// A full request without EOF cannot produce a response. Leave the owner
	// alive while runtime GC/scheduling occur before completing the exchange.
	type result struct {
		raw []byte
		err error
	}
	response := make(chan result, 1)
	go func() { raw, err := readFrame(out); response <- result{raw, err} }()
	select {
	case <-response:
		t.Fatal("response before stdin EOF")
	case <-time.After(75 * time.Millisecond):
	}
	if err := in.Close(); err != nil {
		t.Fatal(err)
	}
	select {
	case got := <-response:
		if got.err != nil || !bytes.Contains(got.raw, []byte(`"status":"ok"`)) {
			t.Fatal("response failed")
		}
	case <-ctx.Done():
		t.Fatal("exchange timed out")
	}
	if tail, err := io.ReadAll(out); err != nil || len(tail) != 0 {
		t.Fatal("trailing stdout")
	}
	if err := cmd.Wait(); err != nil {
		t.Fatal("nonzero exit")
	}
	if stderr.Len() != 0 {
		t.Fatal("unexpected stderr")
	}
}

func TestPreHelloFailureDoesNotReadSource(t *testing.T) {
	for _, args := range [][]string{{"--parent-pid", "1"}, {"--parent-pid", "2147483647"}, {"--parent-pid", "+2"}, {"--source", "PRIVATE_ARG_CANARY"}} {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		cmd := helperCommand(ctx, "scanner", args...)
		in, err := cmd.StdinPipe()
		if err != nil {
			cancel()
			t.Fatal(err)
		}
		var out, stderr bytes.Buffer
		cmd.Stdout = &out
		cmd.Stderr = &stderr
		if err := cmd.Start(); err != nil {
			cancel()
			t.Fatal(err)
		}
		// Keep input open and empty. Setup failures must exit without reading it.
		err = cmd.Wait()
		_ = in.Close()
		cancel()
		if exit, ok := err.(*exec.ExitError); !ok || exit.ExitCode() != 2 {
			t.Fatal("setup failure did not exit 2")
		}
		if out.Len() != 0 || stderr.Len() != 0 {
			t.Fatal("pre-hello setup disclosed output")
		}
	}
}

func TestProcessPartialTrailingAndPrivacy(t *testing.T) {
	valid := framed(validRequest())
	for _, input := range [][]byte{valid[:3], valid[:len(valid)-1], append(append([]byte(nil), valid...), 1), framed([]byte(`{"PRIVATE_WIRE_CANARY":true}`))} {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		cmd := helperCommand(ctx, "scanner", "--parent-pid", strconv.Itoa(os.Getpid()))
		cmd.Stdin = bytes.NewReader(input)
		var out, stderr bytes.Buffer
		cmd.Stdout = &out
		cmd.Stderr = &stderr
		err := cmd.Run()
		cancel()
		if exit, ok := err.(*exec.ExitError); !ok || exit.ExitCode() != 2 {
			t.Fatal("bad wire did not exit 2")
		}
		if hello, err := readFrame(&out); err != nil || string(hello) != sourcefacts.Hello {
			t.Fatal("missing hello")
		}
		response, err := readFrame(&out)
		if err != nil || !bytes.Equal(response, sourcefacts.ErrorResponse(sourcefacts.InvalidRequest)) {
			t.Fatal("wrong closed error")
		}
		if out.Len() != 0 || stderr.Len() != 0 || bytes.Contains(response, []byte("PRIVATE_")) {
			t.Fatal("privacy/trailing-output failure")
		}
	}
}

func TestParentDeathKillsLockedOwnershipThread(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	cmd := helperCommand(ctx, "supervisor")
	output, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("parent-death helper failed: %v (%s)", err, output)
	}
	if len(output) != 0 {
		t.Fatal("parent-death helpers emitted unexpected output")
	}
}

func parentDeathOwner() {
	runtime.LockOSThread() // Keep the actual launching Linux task alive, too.
	// fd 3 is a dedicated test-only PID channel. The product scanner does not
	// inherit it; only this launcher owns the extra descriptor.
	control := os.NewFile(3, "test-control")
	if control == nil {
		os.Exit(21)
	}
	readEnd, writeEnd, err := os.Pipe()
	if err != nil {
		os.Exit(22)
	}
	defer readEnd.Close()
	defer writeEnd.Close()
	cmd := helperCommand(context.Background(), "scanner", "--parent-pid", strconv.Itoa(os.Getpid()))
	cmd.Stdin = readEnd
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		os.Exit(23)
	}
	if _, err := fmt.Fprintf(control, "%d\n", cmd.Process.Pid); err != nil {
		_ = cmd.Process.Kill()
		_ = cmd.Wait()
		os.Exit(24)
	}
	_ = control.Close()
	go func() { _ = cmd.Wait(); os.Exit(25) }()
	// Live launching thread/process and live stdin until explicitly killed.
	for {
		runtime.GC()
		time.Sleep(5 * time.Millisecond)
	}
}

func parentDeathSupervisor() {
	// Only this disposable test helper becomes a subreaper. It can then reap
	// the precise orphaned scanner and verify SIGKILL rather than guess from
	// disappearance or a potentially reused PID. Product code never does this.
	const prSetChildSubreaper = 36
	_, _, errno := syscall.RawSyscall6(syscall.SYS_PRCTL, prSetChildSubreaper, 1, 0, 0, 0, 0)
	if errno != 0 {
		os.Exit(31)
	}
	controlR, controlW, err := os.Pipe()
	if err != nil {
		os.Exit(32)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	owner := helperCommand(ctx, "owner")
	owner.ExtraFiles = []*os.File{controlW}
	out, err := owner.StdoutPipe()
	if err != nil {
		os.Exit(33)
	}
	owner.Stderr = io.Discard
	if err := owner.Start(); err != nil {
		os.Exit(34)
	}
	_ = controlW.Close()
	pidRaw, err := io.ReadAll(io.LimitReader(controlR, 64))
	_ = controlR.Close()
	if err != nil {
		_ = owner.Process.Kill()
		_ = owner.Wait()
		os.Exit(35)
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(pidRaw)))
	if err != nil || pid <= 1 {
		_ = owner.Process.Kill()
		_ = owner.Wait()
		os.Exit(36)
	}
	hello, err := readFrame(out)
	if err != nil || string(hello) != sourcefacts.Hello {
		_ = owner.Process.Kill()
		_ = owner.Wait()
		os.Exit(37)
	}
	// Exercise scheduling/GC with the scanner blocked on stdin, long enough
	// that ownership installed on a transient worker would be exposed.
	time.Sleep(100 * time.Millisecond)
	if err := owner.Process.Kill(); err != nil {
		_ = owner.Wait()
		os.Exit(38)
	}
	err = owner.Wait()
	exit, ok := err.(*exec.ExitError)
	if !ok {
		os.Exit(42)
	}
	ownerStatus, ok := exit.Sys().(syscall.WaitStatus)
	if !ok || !ownerStatus.Signaled() || ownerStatus.Signal() != syscall.SIGKILL {
		os.Exit(43)
	}
	deadline := time.Now().Add(1500 * time.Millisecond)
	for {
		var status syscall.WaitStatus
		got, err := syscall.Wait4(pid, &status, syscall.WNOHANG, nil)
		if err != nil {
			os.Exit(39)
		}
		if got == pid {
			if !status.Signaled() || status.Signal() != syscall.SIGKILL {
				os.Exit(40)
			}
			os.Exit(0)
		}
		if time.Now().After(deadline) {
			// The child remains ours and unreaped, so this PID cannot be reused.
			_ = syscall.Kill(pid, syscall.SIGKILL)
			_, _ = syscall.Wait4(pid, &status, 0, nil)
			os.Exit(41)
		}
		time.Sleep(5 * time.Millisecond)
	}
}
