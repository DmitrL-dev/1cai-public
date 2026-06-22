"""Tests for BSL MicroModel domains (Phase 3.5).

Tests all 5 BSL-oriented domains:
- BSL Pattern Detector
- BSL Code Quality
- 1C Query Optimizer
- BSL Error Predictor
- Config Similarity
"""

import pytest

from src.micro_swarm.bsl_domains import (
    BSL_PATTERN_DOMAIN,
    BSL_QUALITY_DOMAIN,
    CONFIG_SIMILARITY_DOMAIN,
    ERROR_PREDICTOR_DOMAIN,
    QUERY_OPTIMIZER_DOMAIN,
    extract_bsl_pattern_features,
    extract_bsl_quality_features,
    extract_config_features,
    extract_error_features,
    extract_query_optimizer_features,
)
from src.micro_swarm.model import MicroModel, MicroModelConfig

# ──────────────────────────────────────────
# Test fixtures — BSL code samples
# ──────────────────────────────────────────

FORM_HANDLER_CODE = """
Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)
    Если Не ЗначениеЗаполнено(Объект.Ссылка) Тогда
        ОбработкаЗаполнения();
    КонецЕсли;
КонецПроцедуры

Функция ПолучитьДанные() Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура";
    Возврат Запрос.Выполнить().Выгрузить();
КонецФункции
"""

PRINT_FORM_CODE = """
Процедура ПечатьНакладной(Ссылка)
    Макет = ПолучитьМакет("Накладная");
    ТаблДок = Новый ТабличныйДокумент;
    ТаблДок.Вывести(Макет);
КонецПроцедуры
"""

HTTP_CODE = """
Функция ОтправитьДанные(URL, Данные) Экспорт
    Соединение = Новый HTTPСоединение(URL);
    Запрос = Новый HTTPЗапрос("/api/data");
    Соединение.ОтправитьHTTP(Запрос);
КонецФункции
"""

COMPLEX_CODE = """
Процедура ОбработкаДанных(МассивДанных)
    Для Каждого Элемент Из МассивДанных Цикл
        Если Элемент.Тип = 1 Тогда
            Для Индекс = 0 По Элемент.Количество() - 1 Цикл
                Если Элемент.Значение[Индекс] > 100 Тогда
                    Попытка
                        Результат = Элемент.Значение[Индекс] / КоэффициентПересчета;
                    Исключение
                    КонецПопытки;
                КонецЕсли;
            КонецЦикла;
        ИначеЕсли Элемент.Тип = 2 Тогда
            Пока Элемент.ЕстьСледующий() Цикл
                Обработать(Элемент);
            КонецЦикла;
        КонецЕсли;
    КонецЦикла;
КонецПроцедуры
"""

QUERY_CODE = """
Процедура ЗагрузкаДанных()
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ
    |   Номенклатура.Ссылка,
    |   Номенклатура.Наименование
    |ИЗ
    |   Справочник.Номенклатура КАК Номенклатура
    |   ЛЕВОЕ СОЕДИНЕНИЕ Справочник.ЕдиницыИзмерения КАК Единицы
    |       ПО Номенклатура.ЕдиницаИзмерения = Единицы.Ссылка
    |   ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Склады КАК Склады
    |       ПО Номенклатура.Склад = Склады.Ссылка
    |   ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Поставщики КАК Поставщики
    |       ПО Номенклатура.Поставщик = Поставщики.Ссылка
    |   ЛЕВОЕ СОЕДИНЕНИЕ Справочник.Категории КАК Категории
    |       ПО Номенклатура.Категория = Категории.Ссылка
    |ГДЕ
    |   Номенклатура.Активна = ИСТИНА";
КонецПроцедуры
"""

N_PLUS_ONE_CODE = """
Процедура ОбработкаСписка()
    МассивСсылок = Получить();
    Для Каждого Ссылка Из МассивСсылок Цикл
        Запрос = Новый Запрос;
        Запрос.Текст = "ВЫБРАТЬ * ИЗ Документ.Заказ ГДЕ Ссылка = &Ссылка";
        Запрос.УстановитьПараметр("Ссылка", Ссылка);
        Результат = Запрос.Выполнить();
    КонецЦикла;
КонецПроцедуры
"""

ERROR_PRONE_CODE = """
Перем ГлобальнаяПеременная;
Перем Счетчик;

Функция Вычислить(А, Б)
    Попытка
        Результат = А / Б;
        Строка = "" + "Часть1" + "Часть2" + "Часть3";
        Если А > 100 Тогда
            Если Б < 50 Тогда
                Если Результат > 0 Тогда
                    Возврат Результат;
                КонецЕсли;
            КонецЕсли;
        КонецЕсли;
    Исключение;
    КонецПопытки;
    Возврат 0;
КонецФункции
"""

