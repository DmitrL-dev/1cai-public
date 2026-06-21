import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_bsl_standards_review
from src.api.quality_api import router
from src.services.rentgen import standards_review as sr
from src.services.rentgen.standards_review import (
    list_standards_findings,
    review_bsl_standards,
    save_standards_review,
)


UNSAFE_CODE = """
Function UnsafeQuery(Rows) Export
    For Each Row In Rows Do
        Query = New Query("SELECT * FROM Catalog.Products");
        Query.Execute();
    EndDo;
    Execute("Message('x')");
EndFunction
"""

UNSAFE_LEFT_JOIN_CODE = """
Процедура Сформировать()
    Запрос = Новый Запрос(
    "ВЫБРАТЬ
    |   Заказы.Ссылка,
    |   Скидки.Процент КАК ПроцентСкидки
    |ИЗ
    |   Документ.ЗаказПокупателя КАК Заказы
    |   ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.Скидки КАК Скидки
    |   ПО Скидки.Номенклатура = Заказы.Номенклатура");
    Запрос.Выполнить();
КонецПроцедуры
"""

SAFE_LEFT_JOIN_CODE = """
Процедура Сформировать()
    Запрос = Новый Запрос(
    "ВЫБРАТЬ
    |   Заказы.Ссылка,
    |   ЕстьNULL(Скидки.Процент, 0) КАК ПроцентСкидки
    |ИЗ
    |   Документ.ЗаказПокупателя КАК Заказы
    |   ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.Скидки КАК Скидки
    |   ПО Скидки.Номенклатура = Заказы.Номенклатура");
    Запрос.Выполнить();
КонецПроцедуры
"""


MIXED_LEFT_JOIN_CODE = """
Procedure Build()
    Query = New Query(
    "SELECT
    |   ISNULL(Discounts.Percent, 0) AS DiscountPercent, Discounts.Amount AS DiscountAmount
    |FROM
    |   Document.Order AS Orders
    |   LEFT JOIN InfoRegister.Discounts AS Discounts
    |   ON Discounts.Item = Orders.Item");
    Query.Execute();
EndProcedure
"""

JOIN_CONDITION_CONTINUATION_CODE = """
Procedure Build()
    Query = New Query(
    "SELECT
    |   Orders.Ref AS Ref
    |FROM
    |   Document.Order AS Orders
    |   LEFT JOIN InfoRegister.Schedule AS Schedule
    |   ON Orders.Employee = Schedule.Employee
    |       AND Schedule.StartDate <= &SliceDate
    |       AND Schedule.EndDate >= &SliceDate");
    Query.Execute();
EndProcedure
"""

RUSSIAN_MIXED_YESNULL_CODE = """
Процедура Сформировать()
    Запрос = Новый Запрос(
    "ВЫБРАТЬ
    |   ЕстьNULL(СтруктураПредприятия.Ссылка, ЗНАЧЕНИЕ(Справочник.СтруктураПредприятия.ПустаяСсылка)) КАК ЦФО,
    |   СтруктураПредприятия.Код КАК КодЦФО
    |ИЗ
    |   ВТ_Итог КАК ВТ_Итог
    |   ЛЕВОЕ СОЕДИНЕНИЕ Справочник.СтруктураПредприятия КАК СтруктураПредприятия
    |   ПО ВТ_Итог.Подразделение = СтруктураПредприятия.Ссылка");
    Запрос.Выполнить();
КонецПроцедуры
"""

RUSSIAN_CASE_NULL_CHECK_CODE = """
Процедура Сформировать()
    Запрос = Новый Запрос(
    "ВЫБРАТЬ
    |   ВЫБОР
    |       КОГДА НЕ ГрафикиСрез.ГрафикРаботы ЕСТЬ NULL
    |           ТОГДА ГрафикиСрез.ГрафикРаботы
    |       ИНАЧЕ ЗНАЧЕНИЕ(Справочник.ГрафикиРаботыСотрудников.ПустаяСсылка)
    |   КОНЕЦ КАК ГрафикРаботы
    |ИЗ
    |   ВТ_Итог КАК ВТ_Итог
    |   ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.ГрафикРаботыСотрудниковИнтервальный КАК ГрафикиСрез
    |   ПО ВТ_Итог.Сотрудник = ГрафикиСрез.Сотрудник");
    Запрос.Выполнить();
КонецПроцедуры
"""

RUSSIAN_CASE_CHECKS_DIFFERENT_FIELD_CODE = """
Процедура Сформировать()
    Запрос = Новый Запрос(
    "ВЫБРАТЬ
    |   ВЫБОР КОГДА Скидки.Процент ЕСТЬ NULL ТОГДА Скидки.Сумма ИНАЧЕ 0 КОНЕЦ КАК СуммаСкидки
    |ИЗ
    |   Документ.ЗаказПокупателя КАК Заказы
    |   ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.Скидки КАК Скидки
    |   ПО Скидки.Номенклатура = Заказы.Номенклатура");
    Запрос.Выполнить();
КонецПроцедуры
"""

