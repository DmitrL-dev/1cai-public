// bsl-scan — fast parallel BSL code scanner for 1cAI.
//
// Two modes:
//
//	scan      — extract code quality features (Micro-Swarm)
//	callgraph — extract call graph for Рентген (NDJSON to stdout)
//
// Usage:
//
//	bsl-scan [flags] <path>
//	bsl-scan -format summary C:\Projects\ERP
//	bsl-scan -mode callgraph C:\Projects\ERP > graph.ndjson
//	bsl-scan C:\Projects\ERP | python -m router
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"runtime"
	"sort"

	"1cai/bsl-scan/internal/scanner"
	"1cai/bsl-scan/pkg/types"
)

func main() {
	workers := flag.Int("workers", runtime.NumCPU(), "parallel workers")
	mode := flag.String("mode", "scan", "mode: scan|callgraph")
	format := flag.String("format", "json", "output format: json|summary (scan mode only)")
	minLOC := flag.Int("min-loc", 0, "skip files smaller than N lines (scan mode only)")
	coveragePath := flag.String("coverage", "", "strict mode coverage JSON output")
	version := flag.Bool("version", false, "print scanner protocol version")
	flag.Parse()
	if *version {
		fmt.Println("bsl-scan-captured-v1")
		return
	}

	args := flag.Args()
	if len(args) == 0 {
		fmt.Fprintf(os.Stderr, "Usage: bsl-scan [flags] <path>\n")
		fmt.Fprintf(os.Stderr, "\nModes:\n")
		fmt.Fprintf(os.Stderr, "  scan       Extract code quality features (default)\n")
		fmt.Fprintf(os.Stderr, "  callgraph  Extract call graph for Рентген (NDJSON)\n\n")
		flag.PrintDefaults()
		os.Exit(1)
	}

	root := args[0]
	if *mode == "callgraph-strict" {
		if len(args) != 1 || *coveragePath == "" {
			fmt.Fprintln(os.Stderr, `{"error":"invalid_strict_options"}`)
			os.Exit(1)
		}
		runStrictCallGraph(root, *coveragePath)
		return
	}

	// Verify path exists
	if _, err := os.Stat(root); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Error: path %q does not exist\n", root)
		os.Exit(1)
	}

	switch *mode {
	case "scan":
		runScan(root, *workers, *format, *minLOC)
	case "callgraph":
		runCallGraph(root, *workers)
	default:
		fmt.Fprintf(os.Stderr, "Unknown mode: %s (use scan or callgraph)\n", *mode)
		os.Exit(1)
	}
}

func runStrictCallGraph(root, coveragePath string) {
	functions, coverage, scanErr := scanner.ScanCallGraphStrict(root)
	report := struct {
		FormatVersion int                    `json:"format_version"`
		Files         []scanner.FileCoverage `json:"files"`
		Error         string                 `json:"error,omitempty"`
	}{1, coverage, ""}
	if scanErr != nil {
		report.Error = scanErr.Error()
	}
	raw, err := json.Marshal(report)
	if err == nil {
		err = os.WriteFile(coveragePath, raw, 0600)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, `{"error":"coverage_write_failed"}`)
		os.Exit(1)
	}
	if scanErr != nil {
		fmt.Fprintf(os.Stderr, "{\"error\":%q}\n", scanErr.Error())
		os.Exit(1)
	}
	enc := json.NewEncoder(os.Stdout)
	for i := range functions {
		if err := enc.Encode(&functions[i]); err != nil {
			fmt.Fprintln(os.Stderr, `{"error":"output_failed"}`)
			os.Exit(1)
		}
	}
}

// --- Scan mode (existing behavior) ---

func runScan(root string, workers int, format string, minLOC int) {
	result := scanner.Scan(root, workers)

	// Filter by min-loc
	if minLOC > 0 {
		filtered := result.Files[:0]
		for _, f := range result.Files {
			if f.LOC >= minLOC {
				filtered = append(filtered, f)
			}
		}
		result.Files = filtered
		result.TotalFiles = len(filtered)
	}

	switch format {
	case "json":
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(result); err != nil {
			fmt.Fprintf(os.Stderr, "Error encoding JSON: %v\n", err)
			os.Exit(1)
		}
	case "summary":
		printSummary(result)
	default:
		fmt.Fprintf(os.Stderr, "Unknown format: %s\n", format)
		os.Exit(1)
	}
}

// --- Call Graph mode (Рентген) ---

func runCallGraph(root string, workers int) {
	result := scanner.ScanCallGraph(root, workers)

	// Output NDJSON: one JSON line per function (streamed to stdout)
	enc := json.NewEncoder(os.Stdout)
	for i := range result.Functions {
		if err := enc.Encode(&result.Functions[i]); err != nil {
			fmt.Fprintf(os.Stderr, "Error encoding function %d: %v\n", i, err)
		}
	}

	// Summary to stderr (not mixed with NDJSON on stdout)
	fmt.Fprintf(os.Stderr,
		"Рентген: %d files → %d functions (%d errors) in %dms [%d workers]\n",
		result.TotalFiles, result.TotalFuncs, result.Errors,
		result.DurationMs, workers)
}

// --- Summary output (scan mode) ---

func printSummary(result types.ScanResult) {
	fmt.Printf("BSL Scan Results\n")
	fmt.Printf("================\n")
	fmt.Printf("Files:    %d\n", result.TotalFiles)
	fmt.Printf("LOC:      %d\n", result.TotalLOC)
	fmt.Printf("Duration: %dms\n", result.DurationMs)
	fmt.Printf("Workers:  %d\n\n", runtime.NumCPU())

	// Count issues
	var (
		nPlus1   int
		selectSt int
		emptyCat int
		deepNest int
		magic    int
	)
	for _, f := range result.Files {
		if f.Features.HasNPlusOne == 1 {
			nPlus1++
		}
		if f.Features.HasSelectStar == 1 {
			selectSt++
		}
		if f.Features.HasEmptyCatch == 1 {
			emptyCat++
		}
		if f.Features.HasDeepNesting == 1 {
			deepNest++
		}
		if f.Features.HasMagicNumbers == 1 {
			magic++
		}
	}

	fmt.Printf("Issues Found:\n")
	fmt.Printf("  N+1 queries:    %d files\n", nPlus1)
	fmt.Printf("  SELECT *:       %d files\n", selectSt)
	fmt.Printf("  Empty catch:    %d files\n", emptyCat)
	fmt.Printf("  Deep nesting:   %d files\n", deepNest)
	fmt.Printf("  Magic numbers:  %d files\n", magic)

	// Top 10 most complex files
	if len(result.Files) > 0 {
		fmt.Printf("\nTop Complex Files:\n")
		sorted := make([]struct {
			path       string
			complexity float64
		}, 0, len(result.Files))
		for _, f := range result.Files {
			if f.Error == "" {
				sorted = append(sorted, struct {
					path       string
					complexity float64
				}{f.Path, f.Features.Complexity})
			}
		}
		sort.Slice(sorted, func(i, j int) bool {
			return sorted[i].complexity > sorted[j].complexity
		})
		limit := 10
		if len(sorted) < limit {
			limit = len(sorted)
		}
		for i := 0; i < limit; i++ {
			fmt.Printf("  %6.0f  %s\n", sorted[i].complexity, sorted[i].path)
		}
	}
}
