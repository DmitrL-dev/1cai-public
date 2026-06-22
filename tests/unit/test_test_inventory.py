from src.services.rentgen.test_inventory import (
    build_test_inventory,
    match_tests_for_module,
)


def test_test_inventory_matches_changed_module_to_bsl_test(tmp_path):
    test_root = tmp_path / "tests" / "bsl"
    test_root.mkdir(parents=True)
    (test_root / "test_orders.bsl").write_text(
        """
// Формат: YAxUnit
Процедура Тест_ЗаказКлиента_Проведение() Экспорт
    ЮТест.ПроверитьИстину(Истина);
КонецПроцедуры
""",
        encoding="utf-8",
    )

    build_test_inventory.cache_clear()
    inventory = build_test_inventory(str(tmp_path))
    matches = match_tests_for_module(
        "Documents/ЗаказКлиента/Ext/ObjectModule.bsl",
        object_name="ЗаказКлиента",
        root=str(tmp_path),
    )

    assert inventory["summary"]["test_cases"] == 1
    assert matches
    assert matches[0]["framework"] == "YAxUnit"
    assert matches[0]["selector"] == "Тест_ЗаказКлиента_Проведение"
    assert "заказклиента" in matches[0]["matched_terms"]
