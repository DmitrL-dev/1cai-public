//go:build linux && amd64

package scanner

import (
	"os"
	"path/filepath"
	"reflect"
	"syscall"
	"testing"
)

func TestOwnedActualDescriptorParityAndBounds(t *testing.T) {
	root := t.TempDir()
	if err := os.Chmod(root, 0700); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(root, "base", "CommonModules", "Demo", "Ext")
	if err := os.MkdirAll(path, 0700); err != nil {
		t.Fatal(err)
	}
	raw := []byte("\xef\xbb\xbfProcedure Demo()\r\nEndProcedure\r\n")
	if err := os.WriteFile(filepath.Join(path, "Module.bsl"), raw, 0600); err != nil {
		t.Fatal(err)
	}
	want, coverage, err := ScanCallGraphStrict(root)
	if err != nil {
		t.Fatal(err)
	}
	bounded := OwnedLimits{MaxFile: int64(len(raw)), MaxBytes: int64(len(raw)), MaxFiles: 1, MaxEntries: 5, MaxDepth: 4}
	read := func(limits OwnedLimits) bool {
		fd, err := syscall.Open(root, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW, 0)
		if err != nil {
			t.Fatal(err)
		}
		got, report, err := ScanCallGraphOwned(fd, limits)
		if err == nil && (!reflect.DeepEqual(got, want) || !reflect.DeepEqual(report, coverage)) {
			t.Fatalf("parity mismatch")
		}
		return err == nil
	}
	if !read(bounded) {
		t.Fatal("exact threshold refused")
	}
	less := bounded
	less.MaxFile--
	if read(less) {
		t.Fatal("file limit accepted")
	}
	less = bounded
	less.MaxBytes--
	if read(less) {
		t.Fatal("source limit accepted")
	}
	less = bounded
	less.MaxEntries--
	if read(less) {
		t.Fatal("entry limit accepted")
	}
	less = bounded
	less.MaxDepth--
	if read(less) {
		t.Fatal("depth limit accepted")
	}
}
