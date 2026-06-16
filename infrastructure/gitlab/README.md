# GitLab CI Pipeline

| Файл | Описание |
|------|----------|
| `.gitlab-ci.yml` | Пример многостадийного пайплайна (lint → tests → build → security scan → deploy). Использует Docker registry GitLab и окружения для `staging`/`prod`.

## Как использовать
1. Скопируйте `.gitlab-ci.yml` в корень вашего GitLab репозитория.
2. Настройте переменные CI/CD: `REGISTRY_USER`, `REGISTRY_PASSWORD`, `VAULT_TOKEN`, `ARGOCD_TOKEN`, `AWS_*` (по необходимости).
3. При необходимости обновите stages в соответствии с вашим процессом.

Структура стадий отражает требования из [docs/research/constitution.md](../../docs/research/constitution.md).
