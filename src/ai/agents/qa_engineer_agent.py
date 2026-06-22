"""
QA Engineer AI Agent
AI ассистент для тестировщиков
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class QAEngineerAgent:
    """AI агент для QA инженеров"""

    def __init__(self):
        self.agent_name = "local-qa-engineer"

    def _extract_bsl_routines(self, code: str) -> List[str]:
        return [
            match.group(2)
            for match in re.finditer(
                r"\b(Функция|Процедура)\s+([A-Za-zА-Яа-я_][\wА-Яа-я]*)",
                code,
                re.IGNORECASE,
            )
        ]

    async def generate_vanessa_tests(
        self, module_name: str, functions: List[str]
    ) -> str:
        """
        Генерирует Vanessa BDD тесты

        Args:
            module_name: Название модуля
            functions: Список функций для тестирования

        Returns:
            .feature файл с BDD сценариями
        """
        feature_file = f"""# language: ru

Функционал: Тестирование модуля {module_name}
    Как QA инженер
    Я хочу протестировать все функции модуля {module_name}
    Чтобы убедиться в их корректной работе

Контекст:
    Дано Я запускаю сценарий открытия TestClient или TestManager
    И Я закрываю все окна клиентского приложения

"""

        for func in functions:
            feature_file += f"""
Сценарий: Тестирование функции {func}
    Когда Я вызываю функцию "{func}"
    Тогда функция выполнена без ошибок
    И результат соответствует ожидаемому значению

"""

        feature_file += """
Сценарий: Smoke test модуля
    Дано я создаю тестовые данные
    Когда я выполняю основные операции
    Тогда все операции завершены успешно
    И в логе нет ошибок
