package extractor

import (
	"strings"
	"unicode"
)

// bslToken retains physical Unicode character coordinates. Comments are absent;
// a whole string literal is one token, including doubled quotes/continuations.
type bslToken struct {
	text                             string
	kind                             byte // i: identifier, s: string, p: punctuation
	line, column, endLine, endColumn int
}

func lexBSL(code string) []bslToken {
	runes := []rune(strings.TrimPrefix(code, "\ufeff"))
	var tokens []bslToken
	line, column := 1, 1
	i := 0
	advance := func() {
		if runes[i] == '\n' {
			line++
			column = 1
		} else {
			column++
		}
		i++
	}
	for i < len(runes) {
		if unicode.IsSpace(runes[i]) {
			advance()
			continue
		}
		if runes[i] == '/' && i+1 < len(runes) && runes[i+1] == '/' {
			for i < len(runes) && runes[i] != '\n' {
				advance()
			}
			continue
		}
		start := i
		t := bslToken{kind: 'p', line: line, column: column}
		switch {
		case runes[i] == '"':
			t.kind = 's'
			advance()
			for i < len(runes) {
				if runes[i] == '"' {
					advance()
					if i < len(runes) && runes[i] == '"' {
						advance()
						continue
					}
					break
				}
				advance()
			}
		case unicode.IsLetter(runes[i]) || runes[i] == '_':
			t.kind = 'i'
			advance()
			for i < len(runes) && (unicode.IsLetter(runes[i]) || unicode.IsDigit(runes[i]) || runes[i] == '_') {
				advance()
			}
		default:
			advance()
		}
		t.text = string(runes[start:i])
		t.endLine, t.endColumn = line, column
		tokens = append(tokens, t)
	}
	return tokens
}

func tokenIs(t bslToken, names ...string) bool {
	for _, name := range names {
		if strings.EqualFold(t.text, name) {
			return true
		}
	}
	return false
}

// delimiterPairs supports declaration parameter lists and computed receivers.
func delimiterPairs(tokens []bslToken) map[int]int {
	pairs := make(map[int]int)
	var stack []int
	for i, t := range tokens {
		switch t.text {
		case "(", "[":
			stack = append(stack, i)
		case ")", "]":
			if len(stack) == 0 {
				continue
			}
			j := stack[len(stack)-1]
			if (tokens[j].text == "(") != (t.text == ")") {
				continue
			}
			stack = stack[:len(stack)-1]
			pairs[i], pairs[j] = j, i
		}
	}
	return pairs
}
