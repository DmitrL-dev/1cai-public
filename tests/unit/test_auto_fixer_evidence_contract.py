from src.ai.agents.code_review.auto_fixer import AUTO_FIXER_CONTRACT, AutoFixer


def test_auto_fixer_parameterizes_dynamic_query_concat():
    fixer = AutoFixer()
    code = """
Функция ПолучитьДанные(ID)
    Запрос.Текст = "SELECT * WHERE ID = '" + ID + "'";
    Возврат Запрос.Выполнить();
КонецФункции
"""

    result = fixer.auto_fix_all(
        code,
        [{"rule_id": "bsl-dynamic-query-concat", "issue": "SQL injection"}],
    )

    assert result["mode"] == AUTO_FIXER_CONTRACT
    assert result["applied_fixes"]
    assert 'Запрос.Текст = "SELECT * WHERE ID = &ID";' in result["fixed_code"]
    assert 'Запрос.УстановитьПараметр("ID", ID);' in result["fixed_code"]
    assert '"+ ID +"' not in result["fixed_code"].replace(" ", "")
