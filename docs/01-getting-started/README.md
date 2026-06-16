# 🚀 Getting Started

Добро пожаловать в 1C AI Stack — лабораторию эксплуатационных и AI-практик для 1C:Enterprise. Этот раздел помогает быстро развернуть окружение, понять структуру репозитория и выбрать следующий шаг.

---

## 🗂 Что здесь есть

| Файл | Зачем читать |
|------|--------------|
| [`QUICKSTART.md`](QUICKSTART.md) | «TL;DR» запуск на локальной машине с использованием `make`/Docker |
| [`START_HERE.md`](START_HERE.md) | Пошаговый onboarding: обзор репозитория, что запускать в первую очередь |
| [`installation.md`](installation.md) | Детали установки зависимостей и подготовка окружения (Linux/macOS) |
| [`local.md`](local.md) | Работа без Docker: запуск сервисов вручную |
| [`LOCAL_MODEL_TRAINING.md`](LOCAL_MODEL_TRAINING.md) | Генерация датасетов, обучение и тест локальных моделей |
| [`python-setup.md`](python-setup.md) | Настройка Python 3.11 и виртуального окружения |
| [`telegram-setup.md`](telegram-setup.md) | Как подключить Telegram-интеграции платформы |
| [`INSTALLATION_VIDEO_GUIDE.md`](INSTALLATION_VIDEO_GUIDE.md) | Сценарий будущего видеогида (пошаговый сценарий) |
| [`DEPLOYMENT_INSTRUCTIONS.md`](DEPLOYMENT_INSTRUCTIONS.md) | Развертывание в инфраструктуре (Docker/Kubernetes) |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Как мы оформляем вклад: стиль коммитов, проверка, пайплайны |

---

## ⚡ Минимальный запуск (5 минут)

> **Требования:** Python 3.11, Docker 24+, Docker Compose, GNU Make (или PowerShell эквиваленты из `scripts/windows/`).

```bash
# 1. Склонируйте репозиторий
git clone git@github.com:DmitrL-dev/1cai.git
cd 1cai

# 2. Проверьте окружение
make check-runtime

# 3. Поднимите стенд «всё в Docker»
make docker-up      # базовые сервисы (БД, брокеры, Neo4j, Qdrant)
make migrate        # подготовка тестовых данных
make servers        # Graph API + MCP server
open http://localhost:6001/mcp
```

- **Windows:** используйте аналоги из `scripts/windows/` (`docker-up.ps1`, `migrate.ps1`, `servers.ps1`).
- **Под капотом:** см. `makefile` и `scripts/setup/check_runtime.py`.

После запуска доступен живой MCP endpoint, журнал сервисов и тестовые данные — можно сразу подключать IDE.

---

## 🧭 Далее по ролям

- **DevOps/SRE:** читайте [`docs/04-deployment/README.md`](../04-deployment/README.md) и [`docs/ops/devops_platform.md`](../ops/devops_platform.md) — там Helm/ArgoCD, Vault, Linkerd.
- **Архитектор/аналитик конфигураций:** начните с [`docs/06-features/EDT_PARSER_GUIDE.md`](../06-features/EDT_PARSER_GUIDE.md) и [`scripts/analysis/README.md`](../../scripts/analysis/README.md).
- **ML/AI команда:** смотрите [`docs/06-features/ML_DATASET_GENERATOR_GUIDE.md`](../06-features/ML_DATASET_GENERATOR_GUIDE.md) и [`LOCAL_MODEL_TRAINING.md`](LOCAL_MODEL_TRAINING.md).
- **On-call/операции:** беглый обзор в [`docs/process/`](../process/), тренировки и runbooks — [`docs/runbooks/`](../runbooks/), наблюдаемость — [`docs/observability/SLO.md`](../observability/SLO.md).

---

## 🛠 Что важно прогнать перед первым PR

1. `make check-runtime`
2. `make lint` (если правите код в `src/`)
3. `make test` (или соответствующий таргет из `docs/06-features/TESTING_GUIDE.md`)
4. `make render-uml` (если менялись диаграммы или ADR)
5. `make policy-check` (для инфраструктурных правок)

Точные инструкции — в [`docs/05-development/README.md`](../05-development/README.md) и [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 🔄 Навигация

- [⬅️ К оглавлению документации](../README.md)
- [➡️ Архитектура и планы](../02-architecture/README.md)
