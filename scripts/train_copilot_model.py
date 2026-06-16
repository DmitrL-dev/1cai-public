
#!/usr/bin/env python3
"""
Train Copilot LoRA Model
Complete training pipeline for 1C BSL code generation

Best Practice: Fine-tune Qwen2.5-Coder on 1C BSL dataset
"""

import logging
from pathlib import Path

import torch
from datasets import load_dataset
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer,
                          DataCollatorForLanguageModeling, Trainer,
                          TrainingArguments)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def train_copilot_model():
    """
    Complete training pipeline for 1C Copilot
    
    Steps:
    1. Load base model (Qwen2.5-Coder-7B)
    2. Prepare BSL dataset
    3. Configure LoRA
    4. Train model
    5. Save adapter
    6. Evaluate
    """
    
    logger.info("🚀 Starting Copilot model training...")
    
    # Configuration
    base_model_name = "Qwen/Qwen2.5-Coder-7B-Instruct"
    dataset_path = "./data/bsl_code_dataset"
    output_dir = "./models/1c-copilot-lora"
    
    # Check GPU availability
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    if device == "cpu":
        logger.warning("⚠️  Training on CPU will be VERY slow! GPU recommended.")
    
    # Step 1: Load base model
    logger.info(f"📥 Loading base model: {base_model_name}")
    
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        device_map="auto",
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        trust_remote_code=True
    )
    
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_name,
        trust_remote_code=True
    )
    
    # Set pad token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    logger.info("✅ Base model loaded")
    
    # Step 2: Load BSL dataset
    logger.info(f"📚 Loading BSL dataset from {dataset_path}")
    
    if not Path(dataset_path).exists():
        logger.error(f"❌ Dataset not found at {dataset_path}")
        logger.info("Run: python src/ai/copilot/bsl_dataset_preparer.py")
        return
    
    dataset = load_dataset('json', data_files={
        'train': f"{dataset_path}/train.jsonl",
        'validation': f"{dataset_path}/validation.jsonl"
    })
    
    logger.info(f"✅ Dataset loaded: {len(dataset['train'])} train, {len(dataset['validation'])} val")
    
    # Step 3: Configure LoRA
    logger.info("⚙️  Configuring LoRA adapter...")
    
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,  # LoRA rank
        lora_alpha=32,  # LoRA alpha
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],  # Qwen2.5 specific
        bias="none"
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    logger.info("✅ LoRA configured")
    
    # Step 4: Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=3,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=device == "cuda",
        logging_steps=10,
        save_steps=100,
        eval_steps=100,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        warmup_steps=100,
        weight_decay=0.01,
        report_to="tensorboard"
    )
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        data_collator=data_collator
    )
    
    # Step 5: Train!
    logger.info("🔥 Starting training...")
    logger.info("This will take several hours depending on GPU/CPU")
    
    trainer.train()
    
    logger.info("✅ Training complete!")
    
    # Step 6: Save model
    logger.info(f"💾 Saving model to {output_dir}")
    
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    logger.info("✅ Model saved!")
    
    # Step 7: Evaluate
    logger.info("📊 Evaluating model...")
    
    eval_results = trainer.evaluate()
    
    logger.info(f"Evaluation results: {eval_results}")
    
    # Step 8: Test generation
    logger.info("🧪 Testing code generation...")
    
    test_prompts = [
        "Функция ПолучитьДанныеКлиента",
        "Процедура ОбработатьДокумент",
        "Для Каждого Элемент Из Коллекция Цикл"
    ]
    
    for prompt in test_prompts:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        
        outputs = model.generate(
            inputs.input_ids,
            max_new_tokens=100,
            temperature=0.3,
            do_sample=True
        )
        
        generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.info(f"\nPrompt: {prompt}")
        logger.info(f"Generated: {generated}\n")
    
    logger.info("🎉 Training pipeline complete!")
    logger.info(f"Model ready at: {output_dir}")
    logger.info("Set env: export COPILOT_MODEL_PATH={output_dir}")
    logger.info("Restart API to use trained model!")


if __name__ == "__main__":
    train_copilot_model()