EMPTY_CODE = ""


# ──────────────────────────────────────────
# Domain 1: BSL Pattern Detector
# ──────────────────────────────────────────


class TestBSLPatternDetector:
    """Tests for BSL Pattern Detector domain."""

    def test_form_handler_detection(self):
        features = extract_bsl_pattern_features(FORM_HANDLER_CODE)
        assert features["has_form_handler"] == 1.0
        assert features["has_db_query"] == 1.0
        assert features["procedure_count"] == 1.0
        assert features["function_count"] == 1.0

    def test_print_form_detection(self):
        features = extract_bsl_pattern_features(PRINT_FORM_CODE)
        assert features["has_print_form"] == 1.0
        assert features["has_form_handler"] == 0.0

    def test_http_detection(self):
        features = extract_bsl_pattern_features(HTTP_CODE)
        assert features["has_http_call"] == 1.0
        assert features["has_db_query"] == 0.0

    def test_export_ratio(self):
        features = extract_bsl_pattern_features(FORM_HANDLER_CODE)
        # 1 export out of 2 routines = 0.5
        assert features["export_ratio"] == 0.5

    def test_empty_code(self):
        features = extract_bsl_pattern_features(EMPTY_CODE)
        assert features["has_form_handler"] == 0.0
        assert features["has_db_query"] == 0.0
        assert features["procedure_count"] == 0.0
        assert features["function_count"] == 0.0
        assert features["export_ratio"] == 0.0

    def test_domain_config_features_count(self):
        assert BSL_PATTERN_DOMAIN.n_features == 8

    def test_domain_extract_normalization(self):
        features = extract_bsl_pattern_features(FORM_HANDLER_CODE)
        normalized = BSL_PATTERN_DOMAIN.extract(features)
        assert len(normalized) == 8
        assert all(isinstance(v, float) for v in normalized)


# ──────────────────────────────────────────
# Domain 2: BSL Code Quality
# ──────────────────────────────────────────


class TestBSLCodeQuality:
    """Tests for BSL Code Quality domain."""

    def test_complex_code_metrics(self):
        features = extract_bsl_quality_features(COMPLEX_CODE)
        assert features["avg_complexity"] > 1.0
        assert features["loc"] > 0
        assert features["nesting_depth"] >= 3

    def test_doc_coverage(self):
        documented = """
// Функция для получения данных
// Параметры:
//   Ссылка - ссылка на объект
Функция ПолучитьДанные(Ссылка)
    Возврат Ссылка;
КонецФункции
"""
        features = extract_bsl_quality_features(documented)
        assert features["doc_coverage"] > 0.0

    def test_empty_code(self):
        features = extract_bsl_quality_features(EMPTY_CODE)
        assert features["loc"] == 1.0  # min 1 to avoid division by zero
        assert features["avg_complexity"] == 0.0

    def test_domain_config_features_count(self):
        assert BSL_QUALITY_DOMAIN.n_features == 8


# ──────────────────────────────────────────
# Domain 3: 1C Query Optimizer
# ──────────────────────────────────────────


class TestQueryOptimizer:
    """Tests for 1C Query Optimizer domain."""

    def test_n_plus_one_detection(self):
        features = extract_query_optimizer_features(N_PLUS_ONE_CODE)
        assert features["has_n_plus_one"] == 1.0

    def test_star_select_detection(self):
        features = extract_query_optimizer_features(N_PLUS_ONE_CODE)
        assert features["has_star_select"] == 1.0

    def test_no_query(self):
        simple = "Процедура Тест()\nКонецПроцедуры"
        features = extract_query_optimizer_features(simple)
        assert features["query_count"] == 0.0
        assert features["has_n_plus_one"] == 0.0

    def test_join_detection(self):
        features = extract_query_optimizer_features(QUERY_CODE)
        assert features["query_count"] >= 1.0

    def test_domain_config_features_count(self):
        assert QUERY_OPTIMIZER_DOMAIN.n_features == 8

    def test_empty_code(self):
        features = extract_query_optimizer_features(EMPTY_CODE)
        assert features["query_count"] == 0.0


# ──────────────────────────────────────────
# Domain 4: BSL Error Predictor
# ──────────────────────────────────────────


