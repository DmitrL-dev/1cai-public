"""Tests for OneCCodeGraphBuilder (Рентген core)."""

import json
from pathlib import Path

import pytest

from src.ai.code_graph_1c_builder import (
    BslFunction,
    EventSubscription,
    OneCCodeGraphBuilder,
)

# === BSL Code Fixtures ===

SIMPLE_MODULE = """
Процедура ПередЗаписью(Отказ)
    ПроверитьДанные();
    Если НЕ ДанныеКорректны() Тогда
        Отказ = Истина;
    КонецЕсли;
КонецПроцедуры

Функция ДанныеКорректны() Экспорт
    Возврат Истина;
КонецФункции

Процедура ОбработкаПроведения(Отказ, РежимПроведения)
    Движения.РегистрНакопления.Записать();
    ОбщегоНазначения.ПроверитьПраваДоступа();
КонецПроцедуры
"""

QUERY_MODULE = """
Функция ПолучитьДанные()
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ Наименование, Цена ИЗ Справочник.Номенклатура ГДЕ НЕ ПометкаУдаления";
    Возврат Запрос.Выполнить().Выгрузить();
КонецФункции
"""

N_PLUS_ONE_MODULE = """
Процедура ОбработатьТаблицу(Таблица)
    Для Каждого Стр Из Таблица Цикл
        Запрос = Новый Запрос;
        Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура ГДЕ Ссылка = &Ссылка";
        Запрос.УстановитьПараметр("Ссылка", Стр.Номенклатура);
        Результат = Запрос.Выполнить();
    КонецЦикла;
КонецПроцедуры
"""


@pytest.fixture
def builder(tmp_path):
    """Create builder with temp config directory."""
    return OneCCodeGraphBuilder(config_path=str(tmp_path))


@pytest.fixture
def populated_builder(tmp_path):
    """Builder with BSL files in temp directory."""
    # Create module structure
    doc_dir = tmp_path / "Documents" / "ПоступлениеТоваров" / "Ext"
    doc_dir.mkdir(parents=True)
    (doc_dir / "ObjectModule.bsl").write_text(SIMPLE_MODULE, encoding="utf-8")

    cm_dir = tmp_path / "CommonModules" / "ОбщегоНазначения" / "Ext"
    cm_dir.mkdir(parents=True)
    (cm_dir / "Module.bsl").write_text(QUERY_MODULE, encoding="utf-8")

    builder = OneCCodeGraphBuilder(config_path=str(tmp_path))
    return builder


