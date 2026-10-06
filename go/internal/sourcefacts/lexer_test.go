package sourcefacts

import (
	"fmt"
	"strings"
	"testing"
)

func wrapped(body string) string { return "Procedure Caller()\n" + body + "\nEndProcedure" }

func TestAdmissionReasons(t *testing.T) {
	tests := []struct{ name, source, reason string }{
		{"utf8", wrapped("\xff"), "invalid_utf8"},
		{"utf8_in_comment", wrapped("//\xff"), "invalid_utf8"},
		{"bom_twice", "\ufeff\ufeff" + wrapped(""), "invalid_bom"},
		{"bom_string", wrapped("\"\ufeff\""), "invalid_bom"},
		{"nul_comment", wrapped("//\x00"), "forbidden_control"},
		{"c1_string", wrapped("\"\u0085\""), "forbidden_control"},
		{"bare_cr", wrapped("x\ry"), "invalid_line_ending"},
		{"unicode_space", wrapped("A\u00a0.B()"), "unsupported_code_character"},
		{"combining", wrapped("A\u0301.B()"), "unsupported_code_character"},
		{"identifier", wrapped(strings.Repeat("я", 129)), "identifier_limit"},
		{"string_bytes", wrapped("\"" + strings.Repeat("x", 65535) + "\""), "token_bytes_limit"},
		{"comment_bytes", wrapped("//" + strings.Repeat("x", 65535)), "token_bytes_limit"},
		{"number_bytes", wrapped(strings.Repeat("9", 129)), "token_bytes_limit"},
		{"token_count", wrapped(strings.Repeat(";", maxTokens-4)), "token_count_limit"},
		{"number", wrapped("1.2.3"), "invalid_number"},
		{"date", wrapped("'20260101'"), "unsupported_literal"},
		{"unterminated", "Procedure Caller()\n\"secret", "unterminated_string"},
		{"multiline", wrapped("\"secret\nstill string\""), "multiline_string"},
		{"keyword", wrapped("harmless.Execute()"), "unsupported_keyword"},
		{"top_level", "Var A;", "unsupported_top_level"},
		{"header_default", "Procedure P(A=1)\nEndProcedure", "invalid_header"},
		{"header_multiline", "Procedure P(\nA)\nEndProcedure", "invalid_header"},
		{"header_reserved", "Procedure If()\nEndProcedure", "invalid_header"},
		{"parameter_reserved", "Procedure P(Return)\nEndProcedure", "invalid_header"},
		{"parameter_duplicate", "Procedure P(А,а)\nEndProcedure", "duplicate_parameter"},
		{"parameter_limit", parameterSource(maxParameters + 1), "parameter_limit"},
		{"routine_duplicate", "Procedure P()\nEndProcedure\nFunction p()\nEndFunction", "duplicate_routine"},
		{"routine_limit", routineSource(maxRoutines + 1), "routine_limit"},
		{"nested", "Procedure P()\nProcedure Q()\nEndProcedure", "nested_routine"},
		{"embedded_opener", wrapped("R.Procedure();"), "stray_structural_keyword"},
		{"embedded_wrong_terminator", wrapped("R.EndFunction();"), "stray_structural_keyword"},
		{"mismatch", "Procedure P()\nEndFunction", "mismatched_terminator"},
		{"missing", "Procedure P()\nA.B();", "missing_terminator"},
		{"stray", wrapped("Export"), "stray_structural_keyword"},
		{"terminator_semicolon", "Procedure P()\nEndProcedure;", "stray_structural_keyword"},
		{"terminator_inline", "Procedure P()\nx; EndProcedure", "stray_structural_keyword"},
		{"stray_terminator", "EndProcedure", "stray_structural_keyword"},
		{"unbalanced", wrapped("([)]"), "unbalanced_delimiter"},
		{"unclosed", wrapped("("), "unbalanced_delimiter"},
		{"delimiter_depth", wrapped(strings.Repeat("(", maxDelimiterDepth+1) + strings.Repeat(")", maxDelimiterDepth+1)), "delimiter_depth_limit"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := admit([]byte(tt.source))
			if got.reason != tt.reason {
				t.Fatalf("reason = %q, want %q", got.reason, tt.reason)
			}
			if len(got.routines) != 0 || len(got.tokens) != 0 {
				t.Fatal("unavailable admission retained partial facts")
			}
		})
	}
}

func TestAdmissionPrecedence(t *testing.T) {
	tests := []struct{ source, reason string }{
		{"\ufeff\ufeff\x00\r\xff", "invalid_utf8"},
		{"\x00\r\ufeff", "invalid_bom"},
		{"\r\x00", "forbidden_control"},
		{"#\r", "invalid_line_ending"},
		{"Var A;\n#", "unsupported_code_character"},
		{"Procedure P()\n)\n", "unbalanced_delimiter"},
		{"Procedure P()\n(\n", "missing_terminator"},
		{"Procedure P()\n(\nEndProcedure", "unbalanced_delimiter"},
		{wrapped(strings.Repeat(";", maxTokens-4) + "#"), "token_count_limit"},
		{wrapped(strings.Repeat("9", 129) + "e"), "token_bytes_limit"},
	}
	for _, tt := range tests {
		if got := admit([]byte(tt.source)).reason; got != tt.reason {
			t.Errorf("reason = %q, want %q", got, tt.reason)
		}
	}
}

