package scanner

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestScanEmptyDir(t *testing.T) {
	dir := t.TempDir()
	result := Scan(dir, 2)
	if result.TotalFiles != 0 {
		t.Errorf("expected 0 files, got %d", result.TotalFiles)
	}
	if result.TotalLOC != 0 {
		t.Errorf("expected 0 LOC, got %d", result.TotalLOC)
	}
}

func TestScanFindsFiles(t *testing.T) {
	dir := t.TempDir()
	// Create test BSL files
	writeFile(t, filepath.Join(dir, "module1.bsl"), `Функция Тест()
    Возврат 1;
КонецФункции`)
	writeFile(t, filepath.Join(dir, "module2.bsl"), `Процедура Действие()
    Сообщить("Привет");
КонецПроцедуры`)
	// Non-BSL file should be ignored
	writeFile(t, filepath.Join(dir, "readme.txt"), "not BSL")

	result := Scan(dir, 2)
	if result.TotalFiles != 2 {
		t.Errorf("expected 2 files, got %d", result.TotalFiles)
	}
}

func TestScanSubdirectories(t *testing.T) {
	dir := t.TempDir()
	sub := filepath.Join(dir, "src", "modules")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatal(err)
	}
	writeFile(t, filepath.Join(dir, "root.bsl"), "// root")
	writeFile(t, filepath.Join(sub, "deep.bsl"), "// deep")

	result := Scan(dir, 2)
	if result.TotalFiles != 2 {
		t.Errorf("expected 2 files, got %d", result.TotalFiles)
	}
}

func TestScanExtensions(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "a.bsl"), "// bsl")
	writeFile(t, filepath.Join(dir, "b.os"), "// os script")
	writeFile(t, filepath.Join(dir, "c.bsp"), "// bsp")
	writeFile(t, filepath.Join(dir, "d.py"), "# python")
	writeFile(t, filepath.Join(dir, "e.go"), "// go")

	result := Scan(dir, 2)
	if result.TotalFiles != 3 {
		t.Errorf("expected 3 BSL files, got %d", result.TotalFiles)
	}
}

func TestScanExtractsFeatures(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "query.bsl"), `Запрос = Новый Запрос("ВЫБРАТЬ * ИЗ Справочник.Номенклатура");`)

	result := Scan(dir, 1)
	if result.TotalFiles != 1 {
		t.Fatalf("expected 1 file, got %d", result.TotalFiles)
	}
	if result.Files[0].Features.HasSelectStar != 1 {
		t.Error("expected SelectStar=1")
	}
	if result.Files[0].Features.HasDBQuery != 1 {
		t.Error("expected DBQuery=1")
	}
}

func TestScanDurationMs(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "test.bsl"), "// test")
	result := Scan(dir, 1)
	if result.DurationMs < 0 {
		t.Error("duration should be non-negative")
	}
}

func TestModuleNameFromPath(t *testing.T) {
	root := filepath.Join("C:", "cfg", "unpacked")
	join := func(rel string) string {
		return filepath.Join(append([]string{root}, strings.Split(rel, "/")...)...)
	}
	tests := []struct {
		name string
		root string
		path string
		want string
	}{
		// Existing kinds — must be preserved.
		{"common module", root, join("CommonModules/МойМодуль/Ext/Module.bsl"), "МойМодуль"},
		{"object module", root, join("Documents/Док/Ext/ObjectModule.bsl"), "Док.ObjectModule"},
		{"manager module", root, join("Documents/Док/Ext/ManagerModule.bsl"), "Док.ManagerModule"},
		{"command module", root, join("Catalogs/Спр/Commands/Кмд/Ext/CommandModule.bsl"), "Спр.CommandModule"},
		// Forms — the fix. All forms of an object collapse to "<Object>.Form".
		{"object form full scan", root, join("Documents/АвансовыйОтчет/Forms/ФормаДокумента/Ext/Form/Module.bsl"), "АвансовыйОтчет.Form"},
		{"catalog form full scan", root, join("Catalogs/Валюты/Forms/ФормаСписка/Ext/Form/Module.bsl"), "Валюты.Form"},
		{"common form", root, join("CommonForms/ОбщаяФорма/Ext/Form/Module.bsl"), "ОбщаяФорма.Form"},
		// Single-object scan: root IS the object dir, form path is relative to it.
		{"object form single-object scan", filepath.Join(root, "Documents", "АвансовыйОтчет"),
			filepath.Join(root, "Documents", "АвансовыйОтчет", "Forms", "ФормаСписка", "Ext", "Form", "Module.bsl"),
			"АвансовыйОтчет.Form"},
		// Single-object scan pointed at one object dir: rel path is just
		// "Ext/ManagerModule.bsl", so parts[1] would be the file name. Must NOT
		// produce the malformed "ManagerModule.bsl.ManagerModule" — derive the
		// object from the root dir's base name instead.
		{"manager module single-object scan", filepath.Join(root, "Documents", "АвансовыйОтчет"),
			filepath.Join(root, "Documents", "АвансовыйОтчет", "Ext", "ManagerModule.bsl"),
			"АвансовыйОтчет.ManagerModule"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := moduleNameFromPath(tt.path, tt.root)
			if got != tt.want {
				t.Errorf("moduleNameFromPath(%q, %q) = %q, want %q", tt.path, tt.root, got, tt.want)
			}
			// A module name must never carry a file extension in it.
			if strings.Contains(strings.ToLower(got), ".bsl") {
				t.Errorf("moduleNameFromPath(%q, %q) = %q contains \".bsl\"", tt.path, tt.root, got)
			}
		})
	}
}

func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}
