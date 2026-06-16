# Ansible Bootstrap для 1C AI Stack

## 1. Цель
Быстро подготовить Linux-хост (bare metal/VM) к запуску DevOps-стека: Docker, kubectl, Helm, Terraform, ansible-lint.

## 2. Структура
- `infrastructure/ansible/site.yml` — главный playbook.
- `infrastructure/ansible/hosts.ini` — пример inventory.
- `infrastructure/ansible/requirements.yml` — роли (`geerlingguy.docker`).

## 3. Запуск
```bash
cd infrastructure/ansible
ansible-galaxy install -r requirements.yml
ansible-playbook -i hosts.ini site.yml --ask-become-pass
```

## 4. Расширение
- Роли для AWS/Azure (установка CLI, настройки профилей).
- Настройка Vault agent/ Docker registry mirror.
- Интеграция с Jenkins/GitLab runner provisioning.
