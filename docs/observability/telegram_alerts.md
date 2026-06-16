# Telegram Alerts для 1C AI Stack

> Цель: описать, как подключить уведомления в Telegram к существующим алертам Prometheus/Alertmanager и workflow GitHub Actions.

---

## 1. Компоненты

- **Prometheus + Alertmanager** — генерируют алерты по метрикам (`monitoring/prometheus/alerts/ai_alerts.yml` и др.).
- **GitHub Actions workflow** `.github/workflows/telegram-alert.yaml` — отправка сообщений в Telegram по событию/скрипту.
- **Секреты**:
  - `TELEGRAM_BOT_TOKEN` — токен бота;
  - `TELEGRAM_CHAT_ID` — ID чата/канала для уведомлений.

На текущем этапе набор поддерживает:

- ручной/автоматический запуск workflow для отправки уведомлений;
- возможность интегрировать Alertmanager с внешним webhook, который триггерит тот же workflow или отдельный сервис.

---

## 2. Настройка секретов в GitHub

1. Создайте Telegram‑бота через `@BotFather` и получите `BOT_TOKEN`.
2. Получите `CHAT_ID` (для канала/чата):
   - добавьте бота в канал,
   - используйте любой из стандартных способов (например, `getUpdates` в Bot API) для получения ID.
3. В репозитории GitHub:
   - перейдите в **Settings → Secrets and variables → Actions → New repository secret**;
   - добавьте:
     - `TELEGRAM_BOT_TOKEN` = `BOT_TOKEN`,
     - `TELEGRAM_CHAT_ID` = ID канала/чата.

Workflow `.github/workflows/telegram-alert.yaml` использует эти секреты для отправки сообщений.

---

## 3. Связка с Alertmanager (вариант)

Базовый путь интеграции:

1. Alertmanager конфигурируется на отправку алертов в webhook (например, небольшой gateway‑сервис или n8n‑workflow).
2. Gateway вызывает:
   - либо Telegram Bot API напрямую;
   - либо GitHub Actions `workflow_dispatch` (если требуется проходить через CI).

Пример фрагмента Alertmanager‑конфига (идея, не готовый прод‑файл):

```yaml
receivers:
  - name: 'telegram-gateway'
    webhook_configs:
      - url: 'https://example.com/alertmanager/telegram'
```

Сервис `telegram-gateway` конвертирует payload в удобное сообщение и отправляет его в Telegram, используя те же `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`. Этот слой можно реализовать в отдельном репозитории или в `integrations/`.

---

## 4. Когда считать интеграцию завершённой

Для Dev/Stage окружений достаточно:

- секреты заданы в GitHub (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`);
- workflow `.github/workflows/telegram-alert.yaml` отрабатывает успешно;
- тестовый алерт (manual trigger) доходит до нужного чата в Telegram.

Для production‑канала:

- используются отдельные значения секретов (отдельный бот/канал или отдельный репозиторий/Org‑Secrets);
- в конституции/процессах явно описано, какие алерты должны уходить в prod‑канал и кто за них отвечает.

---

На текущем этапе в этом репозитории реализована **техническая основа** (workflow и структура секретов); фактическое подключение production‑канала зависит от конкретной инфраструктуры заказчика и может быть оформлено в виде отдельного runbook/infra‑репозитория.

*** End Patch***  } ***!

