package extractor

import (
	"1cai/bsl-scan/pkg/types"
	"regexp"
	"sort"
	"strings"
)

const id = `[\p{L}_][\p{L}\d_]*`

var reCGQueryTables = regexp.MustCompile(`(?i)(?:ИЗ|FROM|СОЕДИНЕНИЕ|JOIN)\s+(` + id + `(?:\.` + id + `)*)`)

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
		"вызватьисключение", "выполнить", "перем", "асинх", "ждать",
		// English equivalents
		"if", "then", "else", "elsif", "endif",
		"for", "each", "in", "to", "do", "enddo", "while",
		"try", "except", "endtry",
		"return", "continue", "break", "goto",
		"new", "not", "and", "or", "true", "false",
		"undefined", "procedure", "function",
		"endprocedure", "endfunction", "export", "val",
		"raise", "execute", "var", "async", "await",
	}
	bslKeywords = make(map[string]bool, len(keywords))
	for _, k := range keywords {
		bslKeywords[k] = true
	}
}

// ExtractCallGraph uses lexical boundaries, not a full BSL parser. A missing end
// keyword has EndLine 0; preprocessing and receiver types are not resolved.
func ExtractCallGraph(code, moduleName string) []types.BslFunction {
	tokens := lexBSL(code)
	pairs := delimiterPairs(tokens)
	var functions []types.BslFunction
	for i := 0; i+2 < len(tokens); i++ {
		if !declarationAt(tokens, i) {
			continue
		}
		close, ok := pairs[i+2]
		if !ok {
			continue
		}
		f := types.BslFunction{Name: tokens[i+1].text, Module: moduleName,
			Line: tokens[i].line, IsFunction: tokenIs(tokens[i], "функция", "function")}
		bodyStart := close + 1
		if bodyStart < len(tokens) && tokenIs(tokens[bodyStart], "экспорт", "export") {
			f.IsExport = true
			bodyStart++
		}
		end := bodyStart
		for end < len(tokens) {
			if declarationAt(tokens, end) {
				break
			}
			if tokenIs(tokens[end], "конецпроцедуры", "endprocedure", "конецфункции", "endfunction") {
				f.EndLine = tokens[end].line
				break
			}
			end++
		}
		body := tokens[bodyStart:end]
		f.CallSites, f.Calls = extractCallSites(body)
		f.Queries = extractTokenQueries(body)
		f.Complexity = 1
		for _, t := range body {
			if t.kind == 'i' && tokenIs(t, "если", "if", "иначеесли", "elsif", "для", "for", "пока", "while", "и", "and", "или", "or") {
				f.Complexity++
			}
		}
		functions = append(functions, f)
		i = end - 1
	}
	return functions
}

func declarationAt(tokens []bslToken, i int) bool {
	return i+2 < len(tokens) &&
		(i == 0 || tokens[i-1].endLine < tokens[i].line) &&
		tokenIs(tokens[i], "процедура", "procedure", "функция", "function") &&
		tokens[i+1].kind == 'i' && tokens[i+2].text == "("
}

func extractCallSites(tokens []bslToken) ([]types.BslCallSite, []string) {
	sites := make([]types.BslCallSite, 0)
	seen := make(map[string]bool)
	pairs := delimiterPairs(tokens)
	for i, t := range tokens {
		if t.kind != 'i' || i+1 >= len(tokens) || tokens[i+1].text != "(" || bslKeywords[strings.ToLower(t.text)] {
			continue
		}
		start := receiverStart(tokens, pairs, i)
		constructed := start > 0 && tokenIs(tokens[start-1], "новый", "new")
		kind := "direct"
		if start < i {
			kind = "qualified"
		}
		var target strings.Builder
		for j := start; j <= i; j++ {
			target.WriteString(tokens[j].text)
			if tokens[j].kind != 'i' && tokens[j].text != "." {
				kind = "unresolved"
			}
		}
		// A leading dot has an unsupported/missing receiver. Never bind locally.
		if start > 0 && tokens[start-1].text == "." {
			kind = "unresolved"
		}
		if constructed && kind != "unresolved" {
			continue
		}
		sites = append(sites, types.BslCallSite{Target: target.String(), Kind: kind,
			Line: tokens[start].line, Column: tokens[start].column,
			EndLine: t.endLine, EndColumn: t.endColumn})
		if kind != "unresolved" {
			seen[target.String()] = true
		}
	}
	var calls []string
	for target := range seen {
		calls = append(calls, target)
	}
	sort.Strings(calls)
	return sites, calls
}

// receiverStart walks only postfix receiver syntax. Parenthesized/indexed
// receivers remain in the target evidence and are classified as unresolved.
func receiverStart(tokens []bslToken, pairs map[int]int, end int) int {
	start := end
	if tokens[end].text == ")" || tokens[end].text == "]" {
		open, ok := pairs[end]
		if !ok {
			return start
		}
		start = open
		if open > 0 && (tokens[open-1].kind == 'i' || tokens[open-1].text == ")" || tokens[open-1].text == "]") && !bslKeywords[strings.ToLower(tokens[open-1].text)] {
			start = receiverStart(tokens, pairs, open-1)
		}
	}
	if start >= 2 && tokens[start-1].text == "." {
		start = receiverStart(tokens, pairs, start-2)
	}
	return start
}

// Only literal assignments to the conventional query text property are
// extracted. This does not infer aliases, concatenations, or runtime queries.
func extractTokenQueries(tokens []bslToken) []types.BslQuery {
	var queries []types.BslQuery
	for i := 0; i+4 < len(tokens); i++ {
		if !tokenIs(tokens[i], "запрос", "query") || tokens[i+1].text != "." ||
			!tokenIs(tokens[i+2], "текст", "text") || tokens[i+3].text != "=" || tokens[i+4].kind != 's' {
			continue
		}
		if i > 0 && tokens[i-1].text == "." {
			continue
		}
		if i+5 < len(tokens) && tokens[i+5].text != ";" {
			continue
		}
		raw := tokens[i+4].text
		if len(raw) < 2 || !strings.HasSuffix(raw, `"`) {
			continue
		}
		qText := strings.ReplaceAll(raw[1:len(raw)-1], `""`, `"`)
		// The continuation marker/indent is BSL syntax, not query text.
		lines := strings.Split(qText, "\n")
		for j := 1; j < len(lines); j++ {
			lines[j] = strings.TrimPrefix(strings.TrimLeft(lines[j], " \t"), "|")
		}
		qText = strings.Join(lines, "\n")
		var tables []string
		for _, t := range reCGQueryTables.FindAllStringSubmatch(qText, -1) {
			tables = append(tables, t[1])
		}
		queries = append(queries, types.BslQuery{Text: qText, Line: tokens[i].line, Tables: tables})
	}
	return queries
}
