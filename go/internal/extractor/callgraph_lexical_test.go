package extractor

import (
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"testing"
)

func fmtSite(target, kind string, line, column, endLine, endColumn int) string {
	return fmt.Sprintf("%s|%s|%d:%d-%d:%d", target, kind, line, column, endLine, endColumn)
}

func TestCallGraphIgnoresCommentsAndStrings(t *testing.T) {
	code := `// Procedure Fake()
Procedure Real()
 // Ghost(); If For And
 Text = "Ghost() ""quoted()""
 |Procedure Phantom()
 |If For Or
 |EndProcedure";
 Actual(); // Ignored()
 If(True) Then
 EndIf;
EndProcedure
`
	fs := ExtractCallGraph(code, "M")
	if len(fs) != 1 || fs[0].Name != "Real" {
		t.Fatalf("expected only real declaration, got %#v", fs)
	}
	if !reflect.DeepEqual(fs[0].Calls, []string{"Actual"}) || fs[0].Complexity != 2 {
		t.Fatalf("calls/complexity include non-code: %#v", fs[0])
	}
}

func TestCallGraphDeclarationAndQueryPhysicalLines(t *testing.T) {
	code := "\ufeff\r\n\r\n" + strings.ReplaceAll(`Функция Данные(
 Знач Имя = ") Fake(", // declaration comment
 Знач Еще = """quotes""") Экспорт // trailing comment
 // Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Ложный";
 Запрос.Текст = "ВЫБРАТЬ
 |* ИЗ Справочник.Товары";
 Возврат Локальный();
КонецФункции // trailing comment
`, "\n", "\r\n")
	fs := ExtractCallGraph(code, "M")
	if len(fs) != 1 {
		t.Fatalf("expected one multiline declaration, got %#v", fs)
	}
	f := fs[0]
	if f.Line != 3 || !f.IsExport || !f.IsFunction || !reflect.DeepEqual(f.Calls, []string{"Локальный"}) {
		t.Fatalf("wrong declaration/body: %#v", f)
	}
	if len(f.Queries) != 1 || f.Queries[0].Line != 7 || !reflect.DeepEqual(f.Queries[0].Tables, []string{"Справочник.Товары"}) {
		t.Fatalf("query must come from code assignment at physical line 7: %#v", f.Queries)
	}
	data, _ := json.Marshal(f)
	var obj map[string]any
	_ = json.Unmarshal(data, &obj)
	if obj["end_line"] != float64(10) {
		t.Errorf("end_line: %s", data)
	}
}

func TestCallGraphSitesAndReceiverKinds(t *testing.T) {
	code := "Процедура Тест()\n  Модуль.Пуск(); Пуск();\n  Справочники.Товары.Найти();\n  Получить().Пуск();\n  Массив[0].Пуск();\n  Новый Структура(); New Array();\n  Если(Истина) Тогда\n  КонецЕсли;\nКонецПроцедуры\n"
	fs := ExtractCallGraph(code, "M")
	if len(fs) != 1 {
		t.Fatalf("functions: %#v", fs)
	}
	f := fs[0]
	wantCalls := []string{"Модуль.Пуск", "Получить", "Пуск", "Справочники.Товары.Найти"}
	if !reflect.DeepEqual(f.Calls, wantCalls) {
		t.Errorf("calls = %v, want %v", f.Calls, wantCalls)
	}
	data, _ := json.Marshal(f)
	var obj struct {
		Sites []struct {
			Target    string `json:"target"`
			Line      int    `json:"line"`
			Column    int    `json:"column"`
			EndLine   int    `json:"end_line"`
			EndColumn int    `json:"end_column"`
			Kind      string `json:"kind"`
		} `json:"call_sites"`
	}
	_ = json.Unmarshal(data, &obj)
	want := []string{"Модуль.Пуск|qualified|2:3-2:14", "Пуск|direct|2:18-2:22", "Справочники.Товары.Найти|qualified|3:3-3:27", "Получить|direct|4:3-4:11", "Получить().Пуск|unresolved|4:3-4:18", "Массив[0].Пуск|unresolved|5:3-5:17"}
	var got []string
	for _, s := range obj.Sites {
		got = append(got, fmtSite(s.Target, s.Kind, s.Line, s.Column, s.EndLine, s.EndColumn))
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("sites = %v, want %v", got, want)
	}
}

func TestCallGraphQualifiedDoesNotInventLocalCall(t *testing.T) {
	fs := ExtractCallGraph("Procedure Main()\n Lib.Ping();\n Lib.Ping();\nEndProcedure\nProcedure Ping()\nEndProcedure", "M")
	if len(fs) != 2 || !reflect.DeepEqual(fs[0].Calls, []string{"Lib.Ping"}) || len(fs[0].CallSites) != 2 {
		t.Fatalf("qualified call created local binding or lost repeated evidence: %#v", fs)
	}
}

func TestCallGraphComputedReceiverAfterConstructorAndKeywords(t *testing.T) {
	fs := ExtractCallGraph(`Procedure Main()
 New Array().Count();
 Raise("failure");
 ВызватьИсключение("ошибка");
 Execute("Ghost()");
 Выполнить("Ghost()");
EndProcedure`, "M")
	if len(fs) != 1 {
		t.Fatalf("functions: %#v", fs)
	}
	f := fs[0]
	if len(f.Calls) != 0 || len(f.CallSites) != 1 || f.CallSites[0].Kind != "unresolved" || f.CallSites[0].Target != "Array().Count" {
		t.Fatalf("constructors/statement keywords must not bind as local calls, method remains explicit: %#v", f)
	}
}

func TestCallGraphMultilineCallTargetAndUnicodeColumns(t *testing.T) {
	fs := ExtractCallGraph("\ufeffFunction Main() // declaration\r\n  x = \"😀\"; Модуль // receiver\r\n    .Метод();\r\nEndFunction // end\r\n", "M")
	if len(fs) != 1 || len(fs[0].CallSites) != 1 {
		t.Fatalf("functions: %#v", fs)
	}
	s := fs[0].CallSites[0]
	if s.Target != "Модуль.Метод" || s.Line != 2 || s.Column != 12 || s.EndLine != 3 || s.EndColumn != 11 {
		t.Fatalf("physical Unicode target span: %#v", s)
	}
}

func TestCallGraphDoesNotPresentQueryFragmentAsComplete(t *testing.T) {
	fs := ExtractCallGraph(`Procedure Main()
 Query.Text = "SELECT * FROM Catalog.Partial" + DynamicText;
 Query.Text = "SELECT * FROM Catalog.Real";
EndProcedure`, "M")
	if len(fs) != 1 || len(fs[0].Queries) != 1 || fs[0].Queries[0].Line != 3 {
		t.Fatalf("only complete literal assignment is a known query: %#v", fs)
	}
}