COMMENTED_LEFT_JOIN_CODE = """
Процедура Сформировать()
    Запрос = Новый Запрос(
    "ВЫБРАТЬ
    |   Скидки.Процент КАК ПроцентСкидки
    |ИЗ
    |   Документ.ЗаказПокупателя КАК Заказы
    //|   ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.Скидки КАК Скидки
    //|   ПО Скидки.Номенклатура = Заказы.Номенклатура");
    Запрос.Выполнить();
КонецПроцедуры
"""


class _FakeStore:
    """Minimal Рентген store stub: resolves only whitelisted module paths."""

    def __init__(self, resolving: set[str]):
        self._resolving = resolving

    def resolve_module(self, module_ref: str) -> dict:
        if module_ref in self._resolving:
            return {
                "module_ref": module_ref,
                "canonical": {"source": "module_path"},
                "graph_modules": [{"name": module_ref}],
            }
        return {"module_ref": module_ref, "canonical": {}, "graph_modules": []}


class _NoGraphReviewStore:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 15,
            "has_n_plus_one": False,
            "has_empty_catch": False,
            "reasons": [],
        }

    def module_impact(self, module_path, max_depth=4, max_edges=300):
        return {
            "canonical": {"object_name": "OrderForm", "module_kind": "FormModule", "source": "module_path"},
            "graph_modules": [],
            "entry_subroutines": 0,
            "total": 0,
            "impacted_modules": [],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return []


@pytest.fixture
def graph_with(monkeypatch):
    """Patch the lazy store accessor used by the honesty resolution guard."""

    def _install(resolving):
        store = _FakeStore(set(resolving))
        monkeypatch.setattr(
            "src.api._rentgen_store.store_or_none", lambda: store, raising=True
        )
        return store

    return _install


REAL_MODULE = "CommonModules/ОбщегоНазначения/Ext/Module.bsl"
FAKE_MODULE = "CommonModules/Sales/Ext/Module.bsl"


def test_review_maps_diagnostics_to_catalog_and_autofix():
    # Diagnostics themselves are real and deterministic regardless of the graph.
    report = review_bsl_standards(UNSAFE_CODE, module_path=REAL_MODULE)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert {"select-star", "query-in-loop", "dynamic-execute", "undocumented-export"} <= rule_ids
    assert report["summary"]["findings"] >= 4
    assert report["summary"]["autofixable"] >= 2
    assert report["findings"][0]["standard"].startswith("1c:")
    assert "BSL Standards Review" in report["markdown"]
    assert "resolution" in report


def test_left_join_fields_without_null_guard_are_flagged():
    report = review_bsl_standards(UNSAFE_LEFT_JOIN_CODE)
    findings = [item for item in report["findings"] if item["rule_id"] == "join-field-null-guard"]

    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["standard"] == "1c:query-left-join-null-safety"
    assert findings[0]["details"]["alias"] == "Скидки"
    assert "ЕстьNULL" in findings[0]["autofix"]["description"]


def test_left_join_fields_with_yesnull_guard_are_not_flagged():
    report = review_bsl_standards(SAFE_LEFT_JOIN_CODE)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert "join-field-null-guard" not in rule_ids


def test_review_diff_marks_missing_graph_as_unmeasured(monkeypatch):
    monkeypatch.setattr("src.api.quality_api.store_or_none", lambda: _NoGraphReviewStore())

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/quality/review-diff",
        json={"changed_modules": ["Documents/Order/Forms/Main/Ext/Form/Module.bsl"]},
    )

    assert response.status_code == 200
    payload = response.json()
    item = payload["modules"][0]
    assert item["impact_total"] == 0
    assert item["impact_measured"] is False
    assert item["coverage"] == "no_graph_data"
    assert "no graph data" in payload["caveats"][-1]


def test_left_join_mixed_guard_line_still_flags_unguarded_field():
    report = review_bsl_standards(MIXED_LEFT_JOIN_CODE)
    findings = [item for item in report["findings"] if item["rule_id"] == "join-field-null-guard"]

    assert len(findings) == 1
    assert findings[0]["details"]["alias"] == "Discounts"
    assert findings[0]["details"]["field"] == "Amount"


def test_left_join_condition_continuation_is_not_reported_as_field_usage():
    report = review_bsl_standards(JOIN_CONDITION_CONTINUATION_CODE)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert "join-field-null-guard" not in rule_ids


