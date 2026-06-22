from src.telegram.bsl_upload_report import (
    decode_uploaded_text,
    format_bsl_upload_report,
)


def test_format_bsl_upload_report_includes_safe_option_and_test_hint():
    report = format_bsl_upload_report(
        "module.bsl",
        {
            "metrics": {"loc": 12, "procedures": 1, "functions": 0, "max_nesting": 2},
            "diagnostics": [
                {
                    "severity": "high",
                    "line": 7,
                    "code": "join-field-null-guard",
                    "message": "Field from LEFT JOIN is used without an explicit NULL guard.",
                    "details": {
                        "safe_options": ["ЕстьNULL(Скидки.Процент, 0)"],
                        "test_expectations": [
                            "Missing joined row returns the agreed default."
                        ],
                    },
                }
            ],
            "caveats": ["Fallback diagnostics are local and deterministic."],
        },
    )

    assert "Findings: 1 (high 1, medium 0, low 0)" in report
    assert "Safe option: ЕстьNULL(Скидки.Процент, 0)" in report
    assert "Test: Missing joined row returns the agreed default." in report
    assert "Note: Fallback diagnostics are local and deterministic." in report


def test_decode_uploaded_text_accepts_cp1251():
    assert decode_uploaded_text("Процедура Тест()".encode("cp1251")).startswith(
        "Процедура"
    )
