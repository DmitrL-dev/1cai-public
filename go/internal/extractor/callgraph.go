// Package extractor — callgraph.go
// Extracts function/procedure boundaries, calls, queries from BSL code
// for the Рентген call graph analyzer. Designed for 10-50x speedup over Python.
package extractor

import (
	"regexp"
	"sort"
	"strings"

	"1cai/bsl-scan/pkg/types"
)

// Cyrillic-aware identifier patterns.
// Go RE2 \w only matches ASCII, so we use \p{L} for Unicode letters.
const (
	idS = `[\p{L}_]`    // identifier start
	idC = `[\p{L}\d_]*` // identifier continuation
	id  = idS + idC     // full identifier
)

// Compiled regex patterns for BSL call graph extraction.
var (
	// Function/procedure declaration: captures (name) and optional (Экспорт/Export)
	reCGFuncStart = regexp.MustCompile(
		`(?im)^\s*(?:Функция|Function|Процедура|Procedure)\s+(` + id + `)\s*\([^)]*\)\s*(Экспорт|Export)?\s*$`)

	// Function/procedure end
	reCGFuncEnd = regexp.MustCompile(
		`(?im)^\s*(?:КонецФункции|EndFunction|КонецПроцедуры|EndProcedure)\s*$`)

	// Detect function (vs procedure) from declaration line
	reCGIsFunc = regexp.MustCompile(`(?i)^\s*(?:Функция|Function)\s+`)

	// Module.Method() calls
	reCGModuleCall = regexp.MustCompile(`(` + id + `)\.(` + id + `)\s*\(`)

	// Direct function calls: Name(
	reCGDirectCall = regexp.MustCompile(`(` + id + `)\s*\(`)

	// Query text: Запрос.Текст = "..."
	reCGQueryText = regexp.MustCompile(
		`(?i)(?:Запрос\.Текст|Query\.Text)\s*=\s*"([^"]*(?:""[^"]*)*)"`)

	// Table names in SQL/SDBL queries
	reCGQueryTables = regexp.MustCompile(
		`(?i)(?:ИЗ|FROM|СОЕДИНЕНИЕ|JOIN)\s+(` + id + `(?:\.` + id + `)*)`)

	// Complexity: decision points (whitespace-bounded for Cyrillic)
	reCGDecision = regexp.MustCompile(
		`(?i)(?:^|\s)(Если|If|ИначеЕсли|ElsIf|Для|For|Пока|While|И|And|Или|Or)(?:\s|$|;)`)
)

// BSL keywords — must not be counted as function calls.
var bslKeywords map[string]bool

func init() {
	keywords := []string{
		"если", "тогда", "иначе", "иначеесли", "конецесли",
		"для", "каждого", "из", "по", "цикл", "конеццикла", "пока",
		"попытка", "исключение", "конецпопытки",
		"возврат", "продолжить", "прервать", "перейти",
		"новый", "не", "и", "или", "истина", "ложь",
		"неопределено", "null",
		"процедура", "функция", "конецпроцедуры", "конецфункции",
		"экспорт", "знач",
		// English equivalents
		"if", "then", "else", "elsif", "endif",
		"for", "each", "in", "to", "do", "enddo", "while",
		"try", "except", "endtry",
		"return", "continue", "break", "goto",
		"new", "not", "and", "or", "true", "false",
		"undefined", "procedure", "function",
		"endprocedure", "endfunction", "export", "val",
	}
	bslKeywords = make(map[string]bool, len(keywords))
	for _, k := range keywords {
		bslKeywords[k] = true
	}
}

