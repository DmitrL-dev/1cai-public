# ❓ Часто задаваемые вопросы (FAQ)

## Установка и запуск

**Q:** Docker не стартует / контейнеры падают сразу после `docker-compose up`.  
**A:** Проверьте, что Docker выделено не менее 6 CPU и 16 GB RAM. Очистите старые контейнеры:  
```bash
docker ps -aq | % { docker rm -f $_ }
docker volume prune -f
docker-compose up -d
```

**Q:** Нет GPU — можно ли запускать ML worker?  
**A:** Да, используйте сервис `ml-worker-cpu` в `docker-compose.neural.yml`, но обучение займёт больше времени. Для продакшн-релизов рекомендуется GPU.

**Q:** Команда `python run_full_audit.py` падает из-за кодировки.  
**A:** На Windows запустите с `PYTHONIOENCODING=utf-8`:  
```powershell
$env:PYTHONIOENCODING="utf-8"
python run_full_audit.py --stop-on-failure
```

## Работа с конфигурациями 1С

**Q:** Где взять примеры конфигураций для проверки?  
**A:** Минимальные демо-файлы в `examples/configurations`. Для реальных проектов экспортируйте свою конфигурацию из 1C:EDT в `1c_configurations/<NAME>/`.

**Q:** Парсер не видит новые модули после экспорта.  
**A:** Убедитесь, что экспортируете в формат EDT (XML/BSL), не `.cf`. Затем выполните `python scripts/parsers/parse_edt_xml.py --force`.

## EDT-плагин

**Q:** Быстрый анализ показывает заглушки по зависимостям.  
**A:** Проверьте соединение с Neo4j и MCP. Если аналитика выключена, смотрите `docs/05-development/README.md` — раздел оркестратора.

**Q:** Вызов оркестратора падает на Windows.  
**A:** Проверьте наличие PowerShell‑скрипта `scripts/orchestrate_edt_analysis.ps1` и выполните команду от имени администратора.

## ML и обучение

**Q:** Где хранятся датасеты и модели?  
**A:** По умолчанию в `output/dataset/` и `models/`. Путь можно задать переменными `ML_DATASET_PATH`, `MODEL_OUTPUT_DIR` в `.env`.

**Q:** Как оценить качество модели после обучения?  
**A:** Запустите `python scripts/eval/eval_model.py --model ./models/<NAME> --questions output/dataset/<NAME>_qa.jsonl --limit 20`.

## BSL & AST tooling

**Q:** `make bsl-ls-up` ничего не делает на Windows — нет `make`.  
**A:** Используйте PowerShell скрипт `scripts/windows/bsl-ls-up.ps1` или команду `docker-compose -f docker-compose.dev.yml up -d bsl-language-server`. Аналогично для проверки — `scripts/windows/bsl-ls-check.ps1`.

**Q:** `check_bsl_language_server.py` сообщает `LSP недоступен`.  
**A:** Убедитесь, что контейнер `bsl-language-server` запущен и порт 8081 не занят. Проверьте health: `curl http://localhost:8081/actuator/health`. Если работает в Docker Desktop на Windows, включите TCP-переадресацию.

## MCP / AI инструменты

**Q:** EDT плагин пишет “Connection failed”.  
**A:** Проверьте, что оба сервиса запущены: `python -m uvicorn src.main:app --port 8080` и `python -m src.ai.mcp_server --port 6001` (или `make servers`). После изменения `.env` перезапустите.

**Q:** MCP-инструмент `bsl_platform_context` возвращает `configured=false`.  
**A:** Не настроены переменные `MCP_BSL_CONTEXT_BASE_URL` и `MCP_BSL_CONTEXT_TOOL_NAME`. Запустите внешний сервис [alkoleft/mcp-bsl-platform-context](https://github.com/alkoleft/mcp-bsl-platform-context) и пропишите URL в `.env`.

## CI / публикация

**Q:** PR падает на задаче `spec-driven-validation`.  
**A:** Один из файлов `docs/research/features/<slug>/plan|spec|tasks|research.md` содержит `{{FEATURE_TITLE}}`, `{{DATE}}`, `{{OWNER}}` или `TODO`. Заполните реальные данные и запустите `make feature-validate`.

**Q:** Как локально воспроизвести проверки документации?  
**A:** Выполните `npm install -g markdownlint-cli` (или `npx markdownlint "**/*.md"`) и `npx lychee --config .lychee.toml` (см. `.github/workflows/docs-lint.yml`). Ошибки должны быть исправлены до коммита.

## Поддержка

- Технические вопросы → [Issues](https://github.com/DmitrL-dev/1cai-public/issues)  
- Быстрая связь → Telegram-чат `@onec_ai_stack` (см. `docs/SUPPORT.md`)  
- Статус видеодемо → [issue #3](https://github.com/DmitrL-dev/1cai-public/issues/3`)

Дополняйте FAQ: создайте issue с меткой `documentation` или Pull Request с уточнением. Спасибо!