def test_russian_mixed_yesnull_line_flags_only_unguarded_neighbor():
    report = review_bsl_standards(RUSSIAN_MIXED_YESNULL_CODE)
    findings = [item for item in report["findings"] if item["rule_id"] == "join-field-null-guard"]

    assert len(findings) == 1
    assert findings[0]["details"]["alias"] == "СтруктураПредприятия"
    assert findings[0]["details"]["field"] == "Код"
    assert findings[0]["details"]["safe_options"][0].startswith("ЕстьNULL(")
    assert "Р•" not in findings[0]["message"]
    assert all("Р•" not in option for option in findings[0]["details"]["safe_options"])
    assert findings[0]["details"]["test_expectations"]


def test_multiline_case_with_explicit_not_null_check_is_safe():
    report = review_bsl_standards(RUSSIAN_CASE_NULL_CHECK_CODE)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert "join-field-null-guard" not in rule_ids


def test_case_null_check_for_one_join_field_does_not_hide_another_field():
    report = review_bsl_standards(RUSSIAN_CASE_CHECKS_DIFFERENT_FIELD_CODE)
    findings = [item for item in report["findings"] if item["rule_id"] == "join-field-null-guard"]

    assert len(findings) == 1
    assert findings[0]["details"]["field_ref"] == "Скидки.Сумма"


def test_commented_left_join_does_not_create_alias_finding():
    report = review_bsl_standards(COMMENTED_LEFT_JOIN_CODE)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert "join-field-null-guard" not in rule_ids


def test_resolving_module_is_persisted(graph_with, tmp_path):
    graph_with({REAL_MODULE})
    path = tmp_path / "standards_findings.json"

    report = review_bsl_standards(UNSAFE_CODE, module_path=REAL_MODULE)
    assert report["resolution"]["resolved"] is True

    stored = save_standards_review(report, path=path)
    listing = list_standards_findings(path=path)

    assert stored["persisted"] is True
    assert stored["module_path"] == REAL_MODULE
    assert listing["total"] == 1


def test_unresolved_module_is_not_persisted(graph_with, tmp_path):
    # HONESTY: a module that does not exist in the Рентген graph (graph_modules=0)
    # must never be stored/served as real configuration analysis.
    graph_with({REAL_MODULE})  # FAKE_MODULE intentionally absent
    path = tmp_path / "standards_findings.json"

    report = review_bsl_standards(UNSAFE_CODE, module_path=FAKE_MODULE)
    assert report["resolution"]["resolved"] is False
    assert report["resolution"]["graph_modules"] == 0

    stored = save_standards_review(report, path=path)
    listing = list_standards_findings(path=path)

    assert stored["persisted"] is False
    assert stored["status"] == "not_available"
    assert stored["reason"] == "module_not_in_graph"
    # Nothing fabricated was written to the store.
    assert listing["total"] == 0
    assert not path.exists()


def test_findings_store_empty_without_seed(tmp_path):
    # The fabricated seed is gone: an untouched store yields zero findings.
    listing = list_standards_findings(path=tmp_path / "nope.json")
    assert listing["total"] == 0
    assert listing["items"] == []


def test_standards_review_api_skips_unresolved_module(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "STORE_PATH", tmp_path / "standards_findings.json")
    monkeypatch.setattr(
        "src.api._rentgen_store.store_or_none",
        lambda: _FakeStore({REAL_MODULE}),
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/quality/standards-review",
        json={"code": UNSAFE_CODE, "module_path": FAKE_MODULE, "save": True},
    )
    listing = client.get("/quality/standards-findings").json()

    assert response.status_code == 200
    body = response.json()
    # Diagnostics are still returned for the pasted code...
    assert body["summary"]["findings"] >= 4
    # ...but the unresolved module is NOT persisted as configuration analysis.
    assert body["stored"]["persisted"] is False
    assert listing["total"] == 0


def test_standards_review_api_persists_resolving_module(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "STORE_PATH", tmp_path / "standards_findings.json")
    monkeypatch.setattr(
        "src.api._rentgen_store.store_or_none",
        lambda: _FakeStore({REAL_MODULE}),
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/quality/standards-review",
        json={"code": UNSAFE_CODE, "module_path": REAL_MODULE, "save": True},
    )
    listing = client.get("/quality/standards-findings").json()

    assert response.status_code == 200
    assert response.json()["stored"]["persisted"] is True
    assert listing["total"] == 1
    assert listing["items"][0]["summary"]["autofixable"] >= 2


@pytest.mark.asyncio
async def test_mcp_bsl_standards_review_tool_is_registered(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, "STORE_PATH", tmp_path / "standards_findings.json")
    monkeypatch.setattr(
        "src.api._rentgen_store.store_or_none",
        lambda: _FakeStore({REAL_MODULE}),
    )

    result = await handle_bsl_standards_review(
        {"code": UNSAFE_CODE, "module_path": REAL_MODULE, "save": True}
    )

    assert "bsl_standards_review" in {tool.name for tool in TOOLS}
    assert result["summary"]["findings"] >= 4
    assert result["stored"]["persisted"] is True
    assert result["stored"]["module_path"] == REAL_MODULE
