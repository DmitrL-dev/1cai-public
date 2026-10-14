package main

// Recovery replacement authored on 2026-10-05 from the frozen public protocol.
// These are new tests, not recovered bytes of the lost main_test.go. They cover
// only the CLI transport; independent parent-death tests live outside this file.

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"reflect"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"
)

const recoveryChildEnv = "RENTGEN_RECOVERY_CLI_TEST_CHILD"

// Re-execution exercises the real main -> run -> Serve path. The marker and
// testing flags belong only to this harness and are removed before main runs.
// The helper creates no descendants; no BSL bytes enter its argv or environment.
func TestRecoveryCLIProcess(t *testing.T) {
	if os.Getenv(recoveryChildEnv) != "1" {
		return
	}
	for i, arg := range os.Args {
		if arg == "--" {
			os.Args = append([]string{"bsl-source-facts"}, os.Args[i+1:]...)
			main()
			os.Exit(97)
		}
	}
	os.Exit(98)
}

func TestRecoveryCLIRejectsArgumentsBeforeHello(t *testing.T) {
	pid := strconv.Itoa(os.Getpid())
	cases := []struct {
		name string
		args []string
	}{
		{"missing", nil},
		{"missing_value", []string{"--parent-pid"}},
		{"unknown_flag", []string{"--parent", pid}},
		{"equals_form", []string{"--parent-pid=" + pid}},
		{"extra_argument", []string{"--parent-pid", pid, "extra"}},
		{"duplicate_flag", []string{"--parent-pid", pid, "--parent-pid", pid}},
		{"help_is_not_an_entry_point", []string{"--help"}},
		{"empty", []string{"--parent-pid", ""}},
		{"zero", []string{"--parent-pid", "0"}},
		{"one", []string{"--parent-pid", "1"}},
		{"leading_zero", []string{"--parent-pid", "0" + pid}},
		{"plus", []string{"--parent-pid", "+" + pid}},
		{"minus", []string{"--parent-pid", "-" + pid}},
		{"whitespace", []string{"--parent-pid", pid + " "}},
		{"non_ascii_digits", []string{"--parent-pid", "１２"}},
		{"overflow", []string{"--parent-pid", "2147483648"}},
		{"wrong_actual_parent", []string{"--parent-pid", strconv.Itoa(os.Getpid() + 1)}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			p := recoveryStart(t, tc.args)
			// Keep stdin open and empty: setup/argv rejection must not wait for it.
			p.finish(t, 2)
		})
	}
}

func TestRecoveryCLICompleteRequestRequiresEOF(t *testing.T) {
	p := recoveryStart(t, []string{"--parent-pid", strconv.Itoa(os.Getpid())})
	p.hello(t) // No request byte has been written yet.
	request, want := recoveryFixture()
	framed := recoveryFrame(request)
	p.write(t, framed[:2])
	p.quiet(t) // A partial prefix cannot produce a successful response.
	p.write(t, framed[2:])
	p.quiet(t) // Even a complete valid frame must wait for stdin EOF.
	p.closeInput(t)
	recoveryEqualJSON(t, p.frame(t, 65536), want)
	p.finish(t, 0)
}

func TestRecoveryCLIRejectsMalformedFrames(t *testing.T) {
	request, _ := recoveryFixture()
	valid := recoveryFrame(request)
	cases := []struct {
		name string
		wire []byte
		code string
	}{
		{"empty_input", nil, "invalid_request"},
		{"partial_prefix", []byte{1, 0, 0}, "invalid_request"},
		{"empty_frame", recoveryPrefix(0), "invalid_request"},
		{"oversized_prefix_without_allocation", recoveryPrefix(1500001), "input_limit"},
		{"partial_payload", valid[:len(valid)-1], "invalid_request"},
		{"trailing_byte", append(append([]byte(nil), valid...), '\n'), "invalid_request"},
		{"second_frame", append(append([]byte(nil), valid...), valid...), "invalid_request"},
		{"malformed_json", recoveryFrame([]byte("{")), "invalid_request"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			p := recoveryStart(t, []string{"--parent-pid", strconv.Itoa(os.Getpid())})
			p.hello(t)
			p.write(t, tc.wire)
			p.closeInput(t)
			want := []byte(`{"protocol":"source_fact_scan_v1","status":"error","code":"` + tc.code + `"}`)
			recoveryEqualJSON(t, p.frame(t, 65536), want)
			p.finish(t, 2)
		})
	}
}

