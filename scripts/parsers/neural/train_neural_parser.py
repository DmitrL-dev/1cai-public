
#!/usr/bin/env python3
"""
Обучение Neural BSL Parser
Собственная инновационная технология

Обучаем модель на:
- 50,000+ примеров BSL кода
- Intent labels
- Quality scores
- Best practices

Версия: 1.0.0
"""

import json
from pathlib import Path
from typing import Dict, List

import torch
import torch.nn as nn
import torch.optim as optim
from neural_bsl_parser import (BSLTokenizer, CodeIntent,
                               CodeTransformerEncoder, IntentClassifier,
                               QualityScorer)
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm


class BSLCodeDataset(Dataset):
    """
    Dataset для обучения Neural Parser
    
    Структура данных:
    {
        'code': "Функция ...",
        'intent': "data_retrieval",
        'quality': 0.85,
        'complexity': 0.3,
        'suggestions': [...]
    }
    """
    
    def __init__(self, data_path: str, tokenizer: BSLTokenizer):
        self.tokenizer = tokenizer
        self.data = self._load_data(data_path)
    
    def _load_data(self, data_path: str) -> List[Dict]:
        """Загрузка dataset"""
        data_file = Path(data_path)
        
        if not data_file.exists():
            print(f"[WARN] Dataset not found: {data_path}")
            print("[INFO] Creating sample dataset...")
            return self._create_sample_dataset()
        
        with open(data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _create_sample_dataset(self) -> List[Dict]:
        """Создание примера dataset для тестирования"""
        return [
            {
                'code': 'Функция ПолучитьДанные() Запрос = Новый Запрос; Возврат Запрос.Выполнить(); КонецФункции',
                'intent': 'data_retrieval',
                'quality': 0.7,
                'complexity': 0.3,
                'maintainability': 0.8
            },
            {
                'code': 'Процедура СоздатьДокумент() Документ = Документы.Создать(); Документ.Записать(); КонецПроцедуры',
                'intent': 'data_creation',
                'quality': 0.6,
                'complexity': 0.2,
                'maintainability': 0.7
            },
            # TODO: Load actual 50k+ examples from PostgreSQL
        ]
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        item = self.data[idx]
        
        # Токенизация
        tokens = self.tokenizer.encode(item['code'])
        
        # Intent label
        intent_label = list(CodeIntent).index(
            CodeIntent(item['intent'])
        )
        
        # Quality scores
        quality = item.get('quality', 0.5)
        complexity = item.get('complexity', 0.5)
        maintainability = item.get('maintainability', 0.5)
        
        return {
            'tokens': tokens,
            'intent_label': torch.tensor(intent_label, dtype=torch.long),
            'quality': torch.tensor(quality, dtype=torch.float32),
            'complexity': torch.tensor(complexity, dtype=torch.float32),
            'maintainability': torch.tensor(maintainability, dtype=torch.float32)
        }


def collate_fn(batch):
    """Custom collate function для DataLoader"""
    # Padding токенов
    max_len = max(item['tokens'].shape[0] for item in batch)
    
    padded_tokens = []
    for item in batch:
        tokens = item['tokens']
        pad_len = max_len - tokens.shape[0]
        padded = torch.cat([
            tokens,
            torch.zeros(pad_len, dtype=torch.long)
        ])
        padded_tokens.append(padded)
    
    return {
        'tokens': torch.stack(padded_tokens),
        'intent_label': torch.stack([item['intent_label'] for item in batch]),
        'quality': torch.stack([item['quality'] for item in batch]),
        'complexity': torch.stack([item['complexity'] for item in batch]),
        'maintainability': torch.stack([item['maintainability'] for item in batch])
    }


class NeuralParserTrainer:
    """
    Trainer для Neural BSL Parser
    
    Multi-task learning:
    - Intent classification
    - Quality prediction
    - Complexity prediction
    - Maintainability prediction
    """
    
    def __init__(
        self,
        model_params: Dict = None,
        learning_rate: float = 1e-4,
        batch_size: int = 32,
        device: str = None
    ):
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"[INFO] Using device: {self.device}")
        
        # Model components
        self.tokenizer = BSLTokenizer()
        
        params = model_params or {}
        self.encoder = CodeTransformerEncoder(**params).to(self.device)
        self.intent_classifier = IntentClassifier().to(self.device)
        self.quality_scorer = QualityScorer().to(self.device)
        
        # Optimizer
        self.optimizer = optim.AdamW([
            {'params': self.encoder.parameters()},
            {'params': self.intent_classifier.parameters()},
            {'params': self.quality_scorer.parameters()}
        ], lr=learning_rate)
        
        # Loss functions
        self.intent_criterion = nn.CrossEntropyLoss()
        self.quality_criterion = nn.MSELoss()
        
        # Batch size
        self.batch_size = batch_size
        
        # Training history
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'intent_acc': [],
            'quality_mae': []
        }
    
    def train(
        self,
        train_dataset: BSLCodeDataset,
        val_dataset: BSLCodeDataset = None,
        num_epochs: int = 10,
        save_path: str = './models/neural_parser'
    ):
        """
        Обучение модели
        
        Args:
            train_dataset: Обучающий dataset
            val_dataset: Валидационный dataset
            num_epochs: Количество эпох
            save_path: Путь для сохранения модели
        """
        print("=" * 70)
        print("ОБУЧЕНИЕ NEURAL BSL PARSER")
        print("=" * 70)
        
        # DataLoaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            collate_fn=collate_fn
        )
        
        val_loader = None
        if val_dataset:
            val_loader = DataLoader(
                val_dataset,
                batch_size=self.batch_size,
                shuffle=False,
                collate_fn=collate_fn
            )
        
        # Training loop
        for epoch in range(num_epochs):
            print(f"\nEpoch {epoch + 1}/{num_epochs}")
            print("-" * 70)
            
            # Train
            train_metrics = self._train_epoch(train_loader)
            
            print(f"Train Loss: {train_metrics['loss']:.4f} | "
                  f"Intent Acc: {train_metrics['intent_acc']:.2%} | "
                  f"Quality MAE: {train_metrics['quality_mae']:.4f}")
            
            # Validation
            if val_loader:
                val_metrics = self._validate(val_loader)
                
                print(f"Val Loss: {val_metrics['loss']:.4f} | "
                      f"Intent Acc: {val_metrics['intent_acc']:.2%} | "
                      f"Quality MAE: {val_metrics['quality_mae']:.4f}")
                
                # Save history
                self.history['val_loss'].append(val_metrics['loss'])
            
            self.history['train_loss'].append(train_metrics['loss'])
            self.history['intent_acc'].append(train_metrics['intent_acc'])
            self.history['quality_mae'].append(train_metrics['quality_mae'])
        
        # Save model
        self._save_model(save_path)
        
        print("\n" + "=" * 70)
        print("✅ Обучение завершено!")
        print(f"💾 Модель сохранена: {save_path}")
        print("=" * 70)
    
    def _train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Обучение одной эпохи"""
        self.encoder.train()
        self.intent_classifier.train()
        self.quality_scorer.train()
        
        total_loss = 0.0
        correct_intents = 0
        total_samples = 0
        quality_errors = []
        
        progress_bar = tqdm(train_loader, desc="Training")
        
        for batch in progress_bar:
            # Move to device
            tokens = batch['tokens'].to(self.device)
            intent_labels = batch['intent_label'].to(self.device)
            quality_labels = batch['quality'].to(self.device)
            complexity_labels = batch['complexity'].to(self.device)
            maintainability_labels = batch['maintainability'].to(self.device)
            
            # Forward pass
            encoded = self.encoder(tokens)
            
            # Intent classification
            intent_logits = self.intent_classifier(encoded)
            intent_loss = self.intent_criterion(intent_logits, intent_labels)
            
            # Quality prediction
            quality_scores = self.quality_scorer(encoded)
            quality_loss = self.quality_criterion(
                quality_scores['quality'].squeeze(),
                quality_labels
            )
            complexity_loss = self.quality_criterion(
                quality_scores['complexity'].squeeze(),
                complexity_labels
            )
            maintainability_loss = self.quality_criterion(
                quality_scores['maintainability'].squeeze(),
                maintainability_labels
            )
            
            # Total loss (multi-task)
            loss = intent_loss + quality_loss + complexity_loss + maintainability_loss
            
            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.encoder.parameters(), 1.0)
            self.optimizer.step()
            
            # Metrics
            total_loss += loss.item()
            
            intent_preds = intent_logits.argmax(dim=-1)
            correct_intents += (intent_preds == intent_labels).sum().item()
            total_samples += tokens.size(0)
            
            quality_error = torch.abs(
                quality_scores['quality'].squeeze() - quality_labels
            ).mean().item()
            quality_errors.append(quality_error)
            
            # Update progress bar
            progress_bar.set_postfix({
                'loss': loss.item(),
                'intent_acc': correct_intents / total_samples
            })
        
        return {
            'loss': total_loss / len(train_loader),
            'intent_acc': correct_intents / total_samples,
            'quality_mae': sum(quality_errors) / len(quality_errors)
        }
    
    def _validate(self, val_loader: DataLoader) -> Dict[str, float]:
        """Валидация модели"""
        self.encoder.eval()
        self.intent_classifier.eval()
        self.quality_scorer.eval()
        
        total_loss = 0.0
        correct_intents = 0
        total_samples = 0
        quality_errors = []
        
        with torch.no_grad():
            for batch in val_loader:
                tokens = batch['tokens'].to(self.device)
                intent_labels = batch['intent_label'].to(self.device)
                quality_labels = batch['quality'].to(self.device)
                
                # Forward pass
                encoded = self.encoder(tokens)
                intent_logits = self.intent_classifier(encoded)
                quality_scores = self.quality_scorer(encoded)
                
                # Loss
                intent_loss = self.intent_criterion(intent_logits, intent_labels)
                quality_loss = self.quality_criterion(
                    quality_scores['quality'].squeeze(),
                    quality_labels
                )
                loss = intent_loss + quality_loss
                
                total_loss += loss.item()
                
                # Metrics
                intent_preds = intent_logits.argmax(dim=-1)
                correct_intents += (intent_preds == intent_labels).sum().item()
                total_samples += tokens.size(0)
                
                quality_error = torch.abs(
                    quality_scores['quality'].squeeze() - quality_labels
                ).mean().item()
                quality_errors.append(quality_error)
        
        return {
            'loss': total_loss / len(val_loader),
            'intent_acc': correct_intents / total_samples,
            'quality_mae': sum(quality_errors) / len(quality_errors)
        }
    
    def _save_model(self, save_path: str):
        """Сохранение модели"""
        save_dir = Path(save_path)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save components
        torch.save(self.encoder.state_dict(), save_dir / 'encoder.pt')
        torch.save(self.intent_classifier.state_dict(), save_dir / 'intent_classifier.pt')
        torch.save(self.quality_scorer.state_dict(), save_dir / 'quality_scorer.pt')
        
        # Save training history
        with open(save_dir / 'history.json', 'w') as f:
            json.dump(self.history, f, indent=2)
        
        print(f"[INFO] Model saved to {save_dir}")


def main():
    """Main training script"""
    
    # Создаем trainer
    trainer = NeuralParserTrainer(
        learning_rate=1e-4,
        batch_size=16
    )
    
    # Загружаем datasets
    # TODO: Load from actual PostgreSQL with 50k+ examples
    train_dataset = BSLCodeDataset(
        data_path='./data/bsl_train.json',
        tokenizer=trainer.tokenizer
    )
    
    val_dataset = BSLCodeDataset(
        data_path='./data/bsl_val.json',
        tokenizer=trainer.tokenizer
    )
    
    # Обучаем
    trainer.train(
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        num_epochs=10,
        save_path='./models/neural_parser'
    )


if __name__ == "__main__":
    main()




