# Руководство по устранению проблем Windows + Docker

## 🐛 Распространённые проблемы и решения

### Проблема 1: Зависание/блокировка папки node_modules

**Симптомы:**

- VS Code зависает при открытии `portal`
- Невозможно удалить папку `node_modules`
- Docker volume mount вызывает экстремальную медлительность
- Операции с файлами завершаются по таймауту

**Причина:**
Конфликты файловой системы Windows с Docker volume mounts для `node_modules` (тысячи мелких файлов).

**Решение:**

#### Шаг 1: Полная остановка

```powershell
# Остановить все Docker контейнеры
docker-compose down

# Полностью закрыть VS Code (важно!)
# Это освобождает блокировки файлов
```

#### Шаг 2: Ручная очистка (PowerShell от Администратора)

```powershell
cd c:\1cAI\portal

# Принудительно удалить проблемные папки
Remove-Item -Path "node_modules" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path ".vite" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "package-lock.json" -Force -ErrorAction SilentlyContinue
```

**Если папки не удаляются:**

1. Перезагрузите компьютер
2. Сразу после загрузки удалите папки до запуска сервисов
3. Это очистит все скрытые блокировки файлов

#### Шаг 3: Установка зависимостей на хосте (НЕ в Docker)

```bash
# В директории portal
npm install

# Проверить установку
npm list --depth=0
```

#### Шаг 4: Настроить VS Code для исключения папок

Создать/обновить `.vscode/settings.json`:

```json
{
  "files.watcherExclude": {
    "**/node_modules/**": true,
    "**/dist/**": true,
    "**/.vite/**": true
  },
  "search.exclude": {
    "**/node_modules": true,
    "**/dist": true,
    "**/.vite": true
  },
  "files.exclude": {
    "**/node_modules": false,
    "**/dist": true,
    "**/.vite": true
  }
}
```

---

### Проблема 2: Сборка Docker падает на Windows

**Симптомы:**

- `docker build` падает с ошибками прав доступа
- Проблемы с окончаниями строк (CRLF vs LF)
- Проблемы с разделителями путей

**Решение:**

#### Исправить окончания строк

```bash
# Настроить git на использование LF
git config --global core.autocrlf input

# Перевыкачать файлы
git rm --cached -r .
git reset --hard
```

#### Использовать WSL2 Backend

1. Включить WSL2 в настройках Docker Desktop
2. Переместить проект в файловую систему WSL2 для лучшей производительности:

```bash
# В терминале WSL2
cd ~
git clone <ваш-репозиторий>
cd 1cAI
```

---

### Проблема 3: Конфликты портов

**Симптомы:**

- `docker-compose up` падает с "port already in use"
- Сервисы не могут привязаться к портам

**Решение:**

#### Найти и убить процесс, использующий порт

```powershell
# Найти процесс на порту 5432 (PostgreSQL)
netstat -ano | findstr :5432

# Убить процесс (заменить PID)
taskkill /PID <PID> /F
```

#### Или изменить порты в docker-compose.yml

```yaml
services:
  postgres:
    ports:
      - "5433:5432" # Использовать другой порт хоста
```

---

### Проблема 4: Медленная работа Docker на Windows

**Симптомы:**

- Крайне медленные файловые операции
- Высокая загрузка CPU
- Долгое время сборки

**Решения:**

#### 1. Использовать WSL2 Backend

Docker Desktop → Settings → General → Use WSL2 based engine

#### 2. Выделить больше ресурсов

Docker Desktop → Settings → Resources:

- CPUs: 4+
- Memory: 8GB+
- Swap: 2GB+

#### 3. Отключить сканирование антивируса для папок Docker

Добавить исключения в Windows Defender:

- `C:\ProgramData\Docker`
- `C:\Users\<username>\.docker`
- Директория вашего проекта

#### 4. Использовать Named Volumes вместо Bind Mounts

```yaml
# Вместо:
volumes:
  - ./portal:/app

# Использовать:
volumes:
  - frontend-code:/app
volumes:
  frontend-code:
```

---

### Проблема 5: Ошибки компиляции TypeScript

**Симптомы:**

- `tsc --noEmit` показывает 200+ ошибок
- Сборка падает в CI, но работает локально

**Решение:**

#### Очистить кэш TypeScript

```bash
cd portal

# Удалить кэш
rm -rf node_modules/.cache
rm -rf dist

# Переустановить
npm ci

# Пересобрать
npm run build
```

#### Убедиться в правильных версиях Node/npm

```bash
# Проверить версии
node --version  # Должна быть 18.x или 20.x
npm --version   # Должна быть 9.x или 10.x

# Использовать nvm для переключения при необходимости
nvm install 20
nvm use 20
```

---

## 🔧 Советы по предотвращению проблем

### 1. Всегда устанавливать на хосте

Для frontend проектов всегда запускайте `npm install` на хост-машине, а не в Docker.

### 2. Использовать .dockerignore

```
node_modules
dist
.vite
.cache
*.log
```

### 3. Регулярная очистка

```bash
# Еженедельная очистка
docker system prune -a
docker volume prune
```

### 4. Следить за дисковым пространством

Docker может потреблять значительное дисковое пространство. Держите минимум 20GB свободными.

---

## 📞 Всё ещё есть проблемы?

1. Проверьте логи Docker Desktop: Settings → Troubleshoot → View logs
2. Проверьте Windows Event Viewer на системные ошибки
3. Попробуйте запустить в WSL2 вместо Windows
4. Создайте GitHub Issue с:
   - Версией Windows
   - Версией Docker Desktop
   - Сообщениями об ошибках
   - Шагами для воспроизведения

---

**Последнее обновление:** 2025-11-22  
**Применимо к:** Windows 10/11, Docker Desktop 4.x+
