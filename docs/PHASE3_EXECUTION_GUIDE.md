# Phase 3: Руководство по Выполнению

## Быстрый Старт

Этот документ содержит пошаговые инструкции для выполнения Phase 3: Аудит Документации.

---

## Шаг 1: Генерация Docstrings

### Тестовый Запуск (Dry Run)

Сначала запустите в режиме dry-run чтобы увидеть что будет изменено:

```powershell
python scripts/quality/docstring_generator.py src/ --dry-run
```

### Генерация для Приоритетных Файлов

Топ-10 файлов с наибольшим количеством проблем:

```powershell
# 1. marketplace/api/routes.py (25 docstrings)
python scripts/quality/docstring_generator.py src/modules/marketplace/api/ --pattern "routes.py"

# 2. ai_assistants/base_assistant.py (24 docstrings)
python scripts/quality/docstring_generator.py src/ai_assistants/ --pattern "base_assistant.py"

# 3. infrastructure/repositories/marketplace.py (21 docstrings)
python scripts/quality/docstring_generator.py src/infrastructure/repositories/ --pattern "marketplace.py"
```

### Генерация для Всех Файлов

После проверки результатов на приоритетных файлах:

```powershell
python scripts/quality/docstring_generator.py src/
```

**Важно:** Автоматически сгенерированные docstrings содержат TODO. Их нужно будет улучшить вручную.

---

## Шаг 2: Проверка Broken Links

### Запуск Проверки

```powershell
python scripts/quality/link_checker.py --dir .
```

### Анализ Результатов

Проверьте файл `broken_links_report.json`:

```powershell
# Посмотреть количество broken links
python -c "import json; r = json.load(open('broken_links_report.json')); print(f\"Broken links: {r['summary']['broken_links']}\")"

# Посмотреть первые 10
python -c "import json; r = json.load(open('broken_links_report.json')); [print(f\"{l['file']}: {l['link_url']}\") for l in r['broken_links'][:10]]"
```

### Исправление Broken Links

Откройте файлы из отчёта и исправьте ссылки вручную.

---

## Шаг 3: Проверка Coverage

### Запуск Анализа

```powershell
python scripts/quality/phase3_doc_analyzer.py
```

### Целевые Метрики

| Метрика | Текущее | Цель |
|---------|---------|------|
| Docstring Coverage | 14% | 90% |
| Broken Links | ? | 0 |

---

## Шаг 4: Ручное Улучшение

### Приоритет 1: Security Модуль

```powershell
# Откройте файлы в редакторе
code src/security/auth.py
```

Улучшите автоматически сгенерированные docstrings:
- Замените TODO на реальные описания
- Добавьте примеры использования
- Опишите параметры детально

### Приоритет 2: AI Модуль

```powershell
code src/ai/strategies/llm_providers.py
```

### Приоритет 3: API Модуль

```powershell
code src/api/dependencies.py
```

---

## Шаг 5: Верификация

### Проверка Docstrings

```powershell
# Повторный анализ
python scripts/quality/phase3_doc_analyzer.py

# Сравнение с предыдущим результатом
python -c "import json; old = json.load(open('phase3_documentation_analysis.json')); print(f\"Было: {old['missing_docstrings']['total']}, Стало: ???\")"
```

### Проверка Links

```powershell
python scripts/quality/link_checker.py --dir .
```

---

## Шаг 6: Коммит Изменений

### Проверка Изменений

```powershell
git status
git diff --stat
```

### Коммит

```powershell
git add .
git commit -m "docs: Phase 3 - добавлены docstrings и исправлены broken links"
```

---

## Полезные Команды

### Поиск Файлов без Docstrings

```powershell
# Найти все файлы с TODO в docstrings
rg "TODO: Добавить" --type py
```

### Статистика по Модулям

```powershell
# Подсчёт docstrings по модулям
python -c "import json; r = json.load(open('phase3_documentation_analysis.json')); modules = {}; [modules.update({f['file'].split('/')[1]: modules.get(f['file'].split('/')[1], 0) + f['issues']['total']}) for f in r['files_with_issues']]; [print(f\"{k}: {v}\") for k, v in sorted(modules.items(), key=lambda x: x[1], reverse=True)[:10]]"
```

---

## Troubleshooting

### Ошибка: "invalid syntax"

Некоторые файлы могут иметь синтаксические ошибки (например, orchestration.py, bsl_grammar_rules.py). Они уже исключены в `.pylintrc`.

### Ошибка: "encoding"

Убедитесь что все файлы в UTF-8:

```powershell
# Конвертация файла в UTF-8
Get-Content file.py | Set-Content -Encoding UTF8 file.py
```

---

## Следующие Шаги

После завершения Phase 3:

1. ✅ Создать финальный отчёт
2. ✅ Обновить метрики в task.md
3. ✅ Закоммитить все изменения
4. 🚀 Перейти к Phase 4: Architecture Review

---

**Удачи!** 🎯
