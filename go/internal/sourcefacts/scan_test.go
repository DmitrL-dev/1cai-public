package sourcefacts

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"
)

func bufferObject(id int, raw []byte) map[string]any {
	hash := sha256.Sum256(raw)
	return map[string]any{"entry_id": id, "size_bytes": len(raw), "raw_sha256": hex.EncodeToString(hash[:]), "data_base64": base64.StdEncoding.EncodeToString(raw)}
}
func requestObject(caller, candidate string, selection Span, alias bool) map[string]any {
	c := map[string]any{"kind": "distinct_entry", "buffer": bufferObject(1, []byte(candidate))}
	if alias {
		c = map[string]any{"kind": "same_as_caller"}
	}
	return map[string]any{"protocol": Protocol, "caller": bufferObject(0, []byte(caller)), "candidate": c, "selection": selection}
}
func mustJSON(t *testing.T, v any) []byte {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return raw
}
func selectionOf(t *testing.T, source, text string) Span {
	t.Helper()
	n := strings.Index(source, text)
	if n < 0 {
		t.Fatal("test selector missing")
	}
	return Span{n, n + len(text)}
}
func evaluateObject(t *testing.T, obj map[string]any) map[string]any {
	t.Helper()
	raw, code := Evaluate(mustJSON(t, obj))
	if code != "" {
		t.Fatalf("unexpected code: %s", code)
	}
	result, ok := parseObject(raw)
	if !ok {
		t.Fatal("invalid response JSON")
	}
	return result
}
func observedState(t *testing.T, value any, want string) map[string]any {
	t.Helper()
	obj, ok := value.(map[string]any)
	if !ok {
		t.Fatal("response value not object")
	}
	if obj["state"] != want {
		t.Fatalf("state = %v, want %s", obj["state"], want)
	}
	return obj
}
func expectReason(t *testing.T, value any, reason string) {
	t.Helper()
	obj := observedState(t, value, "unavailable")
	if obj["reason"] != reason || len(obj) != 2 {
		t.Fatalf("wrong unavailable shape/reason: %v", obj)
	}
}
func responseSpan(t *testing.T, obj map[string]any, key string) Span {
	t.Helper()
	s, ok := object(obj[key], "start", "end")
	if !ok {
		t.Fatal("wrong span shape")
	}
	start, a := uintField(s["start"], MaxSourceBytes)
	end, b := uintField(s["end"], MaxSourceBytes)
	if !a || !b {
		t.Fatal("wrong span integer")
	}
	return Span{start, end}
}

func TestQualifiedSelectorAndBothExportValues(t *testing.T) {
	for _, exported := range []bool{false, true} {
		marker := ""
		if exported {
			marker = " Export"
		}
		caller := "\ufeff// leading 🦊\r\nProcedure Caller(Module)\r\n  Return Module . Target (\r\n[1,2], \"decoy.A()\");\nEndProcedure\r\n"
		candidate := "//comment\nFunction tArGeT(Val Arg, Знач Параметр)" + marker + " // trailing\nReturn 0;\nКонецФункции\n"
		selection := selectionOf(t, caller, "Module . Target")
		result := evaluateObject(t, requestObject(caller, candidate, selection, false))
		if result["protocol"] != Protocol || result["status"] != "ok" || len(result) != 6 {
			t.Fatal("wrong success root")
		}
		s := observedState(t, result["selector"], "observed")
		if got := responseSpan(t, s, "selector_span"); got != selection {
			t.Fatal("selection changed")
		}
		receiver, method := responseSpan(t, s, "receiver_span"), responseSpan(t, s, "method_span")
		if caller[receiver.Start:receiver.End] != "Module" || caller[method.Start:method.End] != "Target" {
			t.Fatal("not exact raw selector token spans")
		}
		routine := responseSpan(t, s, "routine_span")
		if !strings.HasPrefix(caller[routine.Start:routine.End], "Procedure Caller") || !strings.HasSuffix(caller[routine.Start:routine.End], "EndProcedure") {
			t.Fatal("bad caller routine span")
		}
		h := observedState(t, result["header"], "observed")
		if h["export"] != exported {
			t.Fatal("wrong export value")
		}
		header := responseSpan(t, h, "header_span")
		if candidate[header.Start:header.End] != "Function tArGeT(Val Arg, Знач Параметр)"+marker {
			t.Fatal("bad header extent")
		}
		name := responseSpan(t, h, "name_span")
		if candidate[name.Start:name.End] != "tArGeT" {
			t.Fatal("bad name extent")
		}
		if exported {
			export := responseSpan(t, h, "export_span")
			if candidate[export.Start:export.End] != "Export" {
				t.Fatal("bad export span")
			}
		} else if h["export_span"] != nil {
			t.Fatal("false export requires explicit null")
		}
	}
}

