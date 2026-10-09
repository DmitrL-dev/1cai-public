package sourcefacts

type routine struct {
	span      Span
	header    Span
	name      Span
	key       string
	exported  *Span
	bodyStart int // Token indices, exclusive of header and terminator.
	bodyEnd   int
}

type module struct {
	tokens   []token
	routines []routine
	reason   string
}

func admit(raw []byte) module {
	tokens, reason := lex(raw)
	if reason != "" {
		return module{reason: reason}
	}
	m := module{tokens: tokens}
	seen := make(map[string]bool)
	for i := 0; i < len(tokens); {
		kind := structural(tokens[i].word)
		if kind != procedureOpen && kind != functionOpen {
			if kind != notStructural {
				return module{reason: "stray_structural_keyword"}
			}
			return module{reason: "unsupported_top_level"}
		}
		if len(m.routines) == maxRoutines {
			return module{reason: "routine_limit"}
		}
		j := i + 1
		for j < len(tokens) && tokens[j].line == tokens[i].line {
			j++
		}
		r, reason := parseHeader(tokens[i:j])
		if reason != "" {
			return module{reason: reason}
		}
		if seen[r.key] {
			return module{reason: "duplicate_routine"}
		}
		seen[r.key] = true
		r.bodyStart = j
		var stack []int
		terminated := false
		for j < len(tokens) {
			t := tokens[j]
			s := structural(t.word)
			if s == procedureOpen || s == functionOpen {
				if j > 0 && tokens[j-1].line == t.line {
					return module{reason: "stray_structural_keyword"}
				}
				return module{reason: "nested_routine"}
			}
			if s == procedureEnd || s == functionEnd {
				if j > 0 && tokens[j-1].line == t.line || j+1 < len(tokens) && tokens[j+1].line == t.line {
					return module{reason: "stray_structural_keyword"}
				}
				if kind == procedureOpen && s != procedureEnd || kind == functionOpen && s != functionEnd {
					return module{reason: "mismatched_terminator"}
				}
				if len(stack) != 0 {
					return module{reason: "unbalanced_delimiter"}
				}
				r.bodyEnd, r.span.End = j, t.span.End
				j++
				terminated = true
				break
			}
			if s != notStructural {
				return module{reason: "stray_structural_keyword"}
			}
			switch t.word {
			case "(", "[":
				if len(stack) == maxDelimiterDepth {
					return module{reason: "delimiter_depth_limit"}
				}
				stack = append(stack, j)
			case ")", "]":
				if len(stack) == 0 {
					return module{reason: "unbalanced_delimiter"}
				}
				open := stack[len(stack)-1]
				if tokens[open].word == "(" && t.word != ")" || tokens[open].word == "[" && t.word != "]" {
					return module{reason: "unbalanced_delimiter"}
				}
				tokens[open].mate, tokens[j].mate = j, open
				stack = stack[:len(stack)-1]
			}
			j++
		}
		if !terminated {
			return module{reason: "missing_terminator"}
		}
		m.routines = append(m.routines, r)
		i = j
	}
	return m
}

// reservedName is intentionally a frozen denylist, not a BSL language table.
func reservedName(word string) bool {
	if structural(word) != notStructural || forbiddenKeyword(word) {
		return true
	}
	switch word {
	case "if", "если", "then", "тогда", "elsif", "иначеесли", "else", "иначе", "endif", "конецесли", "elseif",
		"for", "для", "each", "каждого", "in", "из", "to", "по", "while", "пока", "do", "цикл", "enddo", "конеццикла",
		"return", "возврат", "continue", "продолжить", "break", "прервать", "var", "перем",
		"and", "и", "or", "или", "not", "не", "new", "новый", "goto", "перейти",
		"true", "истина", "false", "ложь", "undefined", "неопределено", "null",
		"try", "попытка", "except", "исключение", "endtry", "конецпопытки", "raise", "вызватьисключение",
		"addhandler", "добавитьобработчик", "removehandler", "удалитьобработчик":
		return true
	}
	return false
}

func parseHeader(ts []token) (routine, string) {
	bad := func(reason string) (routine, string) { return routine{}, reason }
	if len(ts) < 4 || ts[1].kind != identifier || reservedName(ts[1].word) || ts[2].word != "(" {
		return bad("invalid_header")
	}
	r := routine{span: Span{Start: ts[0].span.Start}, name: ts[1].span, key: ts[1].word}
	i := 3
	seen := make(map[string]bool)
	if i < len(ts) && ts[i].word != ")" {
		for {
			if i < len(ts) && structural(ts[i].word) == valKeyword {
				i++
			}
			if i >= len(ts) || ts[i].kind != identifier || reservedName(ts[i].word) {
				return bad("invalid_header")
			}
			if len(seen) == maxParameters {
				return bad("parameter_limit")
			}
			if seen[ts[i].word] {
				return bad("duplicate_parameter")
			}
			seen[ts[i].word] = true
			i++
			if i < len(ts) && ts[i].word == "," {
				i++
				continue
			}
			break
		}
	}
	if i >= len(ts) || ts[i].word != ")" {
		return bad("invalid_header")
	}
	r.header = Span{ts[0].span.Start, ts[i].span.End}
	i++
	if i < len(ts) && structural(ts[i].word) == exportKeyword {
		s := ts[i].span
		r.exported, r.header.End = &s, s.End
		i++
	}
	if i != len(ts) {
		return bad("invalid_header")
	}
	return r, ""
}
