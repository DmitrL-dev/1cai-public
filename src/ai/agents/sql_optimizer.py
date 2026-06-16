
"""
SQL Optimizer Agent
AI-оптимизация SQL запросов для 1С (PostgreSQL, MS SQL)

Источники best practices:
- its.1c.ru - Официальная документация 1С
- infostart.ru - Сообщество 1С разработчиков
- PostgreSQL docs - postgrespro.ru
- MS SQL docs - Microsoft Learn
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SQLOptimization:
    """Рекомендация по оптимизации SQL"""

    issue_type: str
    severity: str  # critical, high, medium, low
    current_query: str
    optimized_query: str
    explanation: str
    expected_improvement: str
    source: str  # ITS, Infostart, PostgreSQL, MSSQL


@dataclass
class IndexRecommendation:
    """Рекомендация по индексу"""

    table: str
    columns: List[str]
    index_type: str  # btree, hash, gin, gist
    rationale: str
    estimated_speedup: str
    create_statement: str


class SQLOptimizer:
    """
    AI Оптимизатор SQL запросов для 1С

    Supports:
    - PostgreSQL
    - MS SQL Server
    - 1С Query Language
    """

    def __init__(self, database_type: str = "postgresql"):
        self.database_type = database_type

        # Загрузка best practices
        self.anti_patterns = self._load_sql_anti_patterns()
        self.optimization_rules = self._load_optimization_rules()
        self.index_strategies = self._load_index_strategies()
        self.config_recommendations = self._load_config_recommendations()

    # ==========================================
    # ГЛАВНЫЙ API
    # ==========================================

    async def optimize_query(
        self, query: str, context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Полная оптимизация SQL запроса

        Args:
            query: SQL запрос для оптимизации
            context: {
                "database": "postgresql",
                "table_stats": {...},
                "explain_plan": {...}
            }

        Returns:
            {
                "original_query": "...",
                "optimized_query": "...",
                "optimizations": [...],
                "index_recommendations": [...],
                "expected_improvement": "50-80% faster",
                "confidence": 0.85
            }
        """
        logger.info("Optimizing SQL query")

        # 1. Детекция anti-patterns
        anti_patterns_found = await self._detect_sql_anti_patterns(query)

        # 2. Анализ структуры запроса
        query_structure = await self._analyze_query_structure(query)

        # 3. Генерация оптимизаций
        optimizations = await self._generate_optimizations(
            query, anti_patterns_found, query_structure, context
        )

        # 4. Рекомендации по индексам
        index_recommendations = await self._recommend_indexes(
            query, query_structure, context
        )

        # 5. Создание оптимизированного запроса
        optimized_query = await self._apply_optimizations(query, optimizations)

        # 6. Оценка улучшения
        improvement = await self._estimate_improvement(
            anti_patterns_found, optimizations, context
        )

        return {
            "original_query": query,
            "optimized_query": optimized_query,
            "optimizations": optimizations,
            "index_recommendations": index_recommendations,
            "anti_patterns_found": anti_patterns_found,
            "expected_improvement": improvement["description"],
            "speedup_factor": improvement["factor"],
            "confidence": improvement["confidence"],
            "sources": self._get_sources_used(optimizations),
        }

    # ==========================================
    # ДЕТЕКЦИЯ ANTI-PATTERNS
    # ==========================================

    async def _detect_sql_anti_patterns(self, query: str) -> List[Dict[str, Any]]:
        """
        Детекция SQL anti-patterns

        Based on:
        - Infostart.ru best practices
        - PostgreSQL performance guides
        - MS SQL optimization guides
        - 1С ITS recommendations
        """
        patterns_found = []
        query_upper = query.upper()

        # 1. SELECT * (избегать!)
        if re.search(r"SELECT\s+\*", query_upper):
            patterns_found.append(
                {
                    "type": "SELECT_STAR",
                    "severity": "medium",
                    "description": "Использование SELECT * вместо явного указания столбцов",
                    "impact": "Передача ненужных данных, снижение производительности",
                    "source": "PostgreSQL Best Practices",
                    "reference": "https://nuancesprog.ru/p/16455/",
                }
            )

        # 2. Нет WHERE clause (опасно для больших таблиц!)
        if "WHERE" not in query_upper and "JOIN" in query_upper:
            patterns_found.append(
                {
                    "type": "NO_WHERE_CLAUSE",
                    "severity": "high",
                    "description": "Отсутствует фильтрация данных (WHERE)",
                    "impact": "Полное сканирование таблицы, критично замедляет",
                    "source": "Infostart.ru + ITS",
                    "reference": "https://its.1c.ru/db/metod8dev/",
                }
            )

        # 3. N+1 Problem (запрос в цикле)
        # Для 1С - проверка паттерна "Для Каждого ... Запрос"
        if "Для Каждого" in query or "FOR EACH" in query_upper:
            patterns_found.append(
                {
                    "type": "N_PLUS_ONE",
                    "severity": "critical",
                    "description": "N+1 queries problem - запрос на каждой итерации",
                    "impact": "Линейный рост времени выполнения",
                    "source": "ITS + Infostart",
                    "reference": "https://its.1c.ru/db/metod8dev/",
                }
            )

        # 4. Нет использования LIMIT (для больших результатов)
        if (
            "SELECT" in query_upper
            and "LIMIT" not in query_upper
            and "TOP" not in query_upper
        ):
            # Проверяем что это не агрегирующий запрос
            if "SUM" not in query_upper and "COUNT" not in query_upper:
                patterns_found.append(
                    {
                        "type": "NO_LIMIT",
                        "severity": "medium",
                        "description": "Отсутствует LIMIT для ограничения результатов",
                        "impact": "Избыточная передача данных",
                        "source": "PostgreSQL Best Practices",
                    }
                )

        # 5. OR вместо IN (менее эффективно)
        or_count = query_upper.count(" OR ")
        if or_count > 5:
            patterns_found.append(
                {
                    "type": "MULTIPLE_OR",
                    "severity": "medium",
                    "description": f"Множественные OR ({or_count}) вместо IN",
                    "impact": "Сложный план выполнения, медленнее чем IN",
                    "source": "PostgreSQL + MS SQL",
                    "reference": "https://postgrespro.ru/education/courses/QPT",
                }
            )

        # 6. Функции в WHERE (не используются индексы!)
        if re.search(r"WHERE\s+\w+\([^)]+\)\s*=", query_upper):
            patterns_found.append(
                {
                    "type": "FUNCTION_IN_WHERE",
                    "severity": "high",
                    "description": "Использование функций в WHERE предотвращает использование индексов",
                    "impact": "Index scan невозможен, только Seq Scan",
                    "source": "PostgreSQL + ITS",
                    "reference": "https://sky.pro/wiki/analytics/detalnyj-razbor-explain-analyze/",
                }
            )

        # 7. Implicit type conversion
        if re.search(r"=\s*'[^']+'\s+AND\s+\w+\s*=\s*\d+", query):
            patterns_found.append(
                {
                    "type": "MIXED_TYPES",
                    "severity": "medium",
                    "description": "Смешивание типов данных в условиях",
                    "impact": "Implicit conversion, медленнее",
                    "source": "MS SQL + PostgreSQL",
                }
            )

        # 8. NOT IN с NULL (опасно!)
        if "NOT IN" in query_upper:
            patterns_found.append(
                {
                    "type": "NOT_IN_WITH_NULLS",
                    "severity": "high",
                    "description": "NOT IN может вернуть неожиданные результаты с NULL",
                    "impact": "Некорректные результаты + низкая производительность",
                    "source": "PostgreSQL Best Practices",
                    "fix": "Использовать NOT EXISTS или LEFT JOIN IS NULL",
                }
            )

        return patterns_found

    # ==========================================
    # ОПТИМИЗАЦИЯ ЗАПРОСОВ
    # ==========================================

    async def _generate_optimizations(
        self,
        query: str,
        anti_patterns: List[Dict],
        structure: Dict,
        context: Optional[Dict],
    ) -> List[SQLOptimization]:
        """Генерация оптимизаций на основе найденных проблем"""
        optimizations = []

        # Для каждого anti-pattern генерируем оптимизацию
        for pattern in anti_patterns:
            optimization = await self._create_optimization_for_pattern(
                query, pattern, context
            )
            if optimization:
                optimizations.append(optimization)

        return optimizations

    async def _create_optimization_for_pattern(
        self, query: str, pattern: Dict, context: Optional[Dict]
    ) -> Optional[SQLOptimization]:
        """Создание оптимизации для конкретного pattern"""

        pattern_type = pattern["type"]

        # SELECT * → Explicit columns
        if pattern_type == "SELECT_STAR":
            # В реальности нужно знать структуру таблицы
            # Пока generic рекомендация
            optimized = query.replace("SELECT *", "SELECT колонка1, колонка2, ...")

            return SQLOptimization(
                issue_type="SELECT_STAR",
                severity="medium",
                current_query=query,
                optimized_query=optimized,
                explanation="Замените SELECT * на явный список нужных столбцов",
                expected_improvement="10-30% меньше данных передается",
                source="PostgreSQL Best Practices",
            )

        # NO WHERE → Add filtering
        elif pattern_type == "NO_WHERE_CLAUSE":
            return SQLOptimization(
                issue_type="NO_WHERE_CLAUSE",
                severity="high",
                current_query=query,
                optimized_query=query + "\nWHERE условие_фильтрации",
                explanation="Добавьте WHERE clause для фильтрации данных",
                expected_improvement="100x-1000x ускорение на больших таблицах",
                source="ITS + Infostart",
            )

        # N+1 → JOIN or temp table
        elif pattern_type == "N_PLUS_ONE":
            return SQLOptimization(
                issue_type="N_PLUS_ONE",
                severity="critical",
                current_query=query,
                optimized_query=self._convert_n_plus_one_to_join(query),
                explanation="Замените цикл с запросами на один JOIN или временную таблицу",
                expected_improvement="N раз ускорение (N = количество итераций)",
                source="ITS (its.1c.ru/db/metod8dev/)",
            )

        # MULTIPLE OR → IN
        elif pattern_type == "MULTIPLE_OR":
            optimized = self._convert_or_to_in(query)
            return SQLOptimization(
                issue_type="MULTIPLE_OR",
                severity="medium",
                current_query=query,
                optimized_query=optimized,
                explanation="Замените множественные OR на IN",
                expected_improvement="20-40% ускорение",
                source="PostgreSQL + MS SQL",
            )

        # FUNCTION IN WHERE → Computed column or materialized view
        elif pattern_type == "FUNCTION_IN_WHERE":
            return SQLOptimization(
                issue_type="FUNCTION_IN_WHERE",
                severity="high",
                current_query=query,
                optimized_query=self._remove_function_from_where(query),
                explanation="Вычисляйте функции заранее или используйте computed columns",
                expected_improvement="10x-100x (индексы станут работать)",
                source="PostgreSQL Best Practices",
            )

        # NOT IN → NOT EXISTS
        elif pattern_type == "NOT_IN_WITH_NULLS":
            optimized = query.replace("NOT IN", "NOT EXISTS")
            return SQLOptimization(
                issue_type="NOT_IN_WITH_NULLS",
                severity="high",
                current_query=query,
                optimized_query=optimized,
                explanation="Замените NOT IN на NOT EXISTS для безопасности и производительности",
                expected_improvement="Корректные результаты + 30% ускорение",
                source="PostgreSQL Best Practices",
            )

        return None

    def _convert_n_plus_one_to_join(self, query: str) -> str:
        """Конвертация N+1 в JOIN"""
        # Simplified example
        return """
-- ОПТИМИЗИРОВАННО: Один запрос вместо N
SELECT
    t1.колонка,
    t2.связанная_колонка
FROM таблица1 t1
JOIN таблица2 t2 ON t1.id = t2.foreign_id
WHERE t1.условие
        """.strip()

    def _convert_or_to_in(self, query: str) -> str:
        """Конвертация множественных OR в IN"""
        # Pattern: WHERE column = val1 OR column = val2 OR ...
        # Replace with: WHERE column IN (val1, val2, ...)

        # Simplified - в реальности нужен парсинг AST
        or_pattern = r"(\w+)\s*=\s*([^O]+?)\s+OR\s+\1\s*=\s*([^O]+?)\s+OR"

        match = re.search(or_pattern, query)
        if match:
            match.group(1)
            # Собираем все значения
            optimized = query  # TODO: Real conversion
            return optimized

        return query + "\n-- TODO: Конвертировать OR в IN"

    def _remove_function_from_where(self, query: str) -> str:
        """Убрать функцию из WHERE"""
        return (
            query
            + """

-- РЕКОМЕНДАЦИЯ: Создать computed column или использовать WHERE без функции
-- Вместо: WHERE UPPER(name) = 'VALUE'
-- Лучше: WHERE name = 'Value' (с правильным регистром)
-- Или создать: ALTER TABLE ADD COLUMN name_upper AS UPPER(name) STORED
        """
        )

    # ==========================================
    # РЕКОМЕНДАЦИИ ПО ИНДЕКСАМ
    # ==========================================

    async def _recommend_indexes(
        self, query: str, structure: Dict, context: Optional[Dict]
    ) -> List[IndexRecommendation]:
        """
        Рекомендации по индексам

        Based on:
        - PostgreSQL index strategies
        - MS SQL indexing best practices
        - 1C query patterns
        """
        recommendations = []

        # 1. Индексы для WHERE условий
        where_columns = self._extract_where_columns(query)
        for column_info in where_columns:
            rec = self._create_index_recommendation(
                column_info["table"], [column_info["column"]], column_info["operator"]
            )
            if rec:
                recommendations.append(rec)

        # 2. Индексы для JOIN
        join_columns = self._extract_join_columns(query)
        for join_info in join_columns:
            rec = IndexRecommendation(
                table=join_info["table"],
                columns=[join_info["column"]],
                index_type="btree",
                rationale=f"JOIN на {join_info['column']} будет использовать индекс",
                estimated_speedup="5x-50x для JOIN operations",
                create_statement=f"CREATE INDEX idx_{join_info['table']}_{join_info['column']} ON {join_info['table']}({join_info['column']});",
            )
            recommendations.append(rec)

        # 3. Composite indexes для множественных WHERE
        if len(where_columns) > 1:
            # Рекомендуем composite index
            if where_columns[0]["table"] == where_columns[1]["table"]:
                table = where_columns[0]["table"]
                columns = [
                    c["column"] for c in where_columns[:3] if c["table"] == table
                ]

                rec = IndexRecommendation(
                    table=table,
                    columns=columns,
                    index_type="btree",
                    rationale="Composite index для множественных WHERE условий",
                    estimated_speedup="10x-100x",
                    create_statement=f"CREATE INDEX idx_{table}_composite ON {table}({', '.join(columns)});",
                )
                recommendations.append(rec)

        return recommendations

    def _create_index_recommendation(
        self, table: str, columns: List[str], operator: str
    ) -> Optional[IndexRecommendation]:
        """Создание рекомендации по индексу"""

        # Выбор типа индекса по оператору
        index_type = "btree"  # Default

        if operator in ["LIKE", "ILIKE"]:
            index_type = "gin"  # For full-text
            rationale = "GIN index для LIKE/ILIKE операций"
        elif operator in ["=", ">", "<", ">=", "<=", "BETWEEN"]:
            index_type = "btree"
            rationale = "B-Tree index для сравнений и диапазонов"
        elif operator in ["@>", "<@", "&&"]:  # JSONB operators
            index_type = "gin"
            rationale = "GIN index для JSONB операций"
        else:
            rationale = "Базовый B-Tree index"

        return IndexRecommendation(
            table=table,
            columns=columns,
            index_type=index_type,
            rationale=rationale,
            estimated_speedup="10x-1000x (зависит от размера таблицы)",
            create_statement=f"CREATE INDEX idx_{table}_{'_'.join(columns)} ON {table} USING {index_type} ({', '.join(columns)});",
        )

    def _extract_where_columns(self, query: str) -> List[Dict]:
        """Извлечение столбцов из WHERE"""
        # Simplified extraction
        where_match = re.search(
            r"WHERE\s+(.+?)(?:GROUP BY|ORDER BY|LIMIT|$)",
            query,
            re.IGNORECASE | re.DOTALL,
        )

        if not where_match:
            return []

        where_clause = where_match.group(1)

        # Ищем паттерн: table.column operator value
        pattern = r"(\w+)\.(\w+)\s*(=|>|<|>=|<=|LIKE|IN)\s*"
        matches = re.findall(pattern, where_clause, re.IGNORECASE)

        return [
            {"table": m[0], "column": m[1], "operator": m[2].upper()} for m in matches
        ]

    def _extract_join_columns(self, query: str) -> List[Dict]:
        """Извлечение столбцов из JOIN"""
        # Pattern: JOIN table ON t1.col = t2.col
        pattern = r"JOIN\s+(\w+)\s+\w+\s+ON\s+\w+\.(\w+)\s*=\s*\w+\.(\w+)"
        matches = re.findall(pattern, query, re.IGNORECASE)

        join_columns = []
        for match in matches:
            table = match[0]
            column = match[1]  # или match[2]
            join_columns.append({"table": table, "column": column})

        return join_columns

    # ==========================================
    # 1C-SPECIFIC OPTIMIZATIONS
    # ==========================================

    async def optimize_1c_query(
        self, query_1c: str, context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Оптимизация запроса на языке запросов 1С

        Based on: ITS + Infostart best practices

        Optimizations:
        - ИНДЕКСИРОВАТЬ ПО
        - Правильные JOIN
        - ПЕРВЫЕ N
        - Временные таблицы
        - Виртуальные таблицы регистров
        """
        optimizations = []

        # 1. Проверка ИНДЕКСИРОВАТЬ ПО
        if "ИНДЕКСИРОВАТЬ ПО" not in query_1c:
            if "ГДЕ" in query_1c or "УПОРЯДОЧИТЬ ПО" in query_1c:
                optimizations.append(
                    {
                        "type": "MISSING_INDEX_HINT",
                        "severity": "high",
                        "recommendation": "Добавить ИНДЕКСИРОВАТЬ ПО для ключевых полей",
                        "source": "ITS (its.1c.ru)",
                        "example": """
ВЫБРАТЬ
    Номенклатура,
    СУММА(Количество) КАК Количество
ИЗ
    РегистрНакопления.ОстаткиТоваров
ГДЕ
    Период МЕЖДУ &ДатаНач И &ДатаКон
СГРУППИРОВАТЬ ПО
    Номенклатура
ИНДЕКСИРОВАТЬ ПО
    Номенклатура  // ← Ускорит группировку!
                    """,
                    }
                )

        # 2. Использование виртуальных таблиц
        if "РегистрНакопления" in query_1c and "Остатки" in query_1c:
            if "ОстаткиИОбороты" not in query_1c:
                optimizations.append(
                    {
                        "type": "USE_VIRTUAL_TABLE",
                        "severity": "high",
                        "recommendation": "Использовать виртуальную таблицу ОстаткиИОбороты",
                        "source": "ITS + Infostart",
                        "example": """
// ВМЕСТО ручного расчета остатков:
ВЫБРАТЬ СУММА(КоличествоПриход - КоличествоРасход)
ИЗ РегистрНакопления.Товары

// ИСПОЛЬЗОВАТЬ виртуальную таблицу:
ВЫБРАТЬ
    Номенклатура,
    КоличествоОстаток
ИЗ
    РегистрНакопления.Товары.Остатки(, , , )

// Платформа сама оптимизирует!
                    """,
                    }
                )

        # 3. ПЕРВЫЕ N для ограничения
        if "ПЕРВЫЕ" not in query_1c and "УПОРЯДОЧИТЬ ПО" in query_1c:
            optimizations.append(
                {
                    "type": "USE_TOP_N",
                    "severity": "medium",
                    "recommendation": "Использовать ПЕРВЫЕ N для ограничения результатов",
                    "source": "ITS",
                    "example": "ВЫБРАТЬ ПЕРВЫЕ 100\n  ...",
                }
            )

        return {
            "optimizations": optimizations,
            "optimized_query": self._apply_1c_optimizations(query_1c, optimizations),
            "sources": ["ITS", "Infostart"],
        }

    def _apply_1c_optimizations(self, query: str, optimizations: List[Dict]) -> str:
        """Применение оптимизаций к 1С запросу"""
        optimized = query

        # Применяем каждую оптимизацию
        for opt in optimizations:
            if opt["type"] == "USE_TOP_N" and "ПЕРВЫЕ" not in optimized:
                optimized = optimized.replace("ВЫБРАТЬ", "ВЫБРАТЬ ПЕРВЫЕ 1000")

            # Добавляем ИНДЕКСИРОВАТЬ ПО если нужно
            if opt["type"] == "MISSING_INDEX_HINT":
                # Находим ключевые поля из ГДЕ и УПОРЯДОЧИТЬ ПО
                # Добавляем ИНДЕКСИРОВАТЬ ПО перед концом запроса
                if "ИНДЕКСИРОВАТЬ ПО" not in optimized:
                    # Простая эвристика - индексируем по первому полю в ГДЕ
                    where_match = re.search(r"ГДЕ\s+(\w+)", optimized)
                    if where_match:
                        field = where_match.group(1)
                        optimized += f"\nИНДЕКСИРОВАТЬ ПО\n    {field}"

        return optimized

    # ==========================================
    # ANALYZE QUERY STRUCTURE
    # ==========================================

    async def _analyze_query_structure(self, query: str) -> Dict[str, Any]:
        """Анализ структуры запроса"""
        return {
            "has_where": "WHERE" in query.upper(),
            "has_join": "JOIN" in query.upper(),
            "has_group_by": "GROUP BY" in query.upper(),
            "has_order_by": "ORDER BY" in query.upper(),
            "has_limit": "LIMIT" in query.upper() or "TOP" in query.upper(),
            "table_count": len(re.findall(r"FROM\s+(\w+)", query, re.IGNORECASE)),
            "complexity": self._estimate_query_complexity(query),
        }

    def _estimate_query_complexity(self, query: str) -> str:
        """Оценка сложности запроса"""
        score = 0

        score += query.upper().count("JOIN")
        score += query.upper().count("UNION") * 2
        score += query.upper().count("SUBQUERY") * 2
        score += query.upper().count("GROUP BY")

        if score < 3:
            return "simple"
        elif score < 7:
            return "moderate"
        else:
            return "complex"

    # ==========================================
    # APPLY OPTIMIZATIONS
    # ==========================================

    async def _apply_optimizations(
        self, query: str, optimizations: List[SQLOptimization]
    ) -> str:
        """Применение всех оптимизаций к запросу"""
        optimized = query

        for opt in optimizations:
            # Применяем оптимизацию
            # В реальности нужен SQL AST parser и rewriter
            # Пока просто берем optimized_query из первой оптимизации
            if opt.optimized_query and opt.optimized_query != query:
                optimized = opt.optimized_query
                break  # Берем первую существенную оптимизацию

        return optimized

    # ==========================================
    # ESTIMATE IMPROVEMENT
    # ==========================================

    async def _estimate_improvement(
        self,
        anti_patterns: List[Dict],
        optimizations: List[SQLOptimization],
        context: Optional[Dict],
    ) -> Dict[str, Any]:
        """Оценка ожидаемого улучшения"""

        # Severity weights
        severity_impact = {"critical": 10.0, "high": 5.0, "medium": 2.0, "low": 1.0}

        total_impact = sum(
            severity_impact.get(ap["severity"], 1.0) for ap in anti_patterns
        )

        # Speedup factor estimation
        if total_impact >= 15:
            factor = "10x-100x"
            description = "Критические оптимизации, ожидается 10-100x ускорение"
            confidence = 0.9
        elif total_impact >= 8:
            factor = "3x-10x"
            description = "Существенные оптимизации, ожидается 3-10x ускорение"
            confidence = 0.8
        elif total_impact >= 3:
            factor = "2x-3x"
            description = "Умеренные оптимизации, ожидается 2-3x ускорение"
            confidence = 0.7
        else:
            factor = "1.2x-2x"
            description = "Небольшие улучшения, ожидается 20-100% ускорение"
            confidence = 0.6

        return {
            "factor": factor,
            "description": description,
            "confidence": confidence,
            "total_impact_score": total_impact,
        }

    def _get_sources_used(self, optimizations: List[SQLOptimization]) -> List[str]:
        """Список использованных источников"""
        sources = set()
        for opt in optimizations:
            sources.add(opt.source)
        return list(sources)

    # ==========================================
    # DATABASE CONFIGURATION
    # ==========================================

    async def recommend_database_config(
        self, database_type: str, system_resources: Dict
    ) -> Dict[str, Any]:
        """
        Рекомендации по настройке СУБД

        Args:
            database_type: "postgresql" or "mssql"
            system_resources: {"ram_gb": 16, "cpu_cores": 8, "ssd": True}

        Returns:
            Рекомендованные параметры конфигурации
        """
        if database_type == "postgresql":
            return await self._recommend_postgresql_config(system_resources)
        elif database_type == "mssql":
            return await self._recommend_mssql_config(system_resources)
        else:
            return {"error": f"Unsupported database: {database_type}"}

    async def _recommend_postgresql_config(self, resources: Dict) -> Dict[str, Any]:
        """
        Рекомендации по PostgreSQL конфигурации

        Source: postgrespro.ru + PostgreSQL docs
        """
        ram_gb = resources.get("ram_gb", 8)
        cpu_cores = resources.get("cpu_cores", 4)
        is_ssd = resources.get("ssd", False)

        # Расчет параметров по формулам из PostgreSQL wiki
        shared_buffers_mb = int(ram_gb * 1024 * 0.25)  # 25% RAM
        effective_cache_size_mb = int(ram_gb * 1024 * 0.75)  # 75% RAM
        work_mem_mb = int((ram_gb * 1024 * 0.05) / cpu_cores)  # 5% RAM / cores
        maintenance_work_mem_mb = int(ram_gb * 1024 * 0.1)  # 10% RAM

        config = {
            "shared_buffers": f"{shared_buffers_mb}MB",
            "effective_cache_size": f"{effective_cache_size_mb}MB",
            "work_mem": f"{work_mem_mb}MB",
            "maintenance_work_mem": f"{maintenance_work_mem_mb}MB",
            "max_worker_processes": cpu_cores,
            "max_parallel_workers": cpu_cores,
            "max_parallel_workers_per_gather": max(cpu_cores // 2, 2),
            "random_page_cost": 1.1 if is_ssd else 4.0,  # SSD vs HDD
            "effective_io_concurrency": 200 if is_ssd else 2,
            "wal_buffers": "16MB",
            "checkpoint_completion_target": 0.9,
            "default_statistics_target": 100,
        }

        # Autovacuum tuning
        config.update(
            {
                "autovacuum": "on",
                "autovacuum_max_workers": 3,
                "autovacuum_naptime": "20s",
                "autovacuum_vacuum_scale_factor": 0.05,  # Более частый vacuum
                "autovacuum_analyze_scale_factor": 0.02,
            }
        )

        return {
            "database": "PostgreSQL",
            "system_resources": resources,
            "recommended_config": config,
            "config_file_snippet": self._generate_postgresql_conf(config),
            "sources": [
                "https://postgrespro.ru/education/courses/QPT",
                "https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server",
            ],
            "estimated_improvement": "30-50% overall performance improvement",
        }

    def _generate_postgresql_conf(self, config: Dict) -> str:
        """Генерация конфига postgresql.conf"""
        lines = ["# PostgreSQL Configuration - Optimized for 1C"]
        lines.append("# Generated by AI Architect\n")

        for key, value in config.items():
            lines.append(f"{key} = {value}")

        return "\n".join(lines)

    async def _recommend_mssql_config(self, resources: Dict) -> Dict[str, Any]:
        """Рекомендации по MS SQL конфигурации"""
        ram_gb = resources.get("ram_gb", 8)

        # MS SQL settings
        max_server_memory_mb = int(ram_gb * 1024 * 0.8)  # 80% RAM for SQL Server

        config = {
            "max server memory (MB)": max_server_memory_mb,
            "cost threshold for parallelism": 5,
            "max degree of parallelism": resources.get("cpu_cores", 4),
            "optimize for ad hoc workloads": 1,
            "backup compression default": 1,
        }

        return {
            "database": "MS SQL Server",
            "recommended_config": config,
            "sources": ["Microsoft Learn - SQL Server Performance"],
            "estimated_improvement": "20-40% overall performance",
        }

    # ==========================================
    # KNOWLEDGE BASE
    # ==========================================

    def _load_sql_anti_patterns(self) -> Dict:
        """База знаний SQL anti-patterns"""
        return {
            "SELECT_STAR": "Избегать SELECT *",
            "NO_WHERE": "Всегда использовать WHERE для фильтрации",
            "N_PLUS_ONE": "N+1 queries - критическая проблема",
            "FUNCTION_IN_WHERE": "Функции в WHERE блокируют индексы",
        }

    def _load_optimization_rules(self) -> Dict:
        """Правила оптимизации"""
        return {}

    def _load_index_strategies(self) -> Dict:
        """Стратегии индексирования"""
        return {
            "btree": "Для =, >, <, BETWEEN",
            "hash": "Только для =",
            "gin": "Для JSONB, arrays, full-text",
            "gist": "Для геоданных, ranges",
        }

    def _load_config_recommendations(self) -> Dict:
        """Рекомендации по конфигурации"""
        return {}


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        optimizer = SQLOptimizer("postgresql")

        # Test 1: Optimize generic SQL
        print("=== Test 1: PostgreSQL Query Optimization ===")
        query = """
        SELECT * FROM orders
        JOIN customers ON orders.customer_id = customers.id
        WHERE UPPER(customers.name) = 'ACME'
        """

        result = await optimizer.optimize_query(query)
        print(f"Anti-patterns found: {len(result['anti_patterns_found'])}")
        print(f"Optimizations: {len(result['optimizations'])}")
        print(f"Index recommendations: {len(result['index_recommendations'])}")
        print(f"Expected improvement: {result['expected_improvement']}")

        # Test 2: Optimize 1C query
        print("\n=== Test 2: 1C Query Optimization ===")
        query_1c = """
        ВЫБРАТЬ
            Номенклатура,
            СУММА(Количество) КАК Количество
        ИЗ
            РегистрНакопления.Продажи
        ГДЕ
            Период МЕЖДУ &ДатаНач И &ДатаКон
        СГРУППИРОВАТЬ ПО
            Номенклатура
        """

        result_1c = await optimizer.optimize_1c_query(query_1c)
        print(f"1C Optimizations: {len(result_1c['optimizations'])}")

        # Test 3: Database config
        print("\n=== Test 3: Database Configuration ===")
        config = await optimizer.recommend_database_config(
            "postgresql", {"ram_gb": 16, "cpu_cores": 8, "ssd": True}
        )
        print(f"Config parameters: {len(config['recommended_config'])}")
        print(f"Estimated improvement: {config['estimated_improvement']}")

    asyncio.run(test())