func TestRussianMixedKeywordsAndRawByteSpans(t *testing.T) {
	caller := "\ufeffПроцедура Вызов(знач Модуль)\r\nВозврат МОДУЛЬ.МЕТОД (\"a\"\"b\", [1,2]);\r\nEndProcedure"
	candidate := "Function Метод() Экспорт\r\nКонецФункции"
	span := selectionOf(t, caller, "МОДУЛЬ.МЕТОД")
	result := evaluateObject(t, requestObject(caller, candidate, span, false))
	observedState(t, result["selector"], "observed")
	h := observedState(t, result["header"], "observed")
	s := responseSpan(t, h, "export_span")
	if candidate[s.Start:s.End] != "Экспорт" {
		t.Fatal("Cyrillic offsets are not raw bytes")
	}
}

func TestSelectionIsExactAndDoesNotChooseFirst(t *testing.T) {
	caller := wrapped("// Module.Target()\n\"Module.Target()\"; Other.First(); Module.Target(); Other.Last();")
	candidate := "Procedure Target()\nEndProcedure"
	start := strings.LastIndex(caller, "Module.Target")
	span := Span{start, start + len("Module.Target")}
	result := evaluateObject(t, requestObject(caller, candidate, span, false))
	if got := responseSpan(t, observedState(t, result["selector"], "observed"), "selector_span"); got != span {
		t.Fatal("selected an approximate occurrence")
	}
	for _, span := range []Span{{start, start + len("Module.Target") - 1}, {start + 1, start + len("Module.Target")}, selectionOf(t, caller, "Module.Target")} {
		r := evaluateObject(t, requestObject(caller, candidate, span, false))
		expectReason(t, r["selector"], "selector_span_invalid")
	}
}

func TestSelectorReasons(t *testing.T) {
	cases := []struct{ body, selected, reason string }{
		{"R.M()", "R.M", ""},
		{"If R.M()", "R.M", ""},
		{"Возврат R.M()", "R.M", ""},
		{"x = R.M([1,(2)]);", "R.M", ""},
		{"x R.M()", "R.M", "selector_chained"},
		{"x\nR.M()", "R.M", "selector_chained"},
		{"New R.M()", "R.M", "selector_chained"},
		{"x.R.M()", "R.M", "selector_chained"},
		{"(R).M()", "R).M", "selector_not_qualified"},
		{"R.M().X()", "R.M", "selector_chained"},
		{"R.M()[1]", "R.M", "selector_chained"},
		{"R.M()()", "R.M", "selector_chained"},
		{"R.M()\n.X()", "R.M", "selector_chained"},
		{"R.M", "R.M", "selector_not_qualified"},
		{"R.\nM()", "R.\nM", "selector_not_qualified"},
		{"R.M\n()", "R.M", "selector_not_qualified"},
		{"R.//comment\nM()", "R.//comment\nM", "selector_not_qualified"},
		{"If.M()", "If.M", "selector_not_qualified"},
		{"R.Return()", "R.Return", "selector_not_qualified"},
		{"R.M()", "R.M()", "selector_not_qualified"},
	}
	for _, tt := range cases {
		t.Run(tt.body, func(t *testing.T) {
			caller := wrapped(tt.body)
			result := evaluateObject(t, requestObject(caller, "Procedure M()\nEndProcedure", selectionOf(t, caller, tt.selected), false))
			if tt.reason == "" {
				observedState(t, result["selector"], "observed")
			} else {
				expectReason(t, result["selector"], tt.reason)
				expectReason(t, result["header"], "selector_unavailable")
			}
		})
	}
}

