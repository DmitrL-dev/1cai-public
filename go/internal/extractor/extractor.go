// Package extractor provides BSL code feature extraction using regex.
// Port of Python bsl_domains.py patterns to Go for 10-100x performance.
package extractor

import (
	"regexp"
	"strings"

	"1cai/bsl-scan/pkg/types"
)

// Compiled regex patterns (initialized once, thread-safe).
var (
	// BSL Pattern Detection
	reFormHandler = regexp.MustCompile(`(?i)процедура\s+(приоткрытии|приизменении|призакрытии|принажатии|призаписи|передзаписью|послезаписи|передзакрытием|обработкавыбора|обработкаоповещения)`)
	reDBQuery     = regexp.MustCompile(`(?i)(новый\s+запрос|запрос\.текст\s*=)`)
	rePrintForm   = regexp.MustCompile(`(?i)(табличныйдокумент|макет\s*=\s*получитьмакет|вывестиобласть)`)
	reHTTPCall    = regexp.MustCompile(`(?i)(httpзапрос|httpсоединение|httpсервисответ|ws\s*=\s*новый)`)
	reScheduled   = regexp.MustCompile(`(?i)(регламентноезадание|фоновоезадание|обработчикожидания)`)

	// Query Optimizer
	reSelectStar  = regexp.MustCompile(`(?i)выбрать\s+\*\s+из`)
	reLoopStart   = regexp.MustCompile(`(?i)(для\s+каждого|пока)\s+`)
	reQueryInside = regexp.MustCompile(`(?i)(новый\s+запрос|\.выполнить\(\))`)
	reJoin        = regexp.MustCompile(`(?i)(соединение|левое\s+соединение|правое\s+соединение|полное\s+соединение)`)
	reSubquery    = regexp.MustCompile(`(?i)где\s+.*\(\s*выбрать`)

	// Error Predictor
	reTryStart   = regexp.MustCompile(`(?i)попытка`)
	reCatchStart = regexp.MustCompile(`(?i)исключение`)
	reTryEnd     = regexp.MustCompile(`(?i)конецпопытки`)
	reDivision   = regexp.MustCompile(`/\s*[а-яА-Яa-zA-Z_]`)
	reMagic      = regexp.MustCompile(`(?:=|>|<|>=|<=)\s*\d{3,}`)

	// Quality — Go \b doesn't work with Cyrillic, use whitespace boundaries
	reIfStart   = regexp.MustCompile(`(?i)(?:^|\s)если\s`)
	reElseIf    = regexp.MustCompile(`(?i)(?:^|\s)иначеесли\s`)
	reForLoop   = regexp.MustCompile(`(?i)(?:^|\s)для\s`)
	reWhileLoop = regexp.MustCompile(`(?i)(?:^|\s)пока\s`)
	reFuncStart = regexp.MustCompile(`(?i)(функция|процедура)\s+`)
	reFuncEnd   = regexp.MustCompile(`(?i)(конецфункции|конецпроцедуры)`)
	reComment   = regexp.MustCompile(`^\s*//`)
	reNestOpen  = regexp.MustCompile(`(?i)(?:^|\s)(если|для|пока|попытка)(?:\s|$)`)
	reNestClose = regexp.MustCompile(`(?i)(?:^|\s)(конецесли|конеццикла|конецпопытки)(?:\s|;|$)`)
)

