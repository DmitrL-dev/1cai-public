package sourcefacts

import (
	"encoding/json"
	"unicode/utf8"
)

type admission struct {
	State  string `json:"state"`
	Reason string `json:"reason,omitempty"`
}

type admissionRecord struct {
	EntryID   int       `json:"entry_id"`
	SizeBytes int       `json:"size_bytes"`
	RawSHA256 string    `json:"raw_sha256"`
	Admission admission `json:"admission"`
}

type unavailable struct {
	State  string `json:"state"`
	Reason string `json:"reason"`
}

type selectorObserved struct {
	State        string `json:"state"`
	EntryID      int    `json:"entry_id"`
	RoutineSpan  Span   `json:"routine_span"`
	SelectorSpan Span   `json:"selector_span"`
	ReceiverSpan Span   `json:"receiver_span"`
	MethodSpan   Span   `json:"method_span"`
}

type headerObserved struct {
	State       string `json:"state"`
	EntryID     int    `json:"entry_id"`
	RoutineSpan Span   `json:"routine_span"`
	HeaderSpan  Span   `json:"header_span"`
	NameSpan    Span   `json:"name_span"`
	Export      bool   `json:"export"`
	ExportSpan  *Span  `json:"export_span"`
}

type response struct {
	Protocol  string          `json:"protocol"`
	Status    string          `json:"status"`
	Caller    admissionRecord `json:"caller"`
	Candidate admissionRecord `json:"candidate"`
	Selector  any             `json:"selector"`
	Header    any             `json:"header"`
}

// Evaluate accepts a single unframed request. It performs no IO and returns only
// bounded JSON with byte spans, echoed byte claims and fixed enum values.
func Evaluate(raw []byte) (out []byte, code Code) {
	defer func() {
		if recover() != nil {
			out, code = ErrorResponse(InternalError), InternalError
		}
	}()
	r, code := decodeRequest(raw)
	if code != "" {
		return ErrorResponse(code), code
	}
	caller := admit(r.caller.data)
	candidate := caller
	if !r.alias {
		candidate = admit(r.candidate.data)
	}
	result := response{Protocol: Protocol, Status: "ok", Caller: record(r.caller, caller), Candidate: record(r.candidate, candidate)}
	selected, method, reason := selectSelector(r.caller, caller, r.selection)
	if reason != "" {
		result.Selector = unavailable{"unavailable", reason}
		result.Header = unavailable{"unavailable", "selector_unavailable"}
	} else {
		result.Selector = selected
		result.Header = selectHeader(r.candidate, candidate, method)
	}
	out, err := json.Marshal(result)
	if err != nil || len(out) > MaxResponseBytes {
		return ErrorResponse(InternalError), InternalError
	}
	return out, ""
}

func ErrorResponse(code Code) []byte {
	switch code {
	case InvalidRequest, InputLimit, HashMismatch, SizeMismatch, IOError, InternalError:
	default:
		code = InternalError
	}
	return []byte(`{"protocol":"source_fact_scan_v1","status":"error","code":"` + string(code) + `"}`)
}

func record(b buffer, m module) admissionRecord {
	a := admission{State: "admitted"}
	if m.reason != "" {
		a = admission{State: "unavailable", Reason: m.reason}
	}
	return admissionRecord{b.entryID, b.size, b.hash, a}
}

func boundary(raw []byte, n int) bool {
	return n >= 0 && n <= len(raw) && (n == len(raw) || utf8.RuneStart(raw[n]))
}

func selectSelector(b buffer, m module, span Span) (selectorObserved, string, string) {
	bad := func(reason string) (selectorObserved, string, string) { return selectorObserved{}, "", reason }
	if m.reason != "" {
		return bad("caller_not_admitted")
	}
	if span.Start >= span.End || !boundary(b.data, span.Start) || !boundary(b.data, span.End) {
		return bad("selector_span_invalid")
	}
	start, end := -1, -1
	for i, t := range m.tokens {
		if t.span.Start == span.Start {
			start = i
		}
		if t.span.End == span.End {
			end = i
		}
	}
	if start < 0 || end < start {
		return bad("selector_span_invalid")
	}
	var enclosing *routine
	for i := range m.routines {
		r := &m.routines[i]
		if start >= r.bodyStart && end < r.bodyEnd {
			enclosing = r
			break
		}
	}
	if enclosing == nil {
		return bad("selector_outside_body")
	}
	ts := m.tokens
	if end != start+2 || start+3 >= enclosing.bodyEnd || ts[start].kind != identifier ||
		ts[start+1].word != "." || ts[start+2].kind != identifier || ts[start+3].word != "(" ||
		reservedName(ts[start].word) || reservedName(ts[start+2].word) {
		return bad("selector_not_qualified")
	}
	for i := start + 1; i <= start+3; i++ {
		if ts[i].line != ts[start].line || !horizontalSpace(b.data[ts[i-1].span.End:ts[i].span.Start]) {
			return bad("selector_not_qualified")
		}
	}
	if start > enclosing.bodyStart && !selectorPredecessor(ts[start-1]) {
		return bad("selector_chained")
	}
	close := ts[start+3].mate
	if close < 0 || close >= enclosing.bodyEnd {
		return bad("selector_not_qualified")
	}
	if close+1 < enclosing.bodyEnd {
		switch ts[close+1].word {
		case ".", "[", "(":
			return bad("selector_chained")
		}
	}
	return selectorObserved{"observed", b.entryID, enclosing.span, span, ts[start].span, ts[start+2].span}, ts[start+2].word, ""
}

func horizontalSpace(raw []byte) bool {
	for _, c := range raw {
		if c != ' ' && c != '\t' {
			return false
		}
	}
	return true
}

func selectorPredecessor(t token) bool {
	if t.kind == punctuation {
		switch t.word {
		case ";", "=", "(", "[", ",", "+", "-", "*", "/", "%", "<", ">", "<=", ">=", "<>":
			return true
		}
	}
	if t.kind == identifier {
		switch t.word {
		case "return", "возврат", "if", "если", "while", "пока", "not", "не", "and", "и", "or", "или":
			return true
		}
	}
	return false
}

func selectHeader(b buffer, m module, method string) any {
	if m.reason != "" {
		return unavailable{"unavailable", "candidate_not_admitted"}
	}
	for _, r := range m.routines {
		if r.key == method {
			return headerObserved{"observed", b.entryID, r.span, r.header, r.name, r.exported != nil, r.exported}
		}
	}
	return unavailable{"unavailable", "declaration_unavailable"}
}