"""

        return feature_file

    async def generate_smoke_tests(self, configuration: str) -> List[Dict[str, str]]:
        """
        Генерирует smoke-тесты для конфигурации

        Args:
            configuration: Название конфигурации

        Returns:
            Список smoke-тестов
        """
        target = configuration or "переданная конфигурация"
        return [
            {
                "name": f"Smoke: запуск {target}",
                "steps": [
                    "Запустить 1С",
                    f"Открыть {target}",
                    "Проверить отсутствие ошибок в логе",
                ],
                "expected": "Старт проходит без критических ошибок",
                "coverage": "generic_smoke_shell",
                "caveat": "Критичные бизнес-сценарии не переданы, поэтому smoke-тест не делает вид, что покрывает домен.",
            },
            {
                "name": f"Smoke: открытие основных разделов {target}",
                "steps": [
                    "Открыть главную форму",
                    "Последовательно открыть доступные подсистемы",
                    "Зафиксировать ошибки открытия форм и прав доступа",
                ],
                "expected": "Доступные разделы открываются без исключений",
                "coverage": "generic_smoke_shell",
                "caveat": "Список подсистем должен быть уточнен из EDT/XML метаданных.",
            },
            {
                "name": f"Smoke: журнал ошибок {target}",
                "steps": [
                    "Выполнить короткий пользовательский проход",
                    "Собрать технологический журнал и журнал регистрации",
                    "Проверить критические исключения, блокировки и таймауты",
                ],
                "expected": "Критические ошибки отсутствуют либо приложены как evidence",
                "coverage": "generic_smoke_shell",
                "caveat": "Без tech journal результат нельзя считать доказанным.",
            },
        ]

    async def analyze_test_coverage(self, module_code: str) -> Dict[str, Any]:
        """
        Анализирует покрытие кода тестами

        Args:
            module_code: Код модуля BSL

        Returns:
            Анализ покрытия
        """
        lines = module_code.split("\n")
        total_lines = len(
            [l for l in lines if l.strip() and not l.strip().startswith("//")]
        )
        routines = self._extract_bsl_routines(module_code)
        recommendations = [
            f"Добавить unit/BDD тест для {routine}" for routine in routines
        ] or ["Передать код функций и существующие тесты для расчета покрытия."]

        return {
            "agent": self.agent_name,
            "mode": "offline_static_coverage_triage",
            "coverage_measured": False,
            "coverage": "unknown_no_test_evidence",
            "total_lines": total_lines,
            "covered_lines": 0,
            "coverage_percent": 0.0,
            "coverage_caveat": (
                "Покрытие не измерено: передан код модуля без карты выполненных "
                "тестов, поэтому 0% не является доказательством отсутствия покрытия."
            ),
            "uncovered_functions": routines,
            "recommendations": recommendations,
            "complexity_analysis": {
                "high_complexity_functions": [],
                "caveat": "Cyclomatic complexity не считается без BSL parser AST.",
            },
        }

    async def generate_test_data(
        self, entity_type: str, count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Генерирует тестовые данные

        Args:
            entity_type: Тип сущности (Клиент, Товар и т.д.)
            count: Количество записей

        Returns:
            Список тестовых данных
        """
        if entity_type == "Клиент":
            return [
                {
                    "Наименование": f"ООО Тестовая компания {i}",
                    "ИНН": f"{7700000000 + i}",
                    "КПП": "770001001",
                    "Телефон": f"+7 (495) {i:03d}-{i:02d}-{i:02d}",
                    "Email": f"test{i}@example.com",
                }
                for i in range(1, count + 1)
            ]
        elif entity_type == "Товар":
            return [
                {
                    "Наименование": f"Тестовый товар {i}",
                    "Артикул": f"TEST-{i:04d}",
                    "Цена": 1000.00 * i,
                    "Количество": 100 - i,
                }
                for i in range(1, count + 1)
            ]
        else:
            return []

    async def analyze_bug(
        self, bug_description: str, stacktrace: str = ""
    ) -> Dict[str, Any]:
        """
        Анализирует баг и предлагает решение

        Args:
            bug_description: Описание бага
            stacktrace: Stack trace (если есть)

        Returns:
            Анализ и рекомендации
        """
        evidence = "\n".join(part for part in [bug_description, stacktrace] if part)
        affected_modules = sorted(
            set(
                re.findall(
                    r"(?:ОбщийМодуль|Документ|Справочник)\.[A-Za-zА-Яа-я0-9_]+",
                    evidence,
                )
            )
        )
        lower = evidence.lower()
        severity = "unknown"
        if any(
            marker in lower
            for marker in ("critical", "критич", "падение", "исключение")
        ):
            severity = "high"
        elif any(marker in lower for marker in ("warning", "предупреж", "медлен")):
            severity = "medium"
        return {
            "agent": self.agent_name,
            "mode": "offline_bug_triage",
            "coverage": "source_bug_text" if evidence.strip() else "no_bug_evidence",
            "severity": severity,
            "category": "runtime_or_quality_signal" if evidence.strip() else "unknown",
            "root_cause": "not_determined_from_evidence",
            "affected_modules": affected_modules,
            "recommended_fix": [
                "Приложить минимальные шаги воспроизведения.",
                "Привязать stacktrace/tech journal к модулю и строке кода.",
                "Добавить regression test до исправления.",
            ],
            "regression_tests": [
                "Проверить воспроизведение по исходным шагам.",
                "Проверить негативный сценарий из stacktrace.",
                "Проверить отсутствие новой ошибки в журнале после исправления.",
            ],
            "related_bugs": [],
            "caveats": [
                "Причина не выводится без кода, данных и воспроизводимого журнала."
            ],
        }

    async def generate_tests(
        self, function_code: str, function_name: str
    ) -> Dict[str, Any]:
        """Контракт, ожидаемый RoleBasedRouter для генерации тестов."""
        routines = self._extract_bsl_routines(function_code) or [function_name]
        yaxunit = await self.generate_yaxunit_tests(function_name, routines)
        return {
            "agent": self.agent_name,
            "mode": "offline_test_blueprint",
            "coverage": "source_code" if function_code.strip() else "no_source_code",
            "tests": {
                "framework": "YAxUnit",
                "module": function_name,
                "routines": routines,
                "source": yaxunit,
            },
            "test_cases": [
                {
                    "name": f"Тест_{routine}",
                    "target": routine,
                    "status": "blueprint_requires_expected_values",
                }
                for routine in routines
            ],
            "caveats": [
                "Ожидаемые значения и fixture-данные должны быть подтверждены владельцем домена."
            ],
        }

    async def analyze_coverage(self, config_name: str) -> Dict[str, Any]:
        """Контракт, ожидаемый RoleBasedRouter для анализа покрытия."""
        return {
            "agent": self.agent_name,
            "mode": "offline_coverage_inventory_request",
            "coverage": "no_test_run_evidence",
            "configuration": config_name,
            "coverage_measured": False,
            "coverage_percent": 0.0,
            "coverage_caveat": (
                "Покрытие конфигурации нельзя измерить по имени конфигурации; "
                "нужны результаты YAxUnit/Vanessa или карта тестов."
            ),
            "required_evidence": ["test_run_report", "changed_modules", "test_mapping"],
        }

    async def analyze_bugs(self, bug_history: List[Any]) -> Dict[str, Any]:
        """Агрегирует историю дефектов без выдуманных hotspot-ов."""
        normalized = [str(item) for item in bug_history if str(item).strip()]
        return {
            "agent": self.agent_name,
            "mode": "offline_bug_history_triage",
            "coverage": "bug_history" if normalized else "no_bug_history",
            "total_bugs": len(normalized),
            "patterns": [],
            "recommendations": [
                "Передать defect id, модуль, stacktrace и дату для поиска повторяемых зон."
            ],
            "caveats": ["Паттерны дефектов не строятся без структурированной истории."],
        }

    async def generate_performance_test(
        self, endpoints: List[Any], load_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Создает безопасный blueprint нагрузочного теста."""
        return {
            "agent": self.agent_name,
            "mode": "offline_performance_test_blueprint",
            "coverage": "endpoints_and_profile"
            if endpoints and load_profile
            else "partial_input",
            "endpoints": endpoints,
            "load_profile": load_profile,
            "script_outline": [
                "warmup",
                "steady_load",
                "error_budget_check",
                "tech_journal_collection",
            ],
            "caveats": [
                "Без SLA, тестовых данных и стенда blueprint нельзя считать готовым к запуску."
            ],
        }

    async def generate_yaxunit_tests(
        self, module_name: str, functions: List[str]
    ) -> str:
        """
        Генерирует модульные тесты для YAxUnit (BIA Technologies)

        Args:
            module_name: Название тестируемого модуля
            functions: Список функций

        Returns:
            BSL код тестового модуля
        """
        bsl_code = f"""// YAxUnit Test Module for {module_name}
// Generated by QA Agent (1C AI Stack)

#Использовать yaxunit

Перем ЮТ;

Процедура Инициализация() Экспорт
    ЮТ = Плагин("ЮТ");
КонецПроцедуры

// === Тесты ===
"""

        for func in functions:
            bsl_code += f"""
Процедура Тест_{func}() Экспорт
    // Подготовка данных
    ОжидаемоеЗначение = Истина;
    
    // Вызов тестируемой функции
    // Результат = {module_name}.{func}();
    
    // Проверка (Assert)
    ЮТ.УтверждаетЧто(ОжидаемоеЗначение).Равно(Истина, "Функция {func} должна вернуть Истина");
КонецПроцедуры
"""

        bsl_code += """
// === Регистрация тестов ===
Процедура ВыполнитьТесты() Экспорт
    ЮТ.ЗапуститьТесты();
КонецПроцедуры
"""
        return bsl_code

    async def generate_regression_tests(self, bug_fixes: List[str]) -> str:
        """
        Генерирует регрессионные тесты для исправленных багов

        Args:
            bug_fixes: Список исправленных багов

        Returns:
            Регрессионные тесты
        """
        tests = """# language: ru

Функционал: Регрессионное тестирование исправленных багов

"""
        for i, bug in enumerate(bug_fixes, 1):
            tests += f"""
Сценарий: Проверка исправления бага #{i}
    # {bug}
    Дано выполнены предусловия для воспроизведения бага
    Когда я выполняю действия из бага
    Тогда баг не воспроизводится
    И система работает корректно

"""

        return tests


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        agent = QAEngineerAgent()

        # Test 1: Generate Vanessa tests
        print("=== Test 1: Generate Vanessa BDD Tests ===")
        vanessa = await agent.generate_vanessa_tests(
            "ПродажиСервер", ["СоздатьЗаказ", "РассчитатьСумму", "ПровестиДокумент"]
        )
        print(vanessa[:300] + "...")

        # Test 2: Smoke tests
        print("\n=== Test 2: Generate Smoke Tests ===")
        smoke = await agent.generate_smoke_tests("Управление продажами")
        print(f"Smoke tests: {len(smoke)}")
        for test in smoke:
            print(f"- {test['name']}")

        # Test 3: Coverage analysis
        print("\n=== Test 3: Analyze Coverage ===")
        coverage = await agent.analyze_test_coverage(
            "Функция Test()\n  // code\nКонецФункции"
        )
        print(f"Coverage: {coverage['coverage_percent']}%")

    asyncio.run(test())
