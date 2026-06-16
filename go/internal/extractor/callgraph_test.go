package extractor

import (
	"fmt"
	"os"
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

func TestRegexMatches(t *testing.T) {
	// Test the raw regex against various BSL declarations
	tests := []struct {
		line    string
		matches bool
	}{
		{"Процедура Тест(Парам1) Экспорт", true},
		{"Функция Тест(Парам1)", true},
		{"Procedure Test(Param1) Export", true},
		{"Function Test(Param1)", true},
		{"\tПроцедура Тест()", true},
		{"  Функция Тест(А, Б, В) Экспорт", true},
	}
	for _, tt := range tests {
		m := reCGFuncStart.MatchString(tt.line)
		if m != tt.matches {
			t.Errorf("Line %q: expected match=%v, got %v", tt.line, tt.matches, m)
		} else {
			subs := reCGFuncStart.FindStringSubmatch(tt.line)
			if subs != nil {
				t.Logf("Line %q → name=%q export=%q", tt.line, subs[1], subs[2])
			}
		}
	}
}

func TestExtractCallGraphRealFile(t *testing.T) {
	// Try reading a real BSL file if it exists
	path := `C:\1cAI\data\configs\unpacked\CommonModules\CRMЛокализация\Ext\Module.bsl`
	data, err := os.ReadFile(path)
	if err != nil {
		t.Skipf("Real file not available: %v", err)
	}

	code := string(data)
	// Show first 200 chars for debugging
	preview := code
	if len(preview) > 200 {
		preview = preview[:200]
	}
	t.Logf("File size: %d bytes, preview: %q", len(data), preview)

	// Show hex of first 20 bytes
	hex := ""
	for i := 0; i < 20 && i < len(data); i++ {
		hex += fmt.Sprintf("%02x ", data[i])
	}
	t.Logf("First 20 bytes hex: %s", hex)

	funcs := ExtractCallGraph(code, "CRMЛокализация")
	t.Logf("Extracted %d functions from real file", len(funcs))
	for i, f := range funcs {
		if i >= 5 {
			t.Logf("  ... and %d more", len(funcs)-5)
			break
		}
		t.Logf("  %s (func=%v export=%v complexity=%d calls=%d)",
			f.Name, f.IsFunction, f.IsExport, f.Complexity, len(f.Calls))
	}
}
