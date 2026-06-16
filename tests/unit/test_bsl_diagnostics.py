from src.services.bsl_diagnostics import analyze_bsl


def test_bsl_diagnostics_flags_enterprise_review_risks():
    code = """
Процедура ПровестиДокумент() Экспорт
    Для Каждого Строка Из Таблица Цикл
        Запрос = Новый Запрос("ВЫБРАТЬ * ИЗ Справочник.Номенклатура");
        Запрос.Выполнить();
    КонецЦикла;

    Попытка
    Исключение
    КонецПопытки;

    УстановитьПривилегированныйРежим(Истина);
    Выполнить("Сообщить(1)");
КонецПроцедуры
"""

    result = analyze_bsl(code, module_path="Documents/Заказ/Ext/ObjectModule.bsl")
    codes = {diagnostic["code"] for diagnostic in result["diagnostics"]}

    assert result["engine"] == "fallback"
    assert result["metrics"]["procedures"] == 1
    assert result["metrics"]["metadata_refs"] == 1
    assert {
        "empty-catch",
        "query-in-loop",
        "select-star",
        "privileged-mode",
        "dynamic-execute",
        "undocumented-export",
    } <= codes
