// Package scanner provides parallel BSL file scanning.
package scanner

import (
	"io/fs"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"1cai/bsl-scan/internal/extractor"
	"1cai/bsl-scan/pkg/types"
)

// BSL file extensions to scan.
var bslExtensions = map[string]bool{
	".bsl": true,
	".os":  true,
	".bsp": true,
}

// Scan walks root directory, extracts features from all BSL files in parallel.
func Scan(root string, workers int) types.ScanResult {
	if workers <= 0 {
		workers = runtime.NumCPU()
	}

	start := time.Now()

	// Find all BSL files
	paths := make(chan string, 100)
	go func() {
		defer close(paths)
		_ = filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return nil // skip errors
			}
			if d.IsDir() {
				return nil
			}
			ext := strings.ToLower(filepath.Ext(path))
			if bslExtensions[ext] {
				paths <- path
			}
			return nil
		})
	}()

	// Process files in parallel
	results := make(chan types.FileResult, 100)
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for path := range paths {
				results <- processFile(path)
			}
		}()
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	// Collect results
	var files []types.FileResult
	totalLOC := 0
	for r := range results {
		files = append(files, r)
		totalLOC += r.LOC
	}

	return types.ScanResult{
		Files:      files,
		TotalFiles: len(files),
		TotalLOC:   totalLOC,
		DurationMs: time.Since(start).Milliseconds(),
	}
}

func processFile(path string) types.FileResult {
	data, err := os.ReadFile(path)
	if err != nil {
		return types.FileResult{
			Path:  path,
			Error: err.Error(),
		}
	}

	code := string(data)
	features := extractor.Extract(code)

	return types.FileResult{
		Path:     path,
		Features: features,
		LOC:      int(features.LOC),
	}
}

// --- Call Graph scanning for Рентген ---

// callGraphFileResult holds per-file extraction results for the worker pool.
type callGraphFileResult struct {
	funcs []types.BslFunction
	isErr bool
}

// ScanCallGraph walks root directory and extracts call graph data from all BSL files.
// Uses the same parallel worker pool pattern as Scan but calls ExtractCallGraph.
func ScanCallGraph(root string, workers int) types.CallGraphResult {
	if workers <= 0 {
		workers = runtime.NumCPU()
	}

	start := time.Now()

	// Find all BSL files
	paths := make(chan string, 256)
	go func() {
		defer close(paths)
		_ = filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return nil
			}
			if d.IsDir() {
				return nil
			}
			ext := strings.ToLower(filepath.Ext(path))
			if bslExtensions[ext] {
				paths <- path
			}
			return nil
		})
	}()

	// Process files in parallel
	results := make(chan callGraphFileResult, 256)
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for path := range paths {
				data, err := os.ReadFile(path)
				if err != nil {
					results <- callGraphFileResult{isErr: true}
					continue
				}

				// Strip BOM at file level
				code := string(data)
				if len(data) >= 3 && data[0] == 0xEF && data[1] == 0xBB && data[2] == 0xBF {
					code = string(data[3:])
				}

				moduleName := moduleNameFromPath(path, root)
				funcs := extractor.ExtractCallGraph(code, moduleName)
				results <- callGraphFileResult{funcs: funcs}
			}
		}()
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	// Collect all functions
	var allFuncs []types.BslFunction
	totalFiles := 0
	errors := 0
	for r := range results {
		totalFiles++
		if r.isErr {
			errors++
			continue
		}
		allFuncs = append(allFuncs, r.funcs...)
	}

	return types.CallGraphResult{
		Functions:  allFuncs,
		TotalFiles: totalFiles,
		TotalFuncs: len(allFuncs),
		DurationMs: time.Since(start).Milliseconds(),
		Errors:     errors,
	}
}

// moduleNameFromPath derives 1C module name from file path.
// Replicates Python OneCCodeGraphBuilder._module_name_from_path logic:
//
//	CommonModules/МойМодуль/Ext/Module.bsl                  → МойМодуль
//	Documents/МойДокумент/Ext/ObjectModule.bsl              → МойДокумент.ObjectModule
//	Documents/МойДокумент/Ext/ManagerModule.bsl             → МойДокумент.ManagerModule
//	Documents/МойДокумент/Forms/Форма/Ext/Form/Module.bsl   → МойДокумент.Form
//	CommonForms/ОбщаяФорма/Ext/Form/Module.bsl              → ОбщаяФорма.Form
//
// Form modules of an object are all collapsed into one node "<Object>.Form"
// so the Python side canonicalizes them to (object_name, "form"), matching the
// existing 2-segment "<Object>.<Kind>" convention.
func moduleNameFromPath(filePath, configRoot string) string {
	rel, err := filepath.Rel(configRoot, filePath)
	if err != nil {
		base := filepath.Base(filePath)
		return strings.TrimSuffix(base, filepath.Ext(base))
	}

	// Normalize to forward slashes for splitting
	parts := strings.Split(filepath.ToSlash(rel), "/")

	base := filepath.Base(filePath)
	stem := strings.TrimSuffix(base, filepath.Ext(base))

	// Form module? On disk a form's BSL is always ".../Ext/Form/Module.bsl"
	// (stem "Module" whose parent dir is "Form"). This covers object forms
	// (<Type>/<Object>/Forms/<FormName>/Ext/Form/Module.bsl) and common forms
	// (CommonForms/<FormName>/Ext/Form/Module.bsl). Collapse every form of an
	// object into a single "<Object>.Form" node.
	if stem == "Module" && len(parts) >= 2 && parts[len(parts)-2] == "Form" {
		if obj := formObjectName(parts, configRoot); obj != "" {
			return obj + ".Form"
		}
	}

	// Object name is normally the 2nd path segment of a config-root-relative path
	// (<MetadataType>/<Object>/Ext/<Kind>Module.bsl, so parts[1] == <Object>).
	// But when the scan is rooted directly at a single object directory, the
	// relative path is just "Ext/<Kind>Module.bsl" and parts[1] is the file name
	// itself (e.g. "ManagerModule.bsl"), which would yield the malformed
	// "ManagerModule.bsl.ManagerModule". Detect that case — fewer than 3 segments,
	// or a parts[1] that is the BSL file rather than a directory — and fall back to
	// the configRoot's base name as the object.
	if len(parts) >= 3 && !bslExtensions[strings.ToLower(filepath.Ext(parts[1]))] {
		objName := parts[1]
		if stem == "Module" {
			return objName
		}
		return objName + "." + stem
	}

	// Single-object scan: derive the object from the directory we were pointed at.
	if objName := filepath.Base(configRoot); objName != "" && objName != "." && objName != string(filepath.Separator) {
		if stem == "Module" {
			return objName
		}
		return objName + "." + stem
	}

	return stem
}

// formObjectName extracts the metadata object owning a form module from the
// relative path segments. For object forms the object is the segment directly
// before "Forms"; if "Forms" is the first segment (single-object scan rooted at
// the object dir) we fall back to the configRoot's base name. For common forms
// (no "Forms" segment) the form itself is the object (parts[1]).
func formObjectName(parts []string, configRoot string) string {
	for i, p := range parts {
		if p == "Forms" {
			if i >= 1 {
				return parts[i-1]
			}
			return filepath.Base(configRoot)
		}
	}
	// No "Forms" segment (e.g. CommonForms/<FormName>/Ext/Form/Module.bsl).
	if len(parts) >= 2 {
		return parts[1]
	}
	if len(parts) == 1 && parts[0] != "" {
		return parts[0]
	}
	return filepath.Base(configRoot)
}