class TestErrorPredictor:
    """Tests for BSL Error Predictor domain."""

    def test_empty_catch_detection(self):
        features = extract_error_features(ERROR_PRONE_CODE)
        assert features["has_empty_catch"] == 1.0

    def test_string_concat(self):
        features = extract_error_features(ERROR_PRONE_CODE)
        assert features["string_concat_count"] >= 1.0

    def test_nesting_depth(self):
        features = extract_error_features(ERROR_PRONE_CODE)
        assert features["nested_if_depth"] >= 3

    def test_variable_count(self):
        features = extract_error_features(ERROR_PRONE_CODE)
        assert features["variable_reuse_count"] >= 2.0  # 2 Перем declarations

    def test_clean_code(self):
        clean = "Процедура Тест()\n    Возврат;\nКонецПроцедуры"
        features = extract_error_features(clean)
        assert features["has_empty_catch"] == 0.0
        assert features["has_unguarded_division"] == 0.0

    def test_domain_config_features_count(self):
        assert ERROR_PREDICTOR_DOMAIN.n_features == 8


# ──────────────────────────────────────────
# Domain 5: Config Similarity
# ──────────────────────────────────────────


class TestConfigSimilarity:
    """Tests for Config Similarity domain."""

    def test_feature_extraction(self):
        config = {
            "module_count": 150,
            "role_count": 12,
            "subsystem_depth": 4,
            "form_count": 200,
            "command_count": 50,
            "template_count": 30,
            "scheduled_job_count": 5,
            "attr_count": 1500,
        }
        features = extract_config_features(config)
        assert features["module_count"] == 150.0
        assert features["role_count"] == 12.0

    def test_empty_config(self):
        features = extract_config_features({})
        assert all(v == 0.0 for v in features.values())

    def test_partial_config(self):
        features = extract_config_features({"module_count": 10})
        assert features["module_count"] == 10.0
        assert features["role_count"] == 0.0

    def test_domain_config_features_count(self):
        assert CONFIG_SIMILARITY_DOMAIN.n_features == 8


# ──────────────────────────────────────────
# Integration: MicroModel + BSL Domains
# ──────────────────────────────────────────


class TestMicroModelBSLIntegration:
    """Smoke tests: MicroModel forward pass with BSL domains."""

    @pytest.mark.parametrize(
        "domain,extractor,data",
        [
            (
                BSL_PATTERN_DOMAIN,
                extract_bsl_pattern_features,
                FORM_HANDLER_CODE,
            ),
            (
                BSL_QUALITY_DOMAIN,
                extract_bsl_quality_features,
                COMPLEX_CODE,
            ),
            (
                QUERY_OPTIMIZER_DOMAIN,
                extract_query_optimizer_features,
                QUERY_CODE,
            ),
            (
                ERROR_PREDICTOR_DOMAIN,
                extract_error_features,
                ERROR_PRONE_CODE,
            ),
        ],
    )
    def test_forward_pass(self, domain, extractor, data):
        """MicroModel produces valid score and embedding with BSL features."""
        features = extractor(data)
        normalized = domain.extract(features)
        assert len(normalized) == domain.n_features

        config = MicroModelConfig(n_features=domain.n_features)
        model = MicroModel(config)
        score, emb = model.forward(normalized)

        assert 0.0 <= score <= 1.0
        assert len(emb) == config.n_embd

    def test_config_similarity_forward(self):
        """Config Similarity embedding distance works."""
        config1 = {
            "module_count": 100,
            "role_count": 10,
            "subsystem_depth": 3,
            "form_count": 150,
            "command_count": 40,
            "template_count": 20,
            "scheduled_job_count": 3,
            "attr_count": 800,
        }
        config2 = {
            "module_count": 120,
            "role_count": 15,
            "subsystem_depth": 5,
            "form_count": 300,
            "command_count": 80,
            "template_count": 40,
            "scheduled_job_count": 8,
            "attr_count": 2000,
        }

        domain = CONFIG_SIMILARITY_DOMAIN
        model_config = MicroModelConfig(n_features=domain.n_features)
        model = MicroModel(model_config)

        _, emb1 = model.forward(domain.extract(extract_config_features(config1)))
        _, emb2 = model.forward(domain.extract(extract_config_features(config2)))

        # Embeddings should exist and have same dimensionality
        assert len(emb1) == len(emb2) == model_config.n_embd

        # Cosine similarity check (should be computable)
        dot = sum(a * b for a, b in zip(emb1, emb2))
        mag1 = sum(a * a for a in emb1) ** 0.5
        mag2 = sum(b * b for b in emb2) ** 0.5
        if mag1 > 0 and mag2 > 0:
            cosine_sim = dot / (mag1 * mag2)
            assert -1.0 <= cosine_sim <= 1.0

    def test_training_step(self):
        """MicroModel trains on BSL quality features without crash."""
        features = extract_bsl_quality_features(COMPLEX_CODE)
        normalized = BSL_QUALITY_DOMAIN.extract(features)

        config = MicroModelConfig(n_features=BSL_QUALITY_DOMAIN.n_features)
        model = MicroModel(config)

        loss = model.train_step(normalized, target=0.8, lr=0.01)
        assert isinstance(loss, float)
        assert loss > 0.0
