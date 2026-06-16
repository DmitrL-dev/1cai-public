
#!/usr/bin/env python3
"""
Fine-tune Qwen-Coder on SmolTalk Dataset
Улучшение качества русского языка и диалогов
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          DataCollatorForLanguageModeling, Trainer,
                          TrainingArguments)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QwenFineTuner:
    """Fine-tuner для Qwen-Coder на SmolTalk"""
    
    def __init__(
        self,
        base_model: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
        output_dir: str = "./models/qwen-coder-smoltalk-ru",
        use_4bit: bool = True,
    ):
        """
        Инициализация fine-tuner
        
        Args:
            base_model: Базовая модель Qwen
            output_dir: Директория для сохранения модели
            use_4bit: Использовать 4-bit quantization (для экономии памяти)
        """
        self.base_model_name = base_model
        self.output_dir = output_dir
        self.use_4bit = use_4bit
        
        self.model = None
        self.tokenizer = None
        self.dataset = None
        
        logger.info(f"Initializing QwenFineTuner")
        logger.info(f"  Base model: {base_model}")
        logger.info(f"  Output dir: {output_dir}")
        logger.info(f"  4-bit quantization: {use_4bit}")
    
    def load_base_model(self):
        """Загрузка базовой модели Qwen"""
        logger.info("Loading base model...")
        
        # Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.base_model_name,
            trust_remote_code=True
        )
        
        # Устанавливаем pad_token если его нет
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Model с quantization (если включен)
        if self.use_4bit:
            from transformers import BitsAndBytesConfig
            
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
            
            # Prepare for training
            self.model = prepare_model_for_kbit_training(self.model)
            
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model_name,
                device_map="auto",
                torch_dtype=torch.float16,
                trust_remote_code=True
            )
        
        logger.info("✓ Base model loaded")
        logger.info(f"  Model size: {self.model.num_parameters() / 1e9:.2f}B parameters")
    
    def apply_lora(
        self,
        r: int = 16,
        lora_alpha: int = 32,
        target_modules: Optional[list] = None,
        lora_dropout: float = 0.05,
    ):
        """
        Применение LoRA адаптера
        
        Args:
            r: Ранг LoRA матриц
            lora_alpha: LoRA alpha parameter
            target_modules: Модули для применения LoRA
            lora_dropout: Dropout для LoRA layers
        """
        logger.info("Applying LoRA adapter...")
        
        if target_modules is None:
            # Default для Qwen
            target_modules = [
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ]
        
        lora_config = LoraConfig(
            r=r,
            lora_alpha=lora_alpha,
            target_modules=target_modules,
            lora_dropout=lora_dropout,
            bias="none",
            task_type="CAUSAL_LM",
        )
        
        self.model = get_peft_model(self.model, lora_config)
        
        # Печатаем trainable parameters
        trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        total_params = sum(p.numel() for p in self.model.parameters())
        
        logger.info("✓ LoRA applied")
        logger.info(f"  Trainable params: {trainable_params / 1e6:.2f}M")
        logger.info(f"  Total params: {total_params / 1e6:.2f}M")
        logger.info(f"  Trainable %: {100 * trainable_params / total_params:.2f}%")
    
    def load_smoltalk_dataset(
        self,
        language: str = "ru",
        max_samples: Optional[int] = None,
        train_split: float = 0.95
    ):
        """
        Загрузка SmolTalk датасета
        
        Args:
            language: Язык для фильтрации (ru, en, etc.)
            max_samples: Максимальное количество примеров (для быстрого теста)
            train_split: Процент для train split
        """
        logger.info("Loading SmolTalk dataset...")
        logger.info(f"  Language filter: {language}")
        
        # Загрузка датасета
        dataset = load_dataset("HuggingFaceFW/smoltalk")
        
        logger.info(f"  Total samples: {len(dataset['train'])}")
        
        # Фильтруем по языку (если указан)
        if language:
            dataset = dataset.filter(
                lambda x: x.get('language', '').lower() == language.lower()
            )
            logger.info(f"  After language filter: {len(dataset['train'])} samples")
        
        # Ограничиваем количество (если указано)
        if max_samples:
            dataset['train'] = dataset['train'].select(range(min(max_samples, len(dataset['train']))))
            logger.info(f"  Limited to: {len(dataset['train'])} samples")
        
        # Разбиваем на train/val
        dataset = dataset['train'].train_test_split(test_size=1-train_split)
        
        # Преобразуем в формат для обучения
        def format_example(example):
            """Форматирование примера для обучения"""
            # SmolTalk содержит диалоги в формате messages
            messages = example.get('messages', [])
            
            # Формируем текст из сообщений
            if messages:
                # Применяем chat template токенизатора
                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=False
                )
            else:
                # Fallback: используем просто text поле
                text = example.get('text', '')
            
            return {"text": text}
        
        dataset = dataset.map(format_example)
        
        logger.info("✓ SmolTalk dataset loaded")
        logger.info(f"  Train samples: {len(dataset['train'])}")
        logger.info(f"  Val samples: {len(dataset['test'])}")
        
        self.dataset = dataset
        return dataset
    
    def tokenize_dataset(self, max_length: int = 2048):
        """
        Токенизация датасета
        
        Args:
            max_length: Максимальная длина последовательности
        """
        logger.info("Tokenizing dataset...")
        
        def tokenize_function(examples):
            return self.tokenizer(
                examples["text"],
                truncation=True,
                max_length=max_length,
                padding="max_length",
                return_tensors="pt"
            )
        
        self.dataset = self.dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=self.dataset['train'].column_names
        )
        
        logger.info("✓ Dataset tokenized")
    
    def train(
        self,
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 2e-4,
        gradient_accumulation_steps: int = 4,
        warmup_steps: int = 100,
        save_steps: int = 500,
        logging_steps: int = 50,
    ):
        """
        Обучение модели
        
        Args:
            num_epochs: Количество эпох
            batch_size: Размер батча
            learning_rate: Learning rate
            gradient_accumulation_steps: Gradient accumulation
            warmup_steps: Warmup steps
            save_steps: Шаги для сохранения checkpoint
            logging_steps: Шаги для логирования
        """
        logger.info("Starting training...")
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=self.output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            learning_rate=learning_rate,
            warmup_steps=warmup_steps,
            logging_steps=logging_steps,
            save_steps=save_steps,
            evaluation_strategy="steps",
            eval_steps=save_steps,
            save_total_limit=3,
            fp16=torch.cuda.is_available(),
            gradient_checkpointing=True,
            optim="paged_adamw_8bit" if self.use_4bit else "adamw_torch",
            report_to=["tensorboard"],
            logging_dir=f"{self.output_dir}/logs",
        )
        
        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,
        )
        
        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=self.dataset['train'],
            eval_dataset=self.dataset['test'],
            data_collator=data_collator,
        )
        
        # Train!
        logger.info("🚀 Training started...")
        trainer.train()
        
        logger.info("✓ Training completed!")
        
        # Сохранение финальной модели
        self.save_model()
    
    def save_model(self):
        """Сохранение обученной модели"""
        logger.info(f"Saving model to {self.output_dir}...")
        
        # Сохраняем модель
        self.model.save_pretrained(self.output_dir)
        self.tokenizer.save_pretrained(self.output_dir)
        
        # Сохраняем конфигурацию
        config = {
            "base_model": self.base_model_name,
            "dataset": "HuggingFaceFW/smoltalk",
            "language": "ru",
            "timestamp": str(Path.ctime(Path(self.output_dir))),
        }
        
        config_path = Path(self.output_dir) / "training_config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info("✓ Model saved")
        logger.info(f"  Location: {self.output_dir}")


def main():
    """Главная функция"""
    
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║  Qwen-Coder Fine-tuning on SmolTalk Dataset              ║
    ║  Улучшение качества русского языка                        ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Параметры
    BASE_MODEL = os.getenv("BASE_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
    OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./models/qwen-coder-smoltalk-ru")
    USE_4BIT = os.getenv("USE_4BIT", "true").lower() == "true"
    NUM_EPOCHS = int(os.getenv("NUM_EPOCHS", "3"))
    MAX_SAMPLES = os.getenv("MAX_SAMPLES", None)
    MAX_SAMPLES = int(MAX_SAMPLES) if MAX_SAMPLES else None
    
    logger.info("Configuration:")
    logger.info(f"  BASE_MODEL: {BASE_MODEL}")
    logger.info(f"  OUTPUT_DIR: {OUTPUT_DIR}")
    logger.info(f"  USE_4BIT: {USE_4BIT}")
    logger.info(f"  NUM_EPOCHS: {NUM_EPOCHS}")
    logger.info(f"  MAX_SAMPLES: {MAX_SAMPLES or 'All'}")
    
    # Инициализация
    finetuner = QwenFineTuner(
        base_model=BASE_MODEL,
        output_dir=OUTPUT_DIR,
        use_4bit=USE_4BIT
    )
    
    # Этап 1: Загрузка модели
    finetuner.load_base_model()
    
    # Этап 2: Применение LoRA
    finetuner.apply_lora(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05
    )
    
    # Этап 3: Загрузка датасета
    finetuner.load_smoltalk_dataset(
        language="ru",
        max_samples=MAX_SAMPLES,
        train_split=0.95
    )
    
    # Этап 4: Токенизация
    finetuner.tokenize_dataset(max_length=2048)
    
    # Этап 5: Обучение
    finetuner.train(
        num_epochs=NUM_EPOCHS,
        batch_size=4,
        learning_rate=2e-4,
        gradient_accumulation_steps=4,
        warmup_steps=100,
        save_steps=500,
        logging_steps=50
    )
    
    print("\n" + "="*60)
    print("✅ FINE-TUNING ЗАВЕРШЕН!")
    print("="*60)
    print(f"Модель сохранена в: {OUTPUT_DIR}")
    print("\nТеперь можно использовать обученную модель:")
    print(f"  export COPILOT_MODEL_PATH={OUTPUT_DIR}")
    print(f"  python src/api/copilot_api_perfect.py")
    print("="*60)


if __name__ == "__main__":
    main()





