package sourcefacts

import "unicode/utf8"

type tokenKind uint8

const (
	identifier tokenKind = iota
	punctuation
	stringToken
	numberToken
)

type token struct {
	span Span
	line int
	kind tokenKind
	word string // Private comparison spelling only; never serialized.
	mate int
}

func identStart(r rune) bool {
	return r == '_' || r >= 'A' && r <= 'Z' || r >= 'a' && r <= 'z' ||
		r >= 'А' && r <= 'Я' || r >= 'а' && r <= 'я' || r == 'Ё' || r == 'ё'
}
func identPart(r rune) bool { return identStart(r) || r >= '0' && r <= '9' }

// identEqualKey is deliberately narrower than Unicode case folding/NFC.
func identEqualKey(raw []byte) string {
	out := make([]rune, 0, len(raw))
	for _, r := range string(raw) {
		switch {
		case r >= 'A' && r <= 'Z':
			r += 'a' - 'A'
		case r >= 'А' && r <= 'Я':
			r += 'а' - 'А'
		case r == 'Ё':
			r = 'ё'
		}
		out = append(out, r)
	}
	return string(out)
}

func forbiddenKeyword(word string) bool {
	switch word {
	case "execute", "выполнить", "eval", "вычислить", "async", "асинх", "await", "ждать":
		return true
	}
	return false
}

type structuralKind uint8

const (
	notStructural structuralKind = iota
	procedureOpen
	functionOpen
	procedureEnd
	functionEnd
	exportKeyword
	valKeyword
)

func structural(word string) structuralKind {
	switch word {
	case "procedure", "процедура":
		return procedureOpen
	case "function", "функция":
		return functionOpen
	case "endprocedure", "конецпроцедуры":
		return procedureEnd
	case "endfunction", "конецфункции":
		return functionEnd
	case "export", "экспорт":
		return exportKeyword
	case "val", "знач":
		return valKeyword
	}
	return notStructural
}

func preflight(raw []byte) string {
	if !utf8.Valid(raw) {
		return "invalid_utf8"
	}
	for i, r := range string(raw) {
		if r == '\ufeff' && i != 0 {
			return "invalid_bom"
		}
	}
	for _, r := range string(raw) {
		if r < 0x20 && r != '\t' && r != '\n' && r != '\r' || r >= 0x7f && r <= 0x9f {
			return "forbidden_control"
		}
	}
	for i, c := range raw {
		if c == '\r' && (i+1 == len(raw) || raw[i+1] != '\n') {
			return "invalid_line_ending"
		}
	}
	return ""
}

func lex(raw []byte) ([]token, string) {
	if reason := preflight(raw); reason != "" {
		return nil, reason
	}
	tokens := make([]token, 0)
	line, i := 0, 0
	if len(raw) >= 3 && raw[0] == 0xef && raw[1] == 0xbb && raw[2] == 0xbf {
		i = 3
	}
	for i < len(raw) {
		switch raw[i] {
		case ' ', '\t':
			i++
			continue
		case '\r':
			i += 2
			line++
			continue
		case '\n':
			i++
			line++
			continue
		}
		start := i
		if raw[i] == '/' && i+1 < len(raw) && raw[i+1] == '/' {
			i += 2
			for i < len(raw) && raw[i] != '\r' && raw[i] != '\n' {
				i++
			}
			if i-start > maxStringCommentBytes {
				return nil, "token_bytes_limit"
			}
			continue
		}
		// Comments are not tokens. Every other code position consumes a token
		// budget before its classification, even when that classification fails.
		if len(tokens) == maxTokens {
			return nil, "token_count_limit"
		}
		r, width := utf8.DecodeRune(raw[i:])
		t := token{line: line, mate: -1}
		switch {
		case identStart(r):
			i += width
			count := 1
			for i < len(raw) {
				r, width = utf8.DecodeRune(raw[i:])
				if !identPart(r) {
					break
				}
				i += width
				count++
			}
			if count > maxIdentifierRunes || i-start > maxIdentifierBytes {
				return nil, "identifier_limit"
			}
			t.kind, t.word = identifier, identEqualKey(raw[start:i])
			if forbiddenKeyword(t.word) {
				return nil, "unsupported_keyword"
			}
		case raw[i] == '"':
			i++
			closed := false
			for i < len(raw) && raw[i] != '\r' && raw[i] != '\n' {
				if raw[i] == '"' {
					i++
					if i < len(raw) && raw[i] == '"' {
						i++
						continue
					}
					closed = true
					break
				}
				i++
			}
			if i-start > maxStringCommentBytes {
				return nil, "token_bytes_limit"
			}
			if !closed {
				if i < len(raw) {
					return nil, "multiline_string"
				}
				return nil, "unterminated_string"
			}
			t.kind = stringToken
		case raw[i] == '\'':
			return nil, "unsupported_literal"
		case raw[i] >= '0' && raw[i] <= '9' || raw[i] == '.' && i+1 < len(raw) && raw[i+1] >= '0' && raw[i+1] <= '9':
			i += width
			for i < len(raw) {
				r, width = utf8.DecodeRune(raw[i:])
				if r != '.' && !identPart(r) {
					break
				}
				i += width
			}
			if i-start > maxNumberBytes {
				return nil, "token_bytes_limit"
			}
			if !numberValid(raw[start:i]) {
				return nil, "invalid_number"
			}
			t.kind = numberToken
		default:
			switch raw[i] {
			case '(', ')', '[', ']', '.', ',', ';', '=', '+', '-', '*', '/', '%', '<', '>':
				i++
				if i < len(raw) && (raw[start] == '<' && (raw[i] == '=' || raw[i] == '>') || raw[start] == '>' && raw[i] == '=') {
					i++
				}
				t.kind, t.word = punctuation, string(raw[start:i])
			default:
				return nil, "unsupported_code_character"
			}
		}
		t.span = Span{start, i}
		tokens = append(tokens, t)
	}
	return tokens, ""
}

func numberValid(raw []byte) bool {
	i := 0
	for i < len(raw) && raw[i] >= '0' && raw[i] <= '9' {
		i++
	}
	if i == 0 {
		return false
	}
	if i == len(raw) {
		return true
	}
	if raw[i] != '.' {
		return false
	}
	i++
	first := i
	for i < len(raw) && raw[i] >= '0' && raw[i] <= '9' {
		i++
	}
	return i > first && i == len(raw)
}
