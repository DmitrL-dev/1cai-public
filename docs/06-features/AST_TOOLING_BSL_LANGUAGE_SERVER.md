# AST Tooling: bsl-language-server

> Интеграция bsl-language-server позволяет получить полноценное AST (Abstract Syntax Tree) для BSL-кода и расширить анализ. Ниже описан полный цикл установки, запуска и диагностики.

## Обзор

- **Сервис:** [1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server) (Docker образ `ghcr.io/1c-syntax/bsl-language-server`). Благодарим авторов проекта за открытый доступ и документацию.
- **Назначение:** парсинг BSL кода, диагностика, сбор AST, метрики.
- **Интеграция в 1C AI Stack:**
  - `docker-compose.dev.yml` содержит сервис `bsl-language-server` и health-check.
  - Makefile включает цели `bsl-ls-up/down/logs/check`.
  - `scripts/parsers/bsl_ast_parser.py` читает URL из `BSL_LANGUAGE_SERVER_URL` и автоматически откатывается на regex, если LSP недоступен.
  - Дополнительный скрипт `scripts/parsers/check_bsl_language_server.py` выполняет health-check и тестовый parse.

## Требования

- Docker / Docker Compose (или совместимое окружение).
- Открытый порт `8081` на локальной машине (пробрасывается в контейнер: `8081 → 8080`).
- Python 3.11 для основного приложения.

## Быстрый старт

```bash
# 1. Запустить сервис
make bsl-ls-up

# 2. Проверить health и тестовый parse
make bsl-ls-check

# 3. Посмотреть логи при необходимости
make bsl-ls-logs

# 4. Остановить сервис
make bsl-ls-down
```

Здоровый сервис отвечает `{"status":"UP"}` по адресу `http://localhost:8081/actuator/health`.

## Переменные окружения

| Переменная                    | Назначение                                 | Значение по умолчанию                |
|------------------------------|---------------------------------------------|--------------------------------------|
| `BSL_LANGUAGE_SERVER_URL`    | URL сервиса, которым пользуются парсеры    | `http://bsl-language-server:8080`    |
| `SPRING_MAIN_BANNER-MODE`    | Отключение баннера Spring Boot в контейнере| `off` (настроено в docker-compose)   |

## Интеграция с парсерами

- `scripts/parsers/bsl_ast_parser.py`:
  - При инициализации проверяет `/actuator/health`.
  - Если сервис недоступен, выводит предупреждение и включает fallback на regex.
  - При успешном запуске возвращает AST, diagnostics, контрольные метрики.
- Планы по дальнейшей интеграции (см. `docs/research/bsl_language_server_plan.md`): перепрогон AST-метрик, логирование fallback и др.

## Диагностика

### Команда `make bsl-ls-check`

Выполняет скрипт `scripts/parsers/check_bsl_language_server.py`:
1. Health check (`/actuator/health`).
2. Тестовый parse фрагмента кода (возвращает AST).

### Ручная проверка

```powershell
Invoke-WebRequest http://localhost:8081/actuator/health
```

```bash
curl -X POST http://localhost:8081/lsp/parse \
     -H "Content-Type: application/json" \
     -d '{"text":"Процедура Тест()\nКонецПроцедуры","languageId":"bsl"}'
```

### Логи

```
make bsl-ls-logs
```

### Типичные проблемы

| Симптом                                | Действие                                                          |
|----------------------------------------|-------------------------------------------------------------------|
| Health-check не отвечает               | Убедиться, что Docker запущен; проверить порт 8081; перезапустить сервис. |
| `BSLASTParser` предупреждает о fallback| Проверить `make bsl-ls-check`; если сервис стартует дольше, увеличить `start_period` health-check. |
| Ошибка `java.net.BindException`        | Порт 8080 внутри контейнера занят — убедиться, что нет второго экземпляра. |
| `curl: (7) Failed to connect`          | Проблемы с сетью внутри Docker; проверить `docker network ls`.      |

> Перед эскалацией просьба самостоятельно собрать информацию: результат `make bsl-ls-check`, кусок логов и содержимое health endpoint.

## Откат и очистка

- `make bsl-ls-down` — останавливает сервис.
- `docker-compose -f docker-compose.dev.yml rm bsl-language-server` — принудительное удаление контейнера (при необходимости).

## Благодарности и лицензии

- [1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server) — грамматика и сервис AST.
- Интеграция основана на открытых лицензиях и сопровождается благодарностями также в `README.md` и `CHANGELOG.md`.