// Both complete Buffer records and all expected spans are independently written
// from the public contract. The production evaluator is never the test oracle.
func recoveryFixture() ([]byte, []byte) {
	caller := []byte("Procedure Caller()\n    Probe.DoWork();\nEndProcedure\n")
	candidate := []byte("Procedure DoWork() Export\nEndProcedure\n")
	callerHash := fmt.Sprintf("%x", sha256.Sum256(caller))
	candidateHash := fmt.Sprintf("%x", sha256.Sum256(candidate))
	request := fmt.Sprintf(`{"protocol":"source_fact_scan_v1","caller":{"entry_id":0,"size_bytes":52,"raw_sha256":"%s","data_base64":"%s"},"candidate":{"kind":"distinct_entry","buffer":{"entry_id":1,"size_bytes":39,"raw_sha256":"%s","data_base64":"%s"}},"selection":{"start":23,"end":35}}`,
		callerHash, base64.StdEncoding.EncodeToString(caller), candidateHash, base64.StdEncoding.EncodeToString(candidate))
	want := fmt.Sprintf(`{"protocol":"source_fact_scan_v1","status":"ok","caller":{"entry_id":0,"size_bytes":52,"raw_sha256":"%s","admission":{"state":"admitted"}},"candidate":{"entry_id":1,"size_bytes":39,"raw_sha256":"%s","admission":{"state":"admitted"}},"selector":{"state":"observed","entry_id":0,"routine_span":{"start":0,"end":51},"selector_span":{"start":23,"end":35},"receiver_span":{"start":23,"end":28},"method_span":{"start":29,"end":35}},"header":{"state":"observed","entry_id":1,"routine_span":{"start":0,"end":38},"header_span":{"start":0,"end":25},"name_span":{"start":10,"end":16},"export":true,"export_span":{"start":19,"end":25}}}`,
		callerHash, candidateHash)
	return []byte(request), []byte(want)
}

func recoveryPrefix(n uint32) []byte {
	b := make([]byte, 4)
	binary.LittleEndian.PutUint32(b, n)
	return b
}

func recoveryFrame(raw []byte) []byte {
	return append(recoveryPrefix(uint32(len(raw))), raw...)
}

// Stderr is counted and discarded, never copied into test output or retained.
// The independent reader drains at most 65,537 bytes to detect the 65,536 cap.
type recoveryDiscard struct{ count int }

func (d *recoveryDiscard) Write(p []byte) (int, error) {
	remaining := 65537 - d.count
	if len(p) < remaining {
		d.count += len(p)
	} else {
		d.count = 65537
	}
	return len(p), nil
}

type recoveryChild struct {
	cmd        *exec.Cmd
	in         *os.File
	out        *os.File
	stderr     *recoveryDiscard
	stderrDone chan error
	done       chan error
	reaped     bool
}

func recoveryStart(t *testing.T, args []string) *recoveryChild {
	t.Helper()
	if runtime.GOOS != "linux" {
		t.Skip("the frozen CLI ownership/transport contract is Linux-only")
	}
	exe, err := os.Executable()
	if err != nil {
		t.Fatal("cannot locate test executable")
	}
	// Linux parent-death ownership is thread-sensitive. Keep this launching
	// thread alive until cleanup has confirmed the exact child's reap.
	runtime.LockOSThread()
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	p := &recoveryChild{
		stderr: &recoveryDiscard{}, stderrDone: make(chan error, 1), done: make(chan error, 1),
	}
	var files []*os.File
	t.Cleanup(func() {
		cancel()
		if p.cmd != nil && p.cmd.Process != nil && !p.reaped {
			// No names, process groups, or separately looked-up/reused PIDs.
			_ = p.cmd.Process.Kill()
			select {
			case <-p.done:
				p.reaped = p.cmd.ProcessState != nil
			case <-time.After(2 * time.Second):
			}
			if !p.reaped {
				t.Error("cleanup could not confirm owned child reap")
			}
		}
		for _, f := range files {
			_ = f.Close()
		}
		runtime.UnlockOSThread()
	})
	childIn, parentIn, err := os.Pipe()
	if err != nil {
		t.Fatal("cannot create child stdin")
	}
	files = append(files, childIn, parentIn)
	parentOut, childOut, err := os.Pipe()
	if err != nil {
		t.Fatal("cannot create child stdout")
	}
	files = append(files, parentOut, childOut)
	parentErr, childErr, err := os.Pipe()
	if err != nil {
		t.Fatal("cannot create child stderr")
	}
	files = append(files, parentErr, childErr)
	if err := parentErr.SetReadDeadline(time.Now().Add(12 * time.Second)); err != nil {
		t.Fatal("cannot bound stderr drain")
	}
	p.in, p.out = parentIn, parentOut
	argv := append([]string{"-test.run=^TestRecoveryCLIProcess$", "--"}, args...)
	p.cmd = exec.CommandContext(ctx, exe, argv...)
	for _, e := range os.Environ() {
		if !strings.HasPrefix(e, recoveryChildEnv+"=") {
			p.cmd.Env = append(p.cmd.Env, e)
		}
	}
	p.cmd.Env = append(p.cmd.Env, recoveryChildEnv+"=1")
	p.cmd.Stdin, p.cmd.Stdout, p.cmd.Stderr = childIn, childOut, childErr
	if err := p.cmd.Start(); err != nil {
		t.Fatal("cannot launch CLI test child")
	}
	go func() { p.done <- p.cmd.Wait() }()
	go func() {
		n, err := io.Copy(p.stderr, io.LimitReader(parentErr, 65537))
		if n > 65536 {
			err = errors.New("stderr bound exceeded")
		}
		p.stderrDone <- err
	}()
	_ = childIn.Close()
	_ = childOut.Close()
	_ = childErr.Close()
	return p
}

