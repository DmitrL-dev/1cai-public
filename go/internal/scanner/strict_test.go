package scanner

import (
	"crypto/sha256"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

func TestStrictCoverageIncludesEmptyAndRawBOM(t *testing.T) {
	root := t.TempDir()
	raw := []byte("\xef\xbb\xbfProcedure Hello()\r\nEndProcedure\r\n")
	os.WriteFile(filepath.Join(root, "A.bsl"), raw, 0600)
	os.WriteFile(filepath.Join(root, "Empty.bsl"), []byte("// empty"), 0600)
	result, coverage, err := ScanCallGraphStrict(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(result) != 1 || len(coverage) != 2 || coverage[1].RoutineCount != 0 || coverage[0].RawSHA256 != fmt.Sprintf("%x", sha256.Sum256(raw)) {
		t.Fatalf("bad coverage: %+v", coverage)
	}
}

func TestStrictRejectsInvalidUTF8AndMissingRoot(t *testing.T) {
	root := t.TempDir()
	os.WriteFile(filepath.Join(root, "bad.bsl"), []byte{0xff}, 0600)
	_, coverage, err := ScanCallGraphStrict(root)
	if err == nil || len(coverage) != 1 || coverage[0].Status != "error" {
		t.Fatalf("encoding accepted: %+v %v", coverage, err)
	}
	if _, _, err = ScanCallGraphStrict(filepath.Join(root, "missing")); err == nil {
		t.Fatal("missing root accepted")
	}
}

func TestStrictRejectsUnterminatedRoutine(t *testing.T) {
	root := t.TempDir()
	os.WriteFile(filepath.Join(root, "bad.bsl"), []byte("Procedure Incomplete()\nCall();"), 0600)
	_, coverage, err := ScanCallGraphStrict(root)
	if err == nil || len(coverage) != 1 || coverage[0].Status != "error" {
		t.Fatalf("incomplete span accepted: %+v %v", coverage, err)
	}
}