// Extract analyzes BSL code and returns extracted features.
func Extract(code string) types.Features {
	if code == "" {
		return types.Features{}
	}

	lines := strings.Split(strings.TrimRight(code, "\n\r"), "\n")
	loc := len(lines)
	if loc == 1 && strings.TrimSpace(lines[0]) == "" {
		loc = 0
	}

	f := types.Features{
		LOC: float64(loc),
	}

	// Single-pass feature extraction
	f.HasFormHandler = boolToFloat(reFormHandler.MatchString(code))
	f.HasDBQuery = boolToFloat(reDBQuery.MatchString(code))
	f.HasPrintForm = boolToFloat(rePrintForm.MatchString(code))
	f.HasHTTPCall = boolToFloat(reHTTPCall.MatchString(code))
	f.HasScheduledJob = boolToFloat(reScheduled.MatchString(code))

	// Query optimizer
	f.HasSelectStar = boolToFloat(reSelectStar.MatchString(code))
	f.HasUnnecessaryJoin = boolToFloat(len(reJoin.FindAllString(code, -1)) > 2)
	f.HasSubqueryInCond = boolToFloat(reSubquery.MatchString(code))

	// N+1 detection: query inside loop
	f.HasNPlusOne = detectNPlusOne(lines)

	// Error predictor
	f.HasEmptyCatch = detectEmptyCatch(lines)
	f.HasDivisionRisk = boolToFloat(reDivision.MatchString(code))
	f.HasMagicNumbers = boolToFloat(reMagic.MatchString(code))

	// Nesting and complexity
	maxNest, complexity := analyzeNesting(lines)
	f.MaxNesting = float64(maxNest)
	f.HasDeepNesting = boolToFloat(maxNest > 4)
	f.Complexity = float64(complexity)

	// Doc coverage
	f.DocCoverage = calcDocCoverage(lines)

	return f
}

// detectNPlusOne checks if a query is executed inside a loop.
func detectNPlusOne(lines []string) float64 {
	inLoop := 0
	for _, line := range lines {
		if reLoopStart.MatchString(line) {
			inLoop++
		}
		if inLoop > 0 && reQueryInside.MatchString(line) {
			return 1
		}
		if reNestClose.MatchString(line) && inLoop > 0 {
			inLoop--
		}
	}
	return 0
}

// detectEmptyCatch checks for try/catch blocks with no code in the catch.
func detectEmptyCatch(lines []string) float64 {
	for i, line := range lines {
		if reCatchStart.MatchString(line) {
			// Check if next non-empty line is КонецПопытки
			for j := i + 1; j < len(lines); j++ {
				trimmed := strings.TrimSpace(lines[j])
				if trimmed == "" {
					continue
				}
				if reTryEnd.MatchString(trimmed) {
					return 1
				}
				break // has code in catch block
			}
		}
	}
	return 0
}

// analyzeNesting returns max nesting depth and cyclomatic complexity.
func analyzeNesting(lines []string) (maxNest int, complexity int) {
	current := 0
	complexity = 1 // base complexity

	for _, line := range lines {
		opens := len(reNestOpen.FindAllString(line, -1))
		closes := len(reNestClose.FindAllString(line, -1))

		current += opens
		if current > maxNest {
			maxNest = current
		}
		current -= closes
		if current < 0 {
			current = 0
		}

		// Complexity: count decision points
		complexity += len(reIfStart.FindAllString(line, -1))
		complexity += len(reElseIf.FindAllString(line, -1))
		complexity += len(reForLoop.FindAllString(line, -1))
		complexity += len(reWhileLoop.FindAllString(line, -1))
	}

	return maxNest, complexity
}

// calcDocCoverage returns ratio of documented functions (0.0-1.0).
func calcDocCoverage(lines []string) float64 {
	totalFuncs := 0
	documentedFuncs := 0

	for i, line := range lines {
		if reFuncStart.MatchString(line) {
			totalFuncs++
			// Check if previous non-empty line is a comment
			for j := i - 1; j >= 0; j-- {
				trimmed := strings.TrimSpace(lines[j])
				if trimmed == "" {
					continue
				}
				if reComment.MatchString(lines[j]) {
					documentedFuncs++
				}
				break
			}
		}
	}

	if totalFuncs == 0 {
		return 0
	}
	return float64(documentedFuncs) / float64(totalFuncs)
}

func boolToFloat(b bool) float64 {
	if b {
		return 1
	}
	return 0
}
