package extractor

import (
	"testing"
)

func TestCleanCode(t *testing.T) {
	code := `Функция ПолучитьИмя(Сотрудник)
    Возврат Сотрудник.Наименование;
КонецФункции`
	f := Extract(code)
	if f.HasNPlusOne != 0 {
		t.Error("clean code should not have N+1")
	}
	if f.HasEmptyCatch != 0 {
		t.Error("clean code should not have empty catch")
	}
	if f.HasSelectStar != 0 {
		t.Error("clean code should not have SELECT *")
	}
}

func TestNPlusOne(t *testing.T) {
	code := `Для Каждого Элемент Из Коллекция Цикл
    Запрос = Новый Запрос("ВЫБРАТЬ Ссылка ИЗ Справочник.Номенклатура");
    Результат = Запрос.Выполнить();
КонецЦикла`
	f := Extract(code)
	if f.HasNPlusOne != 1 {
		t.Errorf("expected N+1=1, got %v", f.HasNPlusOne)
	}
}

func TestSelectStar(t *testing.T) {
	code := `Запрос = Новый Запрос("ВЫБРАТЬ * ИЗ Справочник.Номенклатура");`
	f := Extract(code)
	if f.HasSelectStar != 1 {
		t.Errorf("expected SelectStar=1, got %v", f.HasSelectStar)
	}
}

func TestEmptyCatch(t *testing.T) {
	code := `Попытка
    ОпаснаяОперация();
Исключение
КонецПопытки`
	f := Extract(code)
	if f.HasEmptyCatch != 1 {
		t.Errorf("expected EmptyCatch=1, got %v", f.HasEmptyCatch)
	}
}

func TestDeepNesting(t *testing.T) {
	code := `Если А Тогда
    Если Б Тогда
        Если В Тогда
            Если Г Тогда
                Если Д Тогда
                    Действие();
                КонецЕсли;
            КонецЕсли;
        КонецЕсли;
    КонецЕсли;
КонецЕсли;`
	f := Extract(code)
	if f.HasDeepNesting != 1 {
		t.Errorf("expected DeepNesting=1, got %v", f.HasDeepNesting)
	}
	if f.MaxNesting < 5 {
		t.Errorf("expected MaxNesting>=5, got %v", f.MaxNesting)
	}
}

func TestFormHandler(t *testing.T) {
	code := `Процедура ПриОткрытии()
    // код обработчика формы
КонецПроцедуры`
	f := Extract(code)
	if f.HasFormHandler != 1 {
		t.Errorf("expected FormHandler=1, got %v", f.HasFormHandler)
	}
}

func TestDBQuery(t *testing.T) {
	code := `Запрос = Новый Запрос;
Запрос.Текст = "ВЫБРАТЬ Наименование ИЗ Справочник.Контрагенты";`
	f := Extract(code)
	if f.HasDBQuery != 1 {
		t.Errorf("expected DBQuery=1, got %v", f.HasDBQuery)
	}
}

func TestHTTPCall(t *testing.T) {
	code := `HTTPЗапрос = Новый HTTPЗапрос("/api/data");
Соединение = Новый HTTPСоединение("example.com");`
	f := Extract(code)
	if f.HasHTTPCall != 1 {
		t.Errorf("expected HTTPCall=1, got %v", f.HasHTTPCall)
	}
}

func TestComplexity(t *testing.T) {
	code := `Если А Тогда
    Действие1();
ИначеЕсли Б Тогда
    Действие2();
ИначеЕсли В Тогда
    Для Каждого Э Из К Цикл
        Пока Х Цикл
            Действие3();
        КонецЦикла;
    КонецЦикла;
КонецЕсли;`
	f := Extract(code)
	if f.Complexity < 4 {
		t.Errorf("expected complexity>=4, got %v", f.Complexity)
	}
}

func TestDocCoverage(t *testing.T) {
	code := `// Описание функции
// Параметры: нет
Функция МояФункция()
    Возврат 1;
КонецФункции

Функция БезДока()
    Возврат 2;
КонецФункции`
	f := Extract(code)
	if f.DocCoverage <= 0 || f.DocCoverage > 1 {
		t.Errorf("expected DocCoverage in (0,1], got %v", f.DocCoverage)
	}
}

func TestMagicNumbers(t *testing.T) {
	code := `Если Сумма > 150000 Тогда
    Скидка = Сумма * 0.15;
    Бонус = 42;
КонецЕсли;`
	f := Extract(code)
	if f.HasMagicNumbers != 1 {
		t.Errorf("expected MagicNumbers=1, got %v", f.HasMagicNumbers)
	}
}

func TestLOC(t *testing.T) {
	code := "line1\nline2\nline3\n"
	f := Extract(code)
	if f.LOC != 3 {
		t.Errorf("expected LOC=3, got %v", f.LOC)
	}
}

func TestEmptyCode(t *testing.T) {
	f := Extract("")
	if f.LOC != 0 {
		t.Errorf("expected LOC=0, got %v", f.LOC)
	}
	if f.HasNPlusOne != 0 || f.HasSelectStar != 0 || f.HasEmptyCatch != 0 {
		t.Error("empty code should have all zeros")
	}
}
