# 🧠 Локальное обучение моделей (пошагово для новичков)

> Цель: развернуть локальные модели, подготовить данные 1С и выполнить обучение — без предположений и “вариантов”.

---

## 0. Что понадобится

| Что | Зачем | Как проверить |
| --- | --- | --- |
| 🚀 Репозиторий | Код и скрипты | `git clone https://github.com/DmitrL-dev/1cai-public` |
| 🐍 Python 3.11+ | Скрипты подготовки данных | `python --version` |
| 🐳 Docker + Docker Compose | Контейнеры с GPU/CPU моделями | `docker --version`, `docker compose version` |
| ☁️ Место на диске (30+ ГБ) | Данные + артефакты моделей | `Get-PSDrive -Name C` (PowerShell) |
| 📦 1C:EDT 2024.3+ | Экспорт конфигураций | Установить с сайта 1С |

> ⚠️ Если чего-то нет — устанавливаем перед переходом к следующему шагу.

---

## 1. Подготовка окружения

### 1.1 Клонируем репозиторий
```bash
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public
```

### 1.2 Создаём виртуальное окружение
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### 1.3 Ставим зависимости
```bash
pip install -r requirements.txt
pip install -r requirements-neural.txt
```

---

## 2. Выгрузка конфигураций 1С

> Требуется 1C:Enterprise Development Tools (EDT) 2024.3+.

1. Открываем EDT → `File → Import → 1C:Enterprise Configuration`.
2. Выбираем исходную конфигурацию (файл `.cf` или база).
3. **Обязательно** включаем выгрузку в формат `EDT Project` (структура `.xml`, `.bsl`).
4. Указываем путь выгрузки:
   ```
   <корень_репозитория>/1c_configurations/<код_конфигурации>/
   ```
   Примеры: `ERPCPM`, `ERP`, `ZUP`, `BUH`.

Проверяем:
```bash
dir 1c_configurations
```
Должны видеть подкаталоги с конфигурациями.

---

## 3. Подготовка данных для обучения

Все скрипты находятся в `scripts/`.