func TestClosedLexicalAlphabetAndNumbers(t *testing.T) {
	for _, source := range []string{"1e2", "12x", ".5", "2.", "1.2.3", "0xFF", "3_", "2.Метод"} {
		if got := admit([]byte(wrapped(source))).reason; got != "invalid_number" {
			t.Errorf("%q: %q", source, got)
		}
	}
	for _, source := range []string{"#", "&", "~", ":", "?", "|", "{", "}", "\\", "@", "`", "é", "ß", "İ"} {
		if got := admit([]byte(wrapped(source))).reason; got != "unsupported_code_character" {
			t.Errorf("%q: %q", source, got)
		}
	}
	for _, source := range []string{"0", "001.20", "-2.3 + 4", `""`, `"a""b"`, `"emoji 🦊 漢字 \\"`, "//emoji 🦊 漢字", "([1, 2]);", "a<=b; a>=b; a<>b;"} {
		if got := admit([]byte(wrapped(source))).reason; got != "" {
			t.Errorf("valid body %q: %q", source, got)
		}
	}
}

func TestInclusiveLexicalLimits(t *testing.T) {
	for name, source := range map[string]string{
		"identifier": wrapped(strings.Repeat("Я", maxIdentifierRunes)),
		"string":     wrapped("\"" + strings.Repeat("x", maxStringCommentBytes-2) + "\""),
		"comment":    wrapped("//" + strings.Repeat("x", maxStringCommentBytes-2)),
		"number":     wrapped(strings.Repeat("9", maxNumberBytes)),
		"tokens":     wrapped(strings.Repeat(";", maxTokens-5)),
		"routines":   routineSource(maxRoutines),
		"parameters": parameterSource(maxParameters),
		"delimiters": wrapped(strings.Repeat("[", maxDelimiterDepth) + strings.Repeat("]", maxDelimiterDepth)),
	} {
		t.Run(name, func(t *testing.T) {
			if got := admit([]byte(source)).reason; got != "" {
				t.Fatal(got)
			}
		})
	}
}

func parameterSource(n int) string {
	params := make([]string, n)
	for i := range params {
		params[i] = fmt.Sprintf("Val Arg%d", i)
	}
	return "Procedure P(" + strings.Join(params, ",") + ")\nEndProcedure"
}
func routineSource(n int) string {
	var out strings.Builder
	for i := 0; i < n; i++ {
		fmt.Fprintf(&out, "Procedure R%d()\nEndProcedure\n", i)
	}
	return out.String()
}

func TestExplicitIdentifierEquality(t *testing.T) {
	for _, pair := range [][2]string{{"ABC_09", "abc_09"}, {"АБВЁ_09", "абвё_09"}} {
		if identEqualKey([]byte(pair[0])) != identEqualKey([]byte(pair[1])) {
			t.Fatal("supported case mapping differs")
		}
	}
	for _, pair := range [][2]string{{"Ё", "Е"}, {"A", "А"}, {"P", "Р"}, {"C", "С"}} {
		if identEqualKey([]byte(pair[0])) == identEqualKey([]byte(pair[1])) {
			t.Fatal("unsupported identifier equality")
		}
	}
}

func TestReservedNamesAndBodyWords(t *testing.T) {
	words := strings.Fields("If Если Then Тогда ElsIf ИначеЕсли Else Иначе EndIf КонецЕсли ElseIf For Для Each Каждого In Из To По While Пока Do Цикл EndDo КонецЦикла Return Возврат Continue Продолжить Break Прервать Var Перем And И Or Или Not Не New Новый Goto Перейти True Истина False Ложь Undefined Неопределено Null Try Попытка Except Исключение EndTry КонецПопытки Raise ВызватьИсключение AddHandler ДобавитьОбработчик RemoveHandler УдалитьОбработчик")
	for _, word := range words {
		for _, source := range []string{"Procedure " + word + "()\nEndProcedure", "Function P(" + word + ")\nEndFunction"} {
			if reason := admit([]byte(source)).reason; reason != "invalid_header" {
				t.Errorf("reserved %s: %s", word, reason)
			}
		}
		if reason := admit([]byte(wrapped(word))).reason; reason != "" {
			t.Errorf("ordinary body %s: %s", word, reason)
		}
	}
	for _, word := range strings.Fields("Execute Выполнить Eval Вычислить Async Асинх Await Ждать") {
		if reason := admit([]byte(wrapped("R." + word + "()"))).reason; reason != "unsupported_keyword" {
			t.Errorf("banned member %s: %s", word, reason)
		}
	}
}