func (p *recoveryChild) write(t *testing.T, b []byte) {
	t.Helper()
	if err := p.in.SetWriteDeadline(time.Now().Add(5 * time.Second)); err != nil {
		t.Fatal("cannot bound stdin write")
	}
	for len(b) != 0 {
		n, err := p.in.Write(b)
		if err != nil || n == 0 {
			t.Fatal("request write did not complete")
		}
		b = b[n:]
	}
}

func (p *recoveryChild) closeInput(t *testing.T) {
	t.Helper()
	if err := p.in.Close(); err != nil {
		t.Fatal("cannot close request stdin")
	}
}

func (p *recoveryChild) frame(t *testing.T, limit uint32) []byte {
	t.Helper()
	if err := p.out.SetReadDeadline(time.Now().Add(5 * time.Second)); err != nil {
		t.Fatal("cannot bound stdout read")
	}
	var prefix [4]byte
	if _, err := io.ReadFull(p.out, prefix[:]); err != nil {
		t.Fatal("missing or incomplete output frame prefix")
	}
	n := binary.LittleEndian.Uint32(prefix[:])
	if n == 0 || n > limit {
		t.Fatal("output frame length outside contract bound")
	}
	raw := make([]byte, int(n))
	if _, err := io.ReadFull(p.out, raw); err != nil {
		t.Fatal("incomplete output frame payload")
	}
	return raw
}

func (p *recoveryChild) hello(t *testing.T) {
	t.Helper()
	recoveryEqualJSON(t, p.frame(t, 512), []byte(`{"protocol":"source_fact_scan_v1","kind":"hello","ownership":"linux_parent_death_v1"}`))
}

func (p *recoveryChild) quiet(t *testing.T) {
	t.Helper()
	if err := p.out.SetReadDeadline(time.Now().Add(100 * time.Millisecond)); err != nil {
		t.Fatal("cannot bound no-response check")
	}
	var b [1]byte
	n, err := p.out.Read(b[:])
	if n != 0 || !errors.Is(err, os.ErrDeadlineExceeded) {
		t.Fatal("child produced output or closed stdout before request EOF")
	}
}

func (p *recoveryChild) finish(t *testing.T, wantExit int) {
	t.Helper()
	var waitErr error
	select {
	case waitErr = <-p.done:
		p.reaped = p.cmd.ProcessState != nil
	case <-time.After(5 * time.Second):
		t.Fatal("child exit/reap deadline exceeded")
	}
	if !p.reaped || p.cmd.ProcessState.ExitCode() != wantExit {
		t.Fatal("child did not reap with the expected exit status")
	}
	var exitErr *exec.ExitError
	if wantExit == 0 && waitErr != nil || wantExit != 0 && !errors.As(waitErr, &exitErr) {
		t.Fatal("unexpected process wait failure")
	}
	select {
	case err := <-p.stderrDone:
		if err != nil {
			t.Fatal("stderr drain did not reach bounded EOF")
		}
	case <-time.After(time.Second):
		t.Fatal("stderr EOF deadline exceeded")
	}
	if p.stderr.count != 0 {
		t.Fatal("child emitted stderr")
	}
	if err := p.out.SetReadDeadline(time.Now().Add(time.Second)); err != nil {
		t.Fatal("cannot bound stdout EOF check")
	}
	var b [1]byte
	if n, err := p.out.Read(b[:]); n != 0 || err != io.EOF {
		t.Fatal("stdout is not EOF after the exact expected frames")
	}
}

// Exact decoded objects, including every field and span, without imposing a
// non-contractual JSON key order. Token counting also rejects duplicate keys:
// decoding alone would silently overwrite them and weaken the exact comparison.
func recoveryEqualJSON(t *testing.T, got, want []byte) {
	t.Helper()
	var gv, wv any
	gd, wd := json.NewDecoder(bytes.NewReader(got)), json.NewDecoder(bytes.NewReader(want))
	gd.UseNumber()
	wd.UseNumber()
	if len(got) < 2 || got[0] != '{' || got[len(got)-1] != '}' || !json.Valid(got) ||
		gd.Decode(&gv) != nil || wd.Decode(&wv) != nil || !reflect.DeepEqual(gv, wv) {
		t.Fatal("framed JSON does not match the complete expected object")
	}
	count := func(b []byte) int {
		d := json.NewDecoder(bytes.NewReader(b))
		n := 0
		for {
			_, err := d.Token()
			if err != nil {
				return n
			}
			n++
		}
	}
	if count(got) != count(want) {
		t.Fatal("framed JSON contains duplicate fields")
	}
}