// ExtractCallGraph parses BSL source and returns all functions/procedures
// with their calls, queries, and complexity.
func ExtractCallGraph(code, moduleName string) []types.BslFunction {
	if strings.TrimSpace(code) == "" {
		return nil
	}

	// Strip UTF-8 BOM
	code = strings.TrimPrefix(code, "\xef\xbb\xbf")

	// Pre-compute line offset table: O(n) once, then O(log n) per lookup
	lineOffsets := buildLineOffsets(code)

	// Find all function/procedure starts and ends
	starts := reCGFuncStart.FindAllStringSubmatchIndex(code, -1)
	ends := reCGFuncEnd.FindAllStringIndex(code, -1)

	if len(starts) == 0 {
		return nil
	}

	functions := make([]types.BslFunction, 0, len(starts))

	for i, sm := range starts {
		// Group 1: function/procedure name
		name := code[sm[2]:sm[3]]

		// Group 2: Экспорт/Export (optional)
		isExport := sm[4] != -1

		// Determine function vs procedure from declaration line
		declLine := code[sm[0]:sm[1]]
		isFunction := reCGIsFunc.MatchString(declLine)

		startLine := lineAtOffset(lineOffsets, sm[0])

		// Find matching end: first КонецФункции/КонецПроцедуры after this start,
		// but before the next start (to handle sequential functions correctly)
		nextStartOffset := len(code)
		if i+1 < len(starts) {
			nextStartOffset = starts[i+1][0]
		}

		bodyEnd := nextStartOffset
		for _, em := range ends {
			if em[0] > sm[1] && em[0] < nextStartOffset {
				bodyEnd = em[0] // use start of end-keyword, not end
				break
			}
		}

		// Extract body: text between declaration and end keyword
		body := ""
		if sm[1] < bodyEnd {
			body = code[sm[1]:bodyEnd]
		}

		calls := extractCalls(body)
		queries := extractQueries(body, startLine)
		complexity := estimateComplexity(body)

		functions = append(functions, types.BslFunction{
			Name:       name,
			Module:     moduleName,
			Line:       startLine,
			IsExport:   isExport,
			IsFunction: isFunction,
			Complexity: complexity,
			Calls:      calls,
			Queries:    queries,
		})
	}

	return functions
}

// extractCalls finds all function/procedure calls in body text.
// Returns sorted unique list of call targets.
func extractCalls(body string) []string {
	if body == "" {
		return nil
	}

	seen := make(map[string]struct{})

	// Module.Method() calls
	for _, m := range reCGModuleCall.FindAllStringSubmatch(body, -1) {
		module := m[1]
		method := m[2]
		seen[module+"."+method] = struct{}{}
	}

	// Direct calls: Name(
	for _, m := range reCGDirectCall.FindAllStringSubmatch(body, -1) {
		name := m[1]
		if !bslKeywords[strings.ToLower(name)] {
			seen[name] = struct{}{}
		}
	}

	if len(seen) == 0 {
		return nil
	}

	calls := make([]string, 0, len(seen))
	for c := range seen {
		calls = append(calls, c)
	}
	sort.Strings(calls)
	return calls
}

// extractQueries finds SQL/SDBL queries (Запрос.Текст = "...") in body text.
func extractQueries(body string, baseLine int) []types.BslQuery {
	matches := reCGQueryText.FindAllStringSubmatchIndex(body, -1)
	if len(matches) == 0 {
		return nil
	}

	bodyOffsets := buildLineOffsets(body)
	queries := make([]types.BslQuery, 0, len(matches))

	for _, m := range matches {
		qText := body[m[2]:m[3]]
		qText = strings.ReplaceAll(qText, `""`, `"`)
		qLine := baseLine + lineAtOffset(bodyOffsets, m[0]) - 1

		var tables []string
		for _, t := range reCGQueryTables.FindAllStringSubmatch(qText, -1) {
			tables = append(tables, t[1])
		}

		queries = append(queries, types.BslQuery{
			Text:   qText,
			Line:   qLine,
			Tables: tables,
		})
	}

	return queries
}

// estimateComplexity counts decision points for cyclomatic complexity.
func estimateComplexity(body string) int {
	return 1 + len(reCGDecision.FindAllString(body, -1))
}

// buildLineOffsets pre-computes byte offsets of each line start.
// Returns slice where lineOffsets[i] = byte offset of line (i+1).
func buildLineOffsets(text string) []int {
	offsets := make([]int, 0, strings.Count(text, "\n")+1)
	offsets = append(offsets, 0) // line 1 starts at offset 0
	for i := 0; i < len(text); i++ {
		if text[i] == '\n' {
			offsets = append(offsets, i+1)
		}
	}
	return offsets
}

// lineAtOffset returns 1-indexed line number for a byte offset.
// Uses binary search on pre-computed offsets: O(log n).
func lineAtOffset(offsets []int, offset int) int {
	// Find last entry <= offset
	idx := sort.SearchInts(offsets, offset+1) - 1
	if idx < 0 {
		idx = 0
	}
	return idx + 1 // 1-indexed
}
