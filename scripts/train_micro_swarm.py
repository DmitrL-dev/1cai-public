"""Self-training script for Micro-Swarm BSL models.

Trains all 5 domain models on synthetic bootstrap data,
then saves weights to data/models/{domain}.json.

Usage: python -m scripts.train_micro_swarm
"""

import json
import os
from pathlib import Path

# Bootstrap training samples: (code, domain_targets)
# domain_targets: {domain_name: target_float}
SAMPLES = [
    # === CLEAN CODE (target 0.0 for all) ===
    (
        "Процедура ОбработатьДанные(Данные)\n"
        "    Если Данные <> Неопределено Тогда\n"
        "        Сообщить(Данные);\n"
        "    КонецЕсли;\n"
        "КонецПроцедуры",
        {
            "bsl_quality": 0.0,
            "query_optimizer": 0.0,
            "error_predictor": 0.0,
            "bsl_pattern": 0.0,
        },
    ),
    (
        "Функция ПолучитьСписок()\n"
        "    Запрос = Новый Запрос;\n"
        '    Запрос.Текст = "ВЫБРАТЬ Наименование ИЗ Справочник.Номенклатура";\n'
        "    Возврат Запрос.Выполнить().Выгрузить();\n"
        "КонецФункции",
        {
            "bsl_quality": 0.1,
            "query_optimizer": 0.1,
            "error_predictor": 0.0,
            "bsl_pattern": 0.3,
        },
    ),
    # === N+1 QUERY (query_optimizer target 1.0) ===
    (
        "Для Каждого Стр Из Таблица Цикл\n"
        "    Запрос = Новый Запрос;\n"
        '    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Номенклатура ГДЕ Ссылка = &Ссылка";\n'
        '    Запрос.УстановитьПараметр("Ссылка", Стр.Номенклатура);\n'
        "    Результат = Запрос.Выполнить();\n"
        "КонецЦикла;",
        {
            "bsl_quality": 0.6,
            "query_optimizer": 1.0,
            "error_predictor": 0.3,
            "bsl_pattern": 0.4,
        },
    ),
    # === SELECT * (query_optimizer target 0.8) ===
    (
        'Запрос.Текст = "ВЫБРАТЬ * ИЗ Документ.РеализацияТоваров";\n'
        "Результат = Запрос.Выполнить().Выгрузить();",
        {
            "bsl_quality": 0.3,
            "query_optimizer": 0.8,
            "error_predictor": 0.0,
            "bsl_pattern": 0.3,
        },
    ),
    # === EMPTY CATCH (error_predictor target 1.0) ===
    (
        "Попытка\n    ВыполнитьОперацию();\nИсключение\nКонецПопытки;",
        {
            "bsl_quality": 0.7,
            "query_optimizer": 0.0,
            "error_predictor": 1.0,
            "bsl_pattern": 0.1,
        },
    ),
    # === DEEP NESTING (quality target 0.9) ===
    (
        "Если А Тогда\n"
        "    Если Б Тогда\n"
        "        Если В Тогда\n"
        "            Если Г Тогда\n"
        "                Если Д Тогда\n"
        '                    Сообщить("глубоко");\n'
        "                КонецЕсли;\n"
        "            КонецЕсли;\n"
        "        КонецЕсли;\n"
        "    КонецЕсли;\n"
        "КонецЕсли;",
        {
            "bsl_quality": 0.9,
            "query_optimizer": 0.0,
            "error_predictor": 0.5,
            "bsl_pattern": 0.1,
        },
    ),
    # === MAGIC NUMBERS (error_predictor 0.7) ===
    (
        "Если СуммаДокумента > 150000 Тогда\n"
        "    Скидка = СуммаДокумента * 0.15;\n"
        "    НДС = СуммаДокумента * 0.20;\n"
        "КонецЕсли;",
        {
            "bsl_quality": 0.5,
            "query_optimizer": 0.0,
            "error_predictor": 0.7,
            "bsl_pattern": 0.1,
        },
    ),
    # === FORM HANDLER (bsl_pattern target 0.8) ===
    (
        "Процедура ПриОткрытии()\n"
        '    ЭтаФорма.Заголовок = "Тест";\n'
        "    ОбновитьОтображение();\n"
        "КонецПроцедуры\n"
        "Процедура ПриЗакрытии()\n"
        "    // cleanup\n"
        "КонецПроцедуры",
        {
            "bsl_quality": 0.1,
            "query_optimizer": 0.0,
            "error_predictor": 0.0,
            "bsl_pattern": 0.8,
        },
    ),
]

EPOCHS = 200
LR = 0.005
MODELS_DIR = Path("data/models")


def train():
    """Train all domain models on bootstrap data."""
    # Import after path setup
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from src.micro_swarm.bsl_domains import (
        BSL_PATTERN_DOMAIN,
        BSL_QUALITY_DOMAIN,
        QUERY_OPTIMIZER_DOMAIN,
        ERROR_PREDICTOR_DOMAIN,
        extract_bsl_pattern_features,
        extract_bsl_quality_features,
        extract_query_optimizer_features,
        extract_error_features,
    )
    from src.micro_swarm.model import MicroModel, MicroModelConfig

    BSL_DOMAINS = [
        (BSL_PATTERN_DOMAIN, extract_bsl_pattern_features),
        (BSL_QUALITY_DOMAIN, extract_bsl_quality_features),
        (QUERY_OPTIMIZER_DOMAIN, extract_query_optimizer_features),
        (ERROR_PREDICTOR_DOMAIN, extract_error_features),
    ]

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    for domain, extractor in BSL_DOMAINS:
        name = domain.name
        n_feat = len(domain.features)
        print(f"\n{'=' * 50}")
        print(f"Training: {name} ({n_feat} features)")
        print(f"{'=' * 50}")

        model = MicroModel(MicroModelConfig(n_features=n_feat))

        # Collect training pairs for this domain
        pairs = []
        for code, targets in SAMPLES:
            if name not in targets:
                continue
            try:
                feats = extractor(code)
                feat_vec = [feats.get(fs.name, 0.0) for fs in domain.features]
                pairs.append((feat_vec, targets[name]))
            except Exception as e:
                print(f"  Skip sample: {e}")

        if not pairs:
            print(f"  No training data for {name}, skipping")
            continue

        print(f"  Samples: {len(pairs)}")

        # Training loop
        for epoch in range(EPOCHS):
            total_loss = 0.0
            for feats, target in pairs:
                loss = model.train_step(feats, target, lr=LR)
                total_loss += loss
            avg_loss = total_loss / len(pairs)
            if epoch % 50 == 0 or epoch == EPOCHS - 1:
                print(f"  Epoch {epoch:3d} | Loss: {avg_loss:.4f}")

        # Save weights
        path = MODELS_DIR / f"{name}.json"
        model.save(str(path))
        print(f"  Saved: {path}")

        # Verify
        for code, targets in SAMPLES[:3]:
            if name not in targets:
                continue
            feats = extractor(code)
            feat_vec = [feats.get(fs.name, 0.0) for fs in domain.features]
            score = model.forward(feat_vec)
            if isinstance(score, tuple):
                score = score[0]
            target = targets[name]
            print(f"  Verify: target={target:.1f} pred={score:.3f}")

    print(f"\nDone. Weights saved to {MODELS_DIR}/")


if __name__ == "__main__":
    train()
