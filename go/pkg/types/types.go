// Package types defines shared data structures for BSL scanner.
package types

// Features holds extracted BSL code features for Micro-Swarm analysis.
// JSON tags match Python SwarmRouter expected keys.
type Features struct {
	// BSL Pattern Detection
	HasFormHandler  float64 `json:"has_form_handler"`
	HasDBQuery      float64 `json:"has_db_query"`
	HasPrintForm    float64 `json:"has_print_form"`
	HasHTTPCall     float64 `json:"has_http_call"`
	HasScheduledJob float64 `json:"has_scheduled_job"`

	// Query Optimizer
	HasNPlusOne        float64 `json:"has_n_plus_one"`
	HasSelectStar      float64 `json:"has_select_star"`
	HasNoIndexHint     float64 `json:"has_no_index_hint"`
	HasUnnecessaryJoin float64 `json:"has_unnecessary_join"`
	HasSubqueryInCond  float64 `json:"has_subquery_in_condition"`

	// Error Predictor
	HasEmptyCatch   float64 `json:"has_empty_catch"`
	HasDivisionRisk float64 `json:"has_division_risk"`
	HasMagicNumbers float64 `json:"has_magic_numbers"`
	HasDeepNesting  float64 `json:"has_deep_nesting"`

	// Quality Metrics
	Complexity  float64 `json:"complexity"`
	DocCoverage float64 `json:"doc_coverage"`
	MaxNesting  float64 `json:"max_nesting"`
	LOC         float64 `json:"loc"`
}

// FileResult holds analysis results for a single BSL file.
type FileResult struct {
	Path     string   `json:"path"`
	Features Features `json:"features"`
	LOC      int      `json:"loc"`
	Error    string   `json:"error,omitempty"`
}

// ScanResult holds aggregated results of a full project scan.
type ScanResult struct {
	Files      []FileResult `json:"files"`
	TotalFiles int          `json:"total_files"`
	TotalLOC   int          `json:"total_loc"`
	DurationMs int64        `json:"duration_ms"`
}

// --- Call Graph types for Рентген ---

// BslFunction represents an extracted function/procedure with its calls and queries.
type BslFunction struct {
	Name       string        `json:"name"`
	Module     string        `json:"module"`
	Line       int           `json:"line"`
	EndLine    int           `json:"end_line"`
	SourcePath string        `json:"source_path"`
	IsExport   bool          `json:"is_export"`
	IsFunction bool          `json:"is_function"`
	Complexity int           `json:"complexity"`
	Calls      []string      `json:"calls,omitempty"`
	CallSites  []BslCallSite `json:"call_sites"`
	Queries    []BslQuery    `json:"queries,omitempty"`
}

// BslCallSite spans the target expression (excluding call parentheses).
// Positions are 1-based Unicode characters; the end position is exclusive.
// Unresolved sites are evidence only and must never bind as local calls.
type BslCallSite struct {
	Target    string `json:"target"`
	Line      int    `json:"line"`
	Column    int    `json:"column"`
	EndLine   int    `json:"end_line"`
	EndColumn int    `json:"end_column"`
	Kind      string `json:"kind"` // direct, qualified, unresolved
}

// BslQuery represents an extracted SQL/SDBL query.
type BslQuery struct {
	Text   string   `json:"text"`
	Line   int      `json:"line"`
	Tables []string `json:"tables,omitempty"`
}

// CallGraphResult holds aggregated results of a call graph scan.
type CallGraphResult struct {
	Functions  []BslFunction `json:"-"` // streamed as NDJSON, not in summary
	TotalFiles int           `json:"total_files"`
	TotalFuncs int           `json:"total_funcs"`
	DurationMs int64         `json:"duration_ms"`
	Errors     int           `json:"errors"`
}
