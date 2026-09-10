package extractor

import (
	"testing"
)

func TestExtractCallGraphBasic(t *testing.T) {
	code := "Процедура МояПроцедура(Парам1) Экспорт\r\n\tСтрока = ОбщийМодуль.Метод();\r\n\tЛокальный();\r\nКонецПроцедуры\r\n"
	funcs := ExtractCallGraph(code, "TestModule")
	if len(funcs) == 0 {
		t.Fatalf("Expected at least 1 function, got 0")
	}
	f := funcs[0]
	t.Logf("Found: name=%s module=%s export=%v isFunc=%v calls=%v", f.Name, f.Module, f.IsExport, f.IsFunction, f.Calls)
	if f.Name != "МояПроцедура" {
		t.Errorf("Expected name 'МояПроцедура', got %q", f.Name)
	}
	if !f.IsExport {
		t.Error("Expected IsExport=true")
	}
	if f.IsFunction {
		t.Error("Expected IsFunction=false (procedure)")
	}
}

func TestExtractCallGraphFunction(t *testing.T) {
	code := "Функция ПолучитьДанные(Ключ)\r\n\tВозврат Справочники.Товары.НайтиПоНаименованию(Ключ);\r\nКонецФункции\r\n"
	funcs := ExtractCallGraph(code, "TestModule")
	if len(funcs) == 0 {
		t.Fatalf("Expected at least 1 function, got 0")
	}
	f := funcs[0]
	t.Logf("Found: name=%s isFunc=%v calls=%v", f.Name, f.IsFunction, f.Calls)
	if f.Name != "ПолучитьДанные" {
		t.Errorf("Expected name 'ПолучитьДанные', got %q", f.Name)
	}
	if !f.IsFunction {
		t.Error("Expected IsFunction=true")
	}
}

func TestExtractCallGraphMultiple(t *testing.T) {
	code := `Процедура Первая()
	Вторая();
КонецПроцедуры

Функция Вторая() Экспорт
	Возврат 42;
КонецФункции
`
	funcs := ExtractCallGraph(code, "TestModule")
	if len(funcs) != 2 {
		t.Fatalf("Expected 2 functions, got %d", len(funcs))
	}
	t.Logf("Found %d functions", len(funcs))
	for _, f := range funcs {
		t.Logf("  %s (func=%v export=%v calls=%v)", f.Name, f.IsFunction, f.IsExport, f.Calls)
	}
}