func TestMalformedAndOutsideSelection(t *testing.T) {
	caller := wrapped("Р.М();")
	for _, span := range []Span{{0, 0}, {4, 3}, {0, MaxSourceBytes}, {strings.Index(caller, "Р") + 1, strings.Index(caller, "М") + 2}} {
		r := evaluateObject(t, requestObject(caller, "", span, false))
		expectReason(t, r["selector"], "selector_span_invalid")
	}
	for _, text := range []string{"Procedure", "Caller", "EndProcedure"} {
		r := evaluateObject(t, requestObject(caller, "", selectionOf(t, caller, text), false))
		expectReason(t, r["selector"], "selector_outside_body")
	}
}

func TestIndependentAdmissionAndHeaderPrecedence(t *testing.T) {
	caller := wrapped("R.M();")
	selection := selectionOf(t, caller, "R.M")
	for _, candidate := range []string{"#", "Procedure M()\nEndProcedure\nProcedure m()\nEndProcedure"} {
		r := evaluateObject(t, requestObject(caller, candidate, selection, false))
		observedState(t, r["selector"], "observed")
		expectReason(t, r["header"], "candidate_not_admitted")
		ad := r["candidate"].(map[string]any)["admission"]
		observedState(t, ad, "unavailable")
	}
	badCaller := caller + "\n#"
	r := evaluateObject(t, requestObject(badCaller, "#", selection, false))
	expectReason(t, r["selector"], "caller_not_admitted")
	expectReason(t, r["header"], "selector_unavailable")
	r = evaluateObject(t, requestObject(caller, "", selection, false))
	expectReason(t, r["header"], "declaration_unavailable")
}

func TestAliasAndBindingNegativeShapes(t *testing.T) {
	for _, receiver := range []string{"Module", "Server", "ThisObject", "ЭтотОбъект"} {
		source := "Procedure Caller(" + receiver + ")\nVar Local;\n" + receiver + ".Target();\nEndProcedure\nProcedure Target() Export\nEndProcedure"
		r := evaluateObject(t, requestObject(source, "", selectionOf(t, source, receiver+".Target"), true))
		observedState(t, r["selector"], "observed")
		observedState(t, r["header"], "observed")
		if !bytes.Equal(mustJSON(t, r["caller"]), mustJSON(t, r["candidate"])) {
			t.Fatal("alias admission differs")
		}
		if _, exists := r["receiver_binding"]; exists {
			t.Fatal("scanner emitted binding")
		}
	}
}

func TestResponsePrivacyAndSourcePreservation(t *testing.T) {
	canary := "PrivateCanary_73194"
	caller := wrapped(canary + ".Target(\"" + canary + "\"); // " + canary)
	candidate := "Procedure Target() Export\n// " + canary + "\nEndProcedure"
	raw := mustJSON(t, requestObject(caller, candidate, selectionOf(t, caller, canary+".Target"), false))
	before := append([]byte(nil), raw...)
	out, code := Evaluate(raw)
	if code != "" || bytes.Contains(out, []byte(canary)) || bytes.Contains(out, []byte("Target")) {
		t.Fatal("source identity or literal leaked")
	}
	if !bytes.Equal(raw, before) {
		t.Fatal("request bytes mutated")
	}
	for _, source := range []string{"\"" + canary, "#" + canary, "Procedure " + canary + "(\n"} {
		errOut, _ := Evaluate(mustJSON(t, requestObject(source, source, Span{0, 1}, false)))
		if bytes.Contains(errOut, []byte(canary)) {
			t.Fatal("abstention disclosed source")
		}
	}
}

func TestHeaderEqualityDoesNotFoldLookalikesOrYo(t *testing.T) {
	for _, names := range [][2]string{{"Ё", "Е"}, {"A", "А"}, {"P", "Р"}} {
		caller := wrapped("R." + names[0] + "();")
		candidate := "Procedure " + names[1] + "() Export\nEndProcedure"
		r := evaluateObject(t, requestObject(caller, candidate, selectionOf(t, caller, "R."+names[0]), false))
		observedState(t, r["selector"], "observed")
		expectReason(t, r["header"], "declaration_unavailable")
	}
}
