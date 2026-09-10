package scanner

import (
	"crypto/sha256"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"unicode/utf8"

	"1cai/bsl-scan/internal/extractor"
	"1cai/bsl-scan/pkg/types"
)

// FileCoverage reports every BSL input, including valid files without routines.
// Error codes are stable and never include private host paths.
type FileCoverage struct {
	SourcePath   string `json:"source_path"`
	RawSHA256    string `json:"raw_sha256"`
	Status       string `json:"status"`
	RoutineCount int    `json:"routine_count"`
	Error        string `json:"error,omitempty"`
}

// ScanCallGraphStrict is the opt-in captured-source mode. WalkDir ordering is
// deterministic and all walk/read/type/encoding errors fail the entire scan.
func ScanCallGraphStrict(root string) ([]types.BslFunction, []FileCoverage, error) {
	funcs := make([]types.BslFunction, 0)
	coverage := make([]FileCoverage, 0)
	info, err := os.Lstat(root)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return funcs, coverage, fmt.Errorf("root_unavailable")
	}
	err = filepath.WalkDir(root, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return fmt.Errorf("walk_failed")
		}
		if d.IsDir() {
			return nil
		}
		if !d.Type().IsRegular() {
			return fmt.Errorf("unsafe_file_type")
		}
		if !bslExtensions[strings.ToLower(filepath.Ext(path))] {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return fmt.Errorf("relative_path_failed")
		}
		item := FileCoverage{SourcePath: filepath.ToSlash(rel), Status: "error"}
		data, err := os.ReadFile(path)
		if err != nil {
			item.Error = "read_failed"
			coverage = append(coverage, item)
			return fmt.Errorf("read_failed")
		}
		item.RawSHA256 = fmt.Sprintf("%x", sha256.Sum256(data))
		if !utf8.Valid(data) {
			item.Error = "invalid_utf8"
			coverage = append(coverage, item)
			return fmt.Errorf("invalid_utf8")
		}
		code := strings.TrimPrefix(string(data), "\ufeff")
		// Display aliases are presentation only; full source paths retain layer IDs.
		module := moduleNameFromPath(path, root)
		parts := strings.Split(rel, string(filepath.Separator))
		if len(parts) > 1 {
			module = moduleNameFromPath(path, filepath.Join(root, parts[0]))
		}
		found := extractor.ExtractCallGraph(code, module)
		for i := range found {
			if found[i].EndLine < found[i].Line {
				item.Error = "incomplete_routine_span"
				coverage = append(coverage, item)
				return fmt.Errorf("incomplete_routine_span")
			}
			found[i].SourcePath = item.SourcePath
		}
		funcs = append(funcs, found...)
		item.Status = "parsed"
		item.RoutineCount = len(found)
		coverage = append(coverage, item)
		return nil
	})
	return funcs, coverage, err
}