class TestBslParsing:
    """Test BSL module parsing."""

    def test_parse_functions_and_procedures(self, builder, tmp_path):
        mod_dir = tmp_path / "CommonModules" / "Тест" / "Ext"
        mod_dir.mkdir(parents=True)
        (mod_dir / "Module.bsl").write_text(SIMPLE_MODULE, encoding="utf-8")

        functions = builder.parse_bsl_modules()

        names = [f.name for f in functions]
        assert "ПередЗаписью" in names
        assert "ДанныеКорректны" in names
        assert "ОбработкаПроведения" in names

    def test_function_vs_procedure(self, builder, tmp_path):
        mod_dir = tmp_path / "CommonModules" / "Тест" / "Ext"
        mod_dir.mkdir(parents=True)
        (mod_dir / "Module.bsl").write_text(SIMPLE_MODULE, encoding="utf-8")

        functions = builder.parse_bsl_modules()
        by_name = {f.name: f for f in functions}

        assert by_name["ДанныеКорректны"].is_function is True
        assert by_name["ПередЗаписью"].is_function is False

    def test_export_detection(self, builder, tmp_path):
        mod_dir = tmp_path / "CommonModules" / "Тест" / "Ext"
        mod_dir.mkdir(parents=True)
        (mod_dir / "Module.bsl").write_text(SIMPLE_MODULE, encoding="utf-8")

        functions = builder.parse_bsl_modules()
        by_name = {f.name: f for f in functions}

        assert by_name["ДанныеКорректны"].is_export is True
        assert by_name["ПередЗаписью"].is_export is False

    def test_call_extraction(self, builder, tmp_path):
        mod_dir = tmp_path / "CommonModules" / "Тест" / "Ext"
        mod_dir.mkdir(parents=True)
        (mod_dir / "Module.bsl").write_text(SIMPLE_MODULE, encoding="utf-8")

        functions = builder.parse_bsl_modules()
        by_name = {f.name: f for f in functions}

        calls = by_name["ПередЗаписью"].calls
        assert "ПроверитьДанные" in calls
        assert "ДанныеКорректны" in calls

    def test_cross_module_call(self, builder, tmp_path):
        mod_dir = tmp_path / "CommonModules" / "Тест" / "Ext"
        mod_dir.mkdir(parents=True)
        (mod_dir / "Module.bsl").write_text(SIMPLE_MODULE, encoding="utf-8")

        functions = builder.parse_bsl_modules()
        by_name = {f.name: f for f in functions}

        calls = by_name["ОбработкаПроведения"].calls
        assert "ОбщегоНазначения.ПроверитьПраваДоступа" in calls

    def test_query_extraction(self, builder, tmp_path):
        mod_dir = tmp_path / "CommonModules" / "Тест" / "Ext"
        mod_dir.mkdir(parents=True)
        (mod_dir / "Module.bsl").write_text(QUERY_MODULE, encoding="utf-8")

        functions = builder.parse_bsl_modules()
        func = [f for f in functions if f.name == "ПолучитьДанные"][0]

        assert len(func.queries) >= 1
        assert "Номенклатура" in func.queries[0]["text"]

    def test_complexity_estimation(self, builder, tmp_path):
        mod_dir = tmp_path / "CommonModules" / "Тест" / "Ext"
        mod_dir.mkdir(parents=True)
        (mod_dir / "Module.bsl").write_text(SIMPLE_MODULE, encoding="utf-8")

        functions = builder.parse_bsl_modules()
        by_name = {f.name: f for f in functions}

        # ПередЗаписью has Если + НЕ = complexity > 1
        assert by_name["ПередЗаписью"].complexity > 1
        # ДанныеКорректны is trivial
        assert by_name["ДанныеКорректны"].complexity == 1


class TestMetadataParsing:
    """Test 1C metadata XML parsing."""

    def test_parse_documents(self, populated_builder):
        meta = populated_builder.parse_metadata()
        assert "ПоступлениеТоваров" in meta.documents

    def test_parse_common_modules(self, populated_builder):
        meta = populated_builder.parse_metadata()
        names = [m["name"] for m in meta.common_modules]
        assert "ОбщегоНазначения" in names

    def test_parse_subscriptions(self, builder, tmp_path):
        sub_dir = tmp_path / "EventSubscriptions"
        sub_dir.mkdir()
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <EventSubscription>
            <Name>ПроверкаДокументов</Name>
            <Source><Type>DocumentObject.*</Type></Source>
            <Event>ПередЗаписью</Event>
            <Handler>
                <CommonModule>МодульПроверок</CommonModule>
                <Method>ПередЗаписьюДокумента</Method>
            </Handler>
        </EventSubscription>"""
        (sub_dir / "ПроверкаДокументов.xml").write_text(xml, encoding="utf-8")

        meta = builder.parse_metadata()
        assert len(meta.subscriptions) == 1
        sub = meta.subscriptions[0]
        assert sub.event == "ПередЗаписью"
        assert sub.handler_module == "МодульПроверок"
        assert sub.handler_method == "ПередЗаписьюДокумента"


class TestFullPipeline:
    """Test parse_all + JSON export."""

    def test_parse_all(self, populated_builder):
        populated_builder.parse_all()
        assert len(populated_builder.functions) > 0
        assert len(populated_builder.metadata.documents) > 0

    def test_get_all_calls(self, populated_builder):
        populated_builder.parse_all()
        calls = populated_builder.get_all_calls()
        assert isinstance(calls, list)

    def test_to_json(self, populated_builder):
        populated_builder.parse_all()
        j = populated_builder.to_json()
        data = json.loads(j)
        assert "metadata" in data
        assert "functions" in data
