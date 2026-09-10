package scanner

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestCallGraphSourcePathAndWorkerDeterminism(t *testing.T) {
	root := t.TempDir()
	paths := []string{
		"Documents/Док/Forms/А/Ext/Form/Module.bsl",
		"Documents/Док/Forms/Б/Ext/Form/Module.bsl",
		"CommonModules/Общий/Ext/Module.bsl",
	}
	for _, rel := range paths {
		path := filepath.Join(root, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			t.Fatal(err)
		}
		writeFile(t, path, "\ufeffProcedure Run()\r\n  Call();\r\nEndProcedure\r\n\r\nProcedure Next()\r\nEndProcedure\r\n")
	}
	one := ScanCallGraph(root, 1)
	if one.TotalFiles != 3 || one.TotalFuncs != 6 || one.Errors != 0 {
		t.Fatalf("scan summary: %#v", one)
	}
	seen := map[string]int{}
	last := ""
	for _, f := range one.Functions {
		seen[f.SourcePath]++
		if f.SourcePath < last {
			t.Errorf("source order: %q after %q", f.SourcePath, last)
		}
		last = f.SourcePath
		if f.SourcePath == paths[0] || f.SourcePath == paths[1] {
			if f.Module != "Док.Form" {
				t.Errorf("module alias changed: %q", f.Module)
			}
		}
		if f.Name == "Run" && (f.Line != 1 || f.EndLine != 3 || len(f.CallSites) != 1 || f.CallSites[0].Line != 2) {
			t.Errorf("lost spans: %#v", f)
		}
	}
	for _, rel := range paths {
		if seen[rel] != 2 {
			t.Errorf("source_path %q count %d", rel, seen[rel])
		}
	}
	for _, workers := range []int{2, 4, 8} {
		many := ScanCallGraph(root, workers)
		if !reflect.DeepEqual(one.Functions, many.Functions) {
			t.Errorf("worker %d changes ordered functions", workers)
		}
		a, _ := json.Marshal(one.Functions)
		b, _ := json.Marshal(many.Functions)
		if string(a) != string(b) {
			t.Errorf("worker %d changes JSON", workers)
		}
	}
}