### 3.1 Парсим конфигурации
```bash
python scripts/1c_export/export_configuration_structure.py ^
  --input 1c_configurations/ERPCPM ^
  --output output/parsed/ERPCPM.json
```
*(На Linux/Mac заменить `^` на `\`.)*

Если конфигураций несколько — повторяем для каждой, меняя `ERPCPM`.

### 3.2 Собираем датасет BSL-кода
```bash
python scripts/dataset/create_ml_dataset.py ^
  --source 1c_configurations/ERPCPM ^
  --output output/dataset/ERPCPM_dataset.jsonl
```

Проверяем размер:
```bash
dir output/dataset
```

### 3.3 Генерируем синтетические пары “вопрос-ответ”
```bash
python scripts/dataset/create_qa_pairs.py ^
  --dataset output/dataset/ERPCPM_dataset.jsonl ^
  --output output/dataset/ERPCPM_qa.jsonl
```

> 🔁 Для нескольких конфигураций повторяем шаги 3.1–3.3.

---

## 4. Запуск инфраструктуры для обучения

### 4.1 Параметры окружения
Скопировать пример и заполнить:
```bash
copy env.example .env  # Windows
cp env.example .env    # Linux/Mac
```

Обязательно задать:
- `ML_DATASET_PATH` → путь к `.jsonl`,
- `MODEL_OUTPUT_DIR` → куда сохранять модели,
- `HF_TOKEN` → при использовании HuggingFace (опционально).

### 4.2 Запускаем Docker Compose
```bash
docker compose -f docker-compose.neural.yml up -d
```

Что поднимаем:
- `ml-worker` — основной контейнер обучения,
- `mlflow` — отслеживание экспериментов,
- `minio` (если в конфигурации) — хранилище артефактов.

Проверяем:
```bash
docker compose ps
```

---

## 5. Запуск обучения

### 5.1 Базовый запуск
```bash
docker compose exec ml-worker python train.py ^
  --dataset /data/ERPCPM_dataset.jsonl ^
  --epochs 3 ^
  --model qwen/Qwen2.5-7B-Instruct ^
  --output /models/ERPCPM-7B
```

Параметры:
- `--dataset` — путь внутри контейнера (`/data` уже подключен),
- `--model` — базовая модель,
- `--epochs` — кол-во эпох,
- `--output` — итоговая папка.

#### Быстрый демо-запуск
```bash
make train-ml-demo
make eval-ml-demo
```
`train-ml-demo` использует преднастройку `DEMO` из `config/ml_datasets.json`: создаёт модель `models/demo-model` и складывает отчёт в `reports/eval/demo-model.json`. `eval-ml-demo` прогоняет лёгкую проверку качества.

#### Конфигурации
- Список преднастроенных наборов: `python scripts/ml/config_utils.py --list`
- Подробности по набору: `python scripts/ml/config_utils.py --info ERPCPM`
- Запуск полного цикла через Make:
  ```bash
  make train-ml CONFIG=ERPCPM EPOCHS=3
  make eval-ml CONFIG=ERPCPM LIMIT=20
  ```

### 5.2 Мониторим процесс
- Логи обучения: `docker compose logs -f ml-worker`.
- MLflow UI: http://localhost:5000 (если включен в `docker-compose.neural.yml`).

---

## 6. Валидация результата

### 6.1 Сохраняем модель наружу
```bash
docker compose cp ml-worker:/models/ERPCPM-7B ./models/ERPCPM-7B
```

### 6.2 Локальный smoke-тест
```bash
python scripts/eval/eval_model.py ^
  --model ./models/ERPCPM-7B ^
  --questions output/dataset/ERPCPM_qa.jsonl ^
  --limit 10
```

Альтернатива (используем конфигурацию и автоматически сохраняем отчёт):
```bash
make eval-ml CONFIG=ERPCPM LIMIT=10
```

### 6.3 Проверяем качество
- Если `eval_model.py` показывает точность < 0.6 → увеличиваем_epochs, дорабатываем датасет.
- Такие отчёты сохраняются в `output/eval`.

---

## 7. Частые вопросы

### ❓ “Нет GPU, можно CPU?”
Можно, но очень медленно. В `docker-compose.neural.yml` есть сервис `ml-worker-cpu`. Меняем команду на `docker compose -f docker-compose.neural.yml up ml-worker-cpu`.

### ❓ “Где взять пример конфигурации?”
В каталоге `examples/configurations` лежит минимальный `DemoConfig`. Его можно использовать для тренировки процесса.

### ❓ “Как остановить всё?”
```bash
docker compose -f docker-compose.neural.yml down
```
Артефакты остаются в `./models` и `./output`.

### ❓ “Что делать с ошибками Docker?”
- Убедитесь, что сервисы не заняты (`docker ps`).
- Прочитать логи: `docker compose logs ml-worker`.
- Проверить `docker info` — достаточно ли ресурсов.

---

## 8. Итоговая шпаргалка команд

```bash
# 1. Подготовка
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-neural.txt

# 2. Выгрузить конфигурации в 1c_configurations/<NAME>
# (через 1C:EDT, см. шаг 2)

# 3. Парсинг и датасет
python scripts/1c_export/export_configuration_structure.py --input 1c_configurations/ERPCPM --output output/parsed/ERPCPM.json
python scripts/dataset/create_ml_dataset.py --source 1c_configurations/ERPCPM --output output/dataset/ERPCPM_dataset.jsonl
python scripts/dataset/create_qa_pairs.py --dataset output/dataset/ERPCPM_dataset.jsonl --output output/dataset/ERPCPM_qa.jsonl

# 4. Docker окружение
cp env.example .env
docker compose -f docker-compose.neural.yml up -d

# 5. Обучение
docker compose exec ml-worker python train.py --dataset /data/ERPCPM_dataset.jsonl --epochs 3 --model qwen/Qwen2.5-7B-Instruct --output /models/ERPCPM-7B

# Быстрый demo-режим
make train-ml-demo
make eval-ml-demo

# 6. Копия модели и проверка
docker compose cp ml-worker:/models/ERPCPM-7B ./models/ERPCPM-7B
python scripts/eval/eval_model.py --model ./models/ERPCPM-7B --questions output/dataset/ERPCPM_qa.jsonl --limit 10
```

---

## 9. Что дальше?

- Добавить собственные конфигурации → повторяем шаги 3–6.
- Настроить автоматическое расписание обучения → смотрим `docs/06-features/ML_DATASET_GENERATOR_GUIDE.md`.
- Поделиться результатами → коммитим в `models/` (если открытая модель) + загружаем в MLflow.

Готово! Теперь у новичка есть точный чек-лист, как запустить локальное обучение без лишних вопросов. Если что-то непонятно — заводим issue или стучимся к ML-команде. Удачи! 🚀

