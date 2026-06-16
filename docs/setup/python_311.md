# Установка Python 3.11

Цель: обеспечить корректный запуск API/MCP сервисов, которые требуют CPython 3.11.x (64-bit).

## Windows

1. Скачайте официальный установщик 64-bit (`Windows installer (64-bit)`) с [python.org/downloads](https://www.python.org/downloads/release/python-3119/).
2. При запуске установщика:
   - активируйте галочку **"Add python.exe to PATH"**;
   - выберите **Customize installation** → отметьте `pip`, `venv`, `py launcher`;
   - установите для всех пользователей.
3. После установки выполните в PowerShell:
   ```powershell
   py -3.11 --version
   make check-runtime
   ```
   Если команда `make check-runtime` завершилась успешно — требуемая версия доступна.

## Linux (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev
python3.11 --version
make check-runtime
```

## macOS (Homebrew)

```bash
brew install python@3.11
brew link python@3.11 --force
python3.11 --version
make check-runtime
```

## Дополнительно

- Убедитесь, что `pip`/`venv` работают от Python 3.11: `py -3.11 -m venv .venv`.
- Обновите `.venv` проекта: `python3.11 -m venv .venv && source .venv/bin/activate` (или `.\.venv\Scripts\activate` на Windows).
- Перезапустите сервисы: `make servers` (или отдельные `make api`, `make mcp`).
