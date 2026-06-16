
#!/usr/bin/env python3
"""
Полный pipeline обучения Neural BSL Parser

Шаги:
1. Подготовка dataset из PostgreSQL
2. Обучение модели
3. Валидация
4. Сохранение

Использование:
    python scripts/run_neural_training.py
    python scripts/run_neural_training.py --epochs 20 --batch-size 32

Версия: 1.0.0
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))


async def prepare_dataset():
    """Step 1: Подготовка dataset"""
    print("\n" + "=" * 70)
    print("STEP 1: Подготовка Training Dataset")
    print("=" * 70)
    
    from scripts.dataset.prepare_neural_training_data import \
        NeuralDatasetPreparer
    
    preparer = NeuralDatasetPreparer()
    await preparer.prepare_from_postgres()
    preparer.save_dataset()
    
    return preparer.output_dir


def train_model(dataset_dir: Path, epochs: int, batch_size: int):
    """Step 2: Обучение модели"""
    print("\n" + "=" * 70)
    print("STEP 2: Обучение Neural Parser")
    print("=" * 70)
    
    from scripts.parsers.neural.train_neural_parser import (
        BSLCodeDataset, NeuralParserTrainer)

    # Создаем trainer
    trainer = NeuralParserTrainer(
        learning_rate=1e-4,
        batch_size=batch_size
    )
    
    # Загружаем datasets
    train_dataset = BSLCodeDataset(
        data_path=str(dataset_dir / 'train.json'),
        tokenizer=trainer.tokenizer
    )
    
    val_dataset = BSLCodeDataset(
        data_path=str(dataset_dir / 'val.json'),
        tokenizer=trainer.tokenizer
    )
    
    # Обучаем
    trainer.train(
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        num_epochs=epochs,
        save_path='./models/neural_parser'
    )
    
    return trainer


def test_model():
    """Step 3: Тестирование модели"""
    print("\n" + "=" * 70)
    print("STEP 3: Тестирование Neural Parser")
    print("=" * 70)
    
    from scripts.parsers.neural.neural_bsl_parser import NeuralBSLParser
    
    parser = NeuralBSLParser()
    
    # Тестовые примеры
    test_codes = [
        """
        Функция ПолучитьСписокКлиентов() Экспорт
            Запрос = Новый Запрос;
            Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Клиенты";
            Возврат Запрос.Выполнить();
        КонецФункции
        """,
        """
        Функция РассчитатьНДС(Сумма, Ставка = 20) Экспорт
            Если Ставка <= 0 Тогда
                ВызватьИсключение "Неверная ставка";
            КонецЕсли;
            Возврат Сумма * Ставка / 100;
        КонецФункции
        """
    ]
    
    for i, code in enumerate(test_codes, 1):
        print(f"\n--- Тест {i} ---")
        result = parser.parse(code)
        print(f"Intent: {result.intent.value}")
        print(f"Quality: {result.quality_score:.2f}")
        print(f"Complexity: {result.complexity_score:.2f}")
        print(f"Suggestions: {len(result.suggestions)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Neural BSL Parser Training Pipeline"
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=10,
        help='Number of training epochs (default: 10)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=16,
        help='Batch size (default: 16)'
    )
    parser.add_argument(
        '--skip-dataset',
        action='store_true',
        help='Skip dataset preparation (use existing)'
    )
    parser.add_argument(
        '--dataset-dir',
        type=Path,
        default=Path('./data/neural_training'),
        help='Каталог с подготовленным dataset' 
    )
    return parser.parse_args()


async def main():
    """Main pipeline"""
    args = parse_args()

    print("=" * 70)
    print("🚀 NEURAL BSL PARSER - TRAINING PIPELINE")
    print("=" * 70)
    print(f"\nПараметры:")
    print(f"  Epochs: {args.epochs}")
    print(f"  Batch Size: {args.batch_size}")
    print("=" * 70)

    # Step 1: Dataset
    if not args.skip_dataset:
        dataset_dir = await prepare_dataset()
    else:
        dataset_dir = args.dataset_dir
        if not dataset_dir.exists():
            raise FileNotFoundError(f"Каталог с датасетом {dataset_dir} не найден")
        print(f"\n⏭️  Пропуск подготовки dataset, используем: {dataset_dir}")

    # Step 2: Training
    trainer = train_model(dataset_dir, args.epochs, args.batch_size)

    # Step 3: Testing
    test_model()

    print("\n" + "=" * 70)
    print("🎉 PIPELINE ЗАВЕРШЕН!")
    print("=" * 70)
    print("\n✅ Модель обучена и готова к использованию!")
    print(f"\n📁 Модель сохранена: ./models/neural_parser/")
    print(f"\nИспользование:")
    print(f"  from scripts.parsers.neural.neural_bsl_parser import NeuralBSLParser")
    print(f"  parser = NeuralBSLParser()")
    print(f"  result = parser.parse(code)")


if __name__ == "__main__":
    asyncio.run(main())





