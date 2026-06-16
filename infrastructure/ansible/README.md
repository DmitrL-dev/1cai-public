# Ansible Bootstrap Playbook

Назначение — подготовить Linux-хост (Ubuntu/Debian) к запуску 1C AI Stack: Docker, Kubernetes toolchain, Helm, Terraform, Python окружение.

## Запуск
```bash
cd infrastructure/ansible
ansible-playbook -i hosts.ini site.yml --ask-become-pass
```

`hosts.ini` пример:
```
[dev]
node1 ansible_host=192.168.1.20 ansible_user=ubuntu
```

## Что делает `site.yml`
- Обновляет apt, устанавливает Docker, kubectl, Helm, Terraform.
- Добавляет пользователя в группу `docker`.
- Устанавливает Python инструменты (pip, virtualenv, ansible deps из `requirements.yml`).
- Создаёт директории `/opt/1cai`, подготавливает рабочую структуру.

После выполнения хост готов к запуску `make docker-up`, `make helm-deploy` и других команд. Дополнительные инструкции — в [docs/ops/devops_platform.md](../../docs/ops/devops_platform.md).
