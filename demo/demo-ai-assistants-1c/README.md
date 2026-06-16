# AI Assistants для 1C

Современное веб-приложение с AI ассистентами для платформы 1C, созданное на React + TypeScript + Vite.

[![Test Suite](https://github.com/demo/demo-ai-assistants-1c/actions/workflows/test.yml/badge.svg)](https://github.com/demo/demo-ai-assistants-1c/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/demo/demo-ai-assistants-1c/branch/main/graph/badge.svg)](https://codecov.io/gh/demo/demo-ai-assistants-1c)
[![Coverage Status](https://img.shields.io/badge/coverage-80%25-brightgreen.svg)](https://codecov.io/gh/demo/demo-ai-assistants-1c)
[![Tests](https://img.shields.io/badge/tests-ready-green.svg)](./docs/testing-guide.md)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-active-blue.svg)](./.github/workflows/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](../../LICENSE)

## 🚀 Быстрый старт

### Предварительные требования

- Node.js 18+ 
- pnpm 8+
- Git

### Установка и запуск

```bash
# Клонирование репозитория
git clone <repository-url>
cd demo-ai-assistants-1c

# Установка зависимостей
pnpm install

# Запуск в режиме разработки
pnpm dev

# Сборка для production
pnpm build

# Предварительный просмотр production сборки
pnpm preview
```

## 🧪 Тестирование и Coverage

### Обзор системы тестирования

Проект использует многоуровневую стратегию тестирования с автоматической coverage отчетностью:

- **Unit тесты** (`tests/unit/`) - изолированное тестирование компонентов и функций с Deno
- **Integration тесты** (`tests/integration/`) - тестирование взаимодействия между модулями
- **E2E тесты** (`tests/e2e/`) - полные пользовательские сценарии с Playwright

### 🚀 Быстрый запуск тестов

```bash
# Запуск всех тестов с coverage
pnpm test:all

# Unit тесты
pnpm test:unit
pnpm test:unit:coverage

# Integration тесты  
pnpm test:integration
pnpm test:integration:coverage

# E2E тесты
pnpm test:e2e
pnpm test:e2e:ui

# Полный набор тестов для CI/CD
pnpm test:ci

# Генерация coverage отчетов
pnpm test:coverage
pnpm test:analyze
pnpm coverage:serve

# Watch режим для разработки
pnpm test:watch
```

### 📊 Coverage Отчеты

#### Структура coverage данных

```
coverage/
├── html/                    # HTML отчеты для просмотра в браузере
├── coverage-final.json     # JSON данные coverage
├── coverage.lcov           # LCOV формат для интеграции с CI/CD
├── detailed/               # Детальные отчеты
│   ├── dashboard.md        # Общий дашборд coverage
│   ├── files-analysis.md   # Анализ покрытия файлов
│   ├── functions-analysis.md # Анализ покрытия функций
│   └── component-analysis.md # Анализ покрытия компонентов
└── playwright/             # E2E тест результаты
    ├── results.json        # Результаты Playwright
    ├── results.xml         # JUnit формат
    ├── videos/             # Видео проваленных тестов
    ├── screenshots/        # Скриншоты ошибок
    └── har/                # HAR файлы для анализа производительности
```

#### Coverage Метрики

- **Общий coverage**: ≥ 80%
- **Компоненты**: ≥ 70%
- **Hooks**: ≥ 85%
- **Утилиты**: ≥ 95%
- **API сервисы**: ≥ 80%

### 🔄 Автоматизация CI/CD

#### GitHub Actions Pipeline

Автоматические тесты запускаются при:
- ✅ Создании Pull Request
- ✅ Push в main/develop ветку
- ✅ Ежедневно в 02:00 UTC

#### CI/CD Стадии

1. **Setup Environment**
   - Node.js 18.x и 20.x matrix
   - pnpm установка с кэшированием
   - Dependency cache optimization

2. **Code Quality**
   - ESLint проверка
   - TypeScript компиляция
   - Security audit

3. **Test Execution**
   - Unit тесты с coverage
   - Integration тесты с coverage  
   - E2E тесты (Playwright)
   - Security и dependency checks

4. **Coverage Reporting**
   - Upload в Codecov
   - PR комментарии с coverage
   - Артефакты для скачивания

#### Coverage Интеграция

- **Codecov**: Автоматическая отправка coverage данных
- **GitHub PR**: Комментарии с coverage в Pull Request
- **Badge**: Coverage статус в README
- **HTML Reports**: Детальные отчеты в артефактах

### 🛠️ Инструменты тестирования

#### Технологии
- **Deno Test Runner** - для Unit/Integration тестов
- **Playwright** - для E2E тестов на всех браузерах
- **MSW** - Mock Service Worker для API тестирования

#### Конфигурация
- `deno.json` - Настройки Deno coverage
- `playwright.config.ts` - Конфигурация E2E тестов
- `.deno/coverage/` - Конфигурация coverage
- `scripts/run-tests.ts` - Основной runner всех тестов
- `scripts/test-coverage.ts` - Детальный coverage анализ

### 📝 Рекомендации по тестированию

#### При написании тестов
- Стремитесь к 80% coverage
- Тестируйте критическую бизнес-логику
- Используйте моки для внешних зависимостей
- Добавляйте E2E тесты для ключевых пользовательских сценариев

#### Структура тестов
```
tests/
├── unit/                   # .test.ts файлы
│   ├── components/         # Тесты компонентов
│   ├── hooks/             # Тесты custom hooks
│   └── utils/             # Тесты утилит
├── integration/           # .test.ts файлы
│   ├── api/               # API интеграция
│   └── workflows/         # Бизнес-процессы
└── e2e/                   # .spec.ts файлы
    ├── auth.spec.ts       # Авторизация
    ├── generation.spec.ts # Генерация контента
    └── navigation.spec.ts # Навигация
```

## 📁 Структура проекта

```
demo-ai-assistants-1c/
├── docs/                    # Документация
│   ├── testing-guide.md     # Руководство по тестированию
│   ├── test-coverage-report.md # Отчет по coverage
│   └── api/                 # API документация
├── tests/                   # Тесты
│   ├── unit/               # Модульные тесты
│   ├── integration/        # Интеграционные тесты
│   ├── e2e/               # End-to-End тесты
│   └── fixtures/          # Тестовые данные
├── src/                    # Исходный код
│   ├── components/        # React компоненты
│   ├── hooks/            # Custom hooks
│   ├── services/         # API сервисы
│   ├── contexts/         # React контексты
│   └── utils/            # Утилиты
├── public/                # Статические файлы
└── dist/                  # Production сборка
```

## 🛠️ Технологический стек

### Frontend
- **React 18** - UI библиотека
- **TypeScript** - типизированный JavaScript
- **Vite** - сборщик и dev server
- **Tailwind CSS** - CSS фреймворк
- **Radix UI** - компоненты доступности
- **React Router** - маршрутизация

### Тестирование
- **Deno Test Runner** - основной тестовый раннер для unit/integration тестов
- **Playwright** - E2E тестирование на всех браузерах (Chrome, Firefox, Safari, Mobile)
- **Testing Library** - тестирование React компонентов
- **MSW** - Mock Service Worker для API тестирования
- **Codecov** - автоматическая coverage отчетность
- **GitHub Actions** - CI/CD pipeline с matrix testing (Node.js 18.x, 20.x)

### DevOps и Quality Assurance
- **Coverage Reporting** - автоматические отчеты в HTML, LCOV, JSON форматах
- **Security Audit** - автоматическая проверка зависимостей на уязвимости
- **Matrix Testing** - тестирование на multiple Node.js версиях
- **Artifact Storage** - сохранение coverage отчетов, видео, скриншотов
- **Badge Integration** - live coverage status в README

### Утилиты
- **React Hook Form** - управление формами
- **Zod** - валидация схем
- **Date-fns** - работа с датами
- **Lucide React** - иконки

## 🚀 Available Scripts

```bash
# Development
pnpm dev                 # Запуск dev сервера
pnpm build              # Production сборка
pnpm build:prod         # Production сборка с оптимизацией
pnpm preview            # Preview production сборки

# Code Quality
pnpm lint               # ESLint проверка
pnpm lint:fix           # ESLint автоисправление
pnpm type-check         # TypeScript проверка

# Testing - Unit тесты
pnpm test               # Запуск всех тестов
pnpm test:unit          # Unit тесты
pnpm test:unit:coverage # Unit тесты с coverage
pnpm test:watch         # Watch режим для тестов

# Testing - Integration тесты  
pnpm test:integration   # Integration тесты
pnpm test:integration:coverage # Integration тесты с coverage

# Testing - E2E тесты
pnpm test:e2e           # End-to-End тесты
pnpm test:e2e:ui        # E2E тесты в UI режиме

# Testing - Комплексные команды
pnpm test:all           # Все тесты (unit + integration + e2e)
pnpm test:ci            # CI режим тестирования (полный набор)

# Coverage анализ
pnpm test:coverage      # Генерация coverage отчета
pnpm test:coverage:html # HTML отчет coverage
pnpm test:coverage:lcov # LCOV отчет для CI/CD
pnpm coverage:report    # Полный coverage отчет (HTML + LCOV)
pnpm coverage:serve     # Запуск сервера для просмотра HTML coverage

# Детальный анализ
pnpm test:analyze       # Детальный coverage анализ с отчетами
pnpm test:analyze:detailed # Расширенный анализ всех метрик

# Security
pnpm security:audit         # Проверка безопасности зависимостей
pnpm security:audit:fix     # Автоматическое исправление уязвимостей

# Dependencies
pnpm deps:update            # Обновление всех пакетов
pnpm deps:check             # Проверка устаревших пакетов
pnpm deps:analyze           # Анализ зависимостей

# Utilities
pnpm install-deps       # Переустановка зависимостей
pnpm clean              # Очистка node_modules и lock файла
```

## 📱 Ассистенты

### Доступные ассистенты

🤖 **Архитектор 1C** - Помогает с проектированием архитектуры систем

👨‍💻 **Разработчик 1C** - Помогает с разработкой и отладкой кода

📊 **Проект-менеджер** - Управление проектами и задачами

📈 **Аналитик** - Анализ данных и создание отчетов

🔧 **Администратор** - Настройка и администрирование системы

### Использование ассистентов

```typescript
import { useAssistant } from '@/hooks/useAssistant'

const { sendMessage, isLoading, error } = useAssistant('architect-assistant')

const handleSendMessage = async () => {
  await sendMessage('Создай архитектуру для CRM системы')
}
```

## 🔧 Настройка окружения

### Environment переменные

Создайте файл `.env.local`:

```env
# Supabase (опционально)
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_key

# API Configuration
VITE_API_BASE_URL=http://localhost:3000
VITE_API_TIMEOUT=10000

# Feature Flags
VITE_ENABLE_MOCK_DATA=true
VITE_ENABLE_DEBUG=true
```

### Настройка тестирования

Для полной функциональности тестов установите дополнительные зависимости:

```bash
# Основные тестовые библиотеки
pnpm add -D vitest @vitest/ui jsdom
pnpm add -D @testing-library/react @testing-library/jest-dom
pnpm add -D @testing-library/user-event
pnpm add -D happy-dom

# E2E тестирование
pnpm add -D @playwright/test

# Покрытие кода
pnpm add -D @vitest/coverage-v8
```

## 🤝 Контрибьюция

### Процесс разработки

1. **Fork** репозитория
2. **Создайте** feature branch (`git checkout -b feature/amazing-feature`)
3. **Напишите** тесты для новой функциональности
4. **Убедитесь** что все тесты проходят (`pnpm test:all`)
5. **Commit** изменения (`git commit -m 'Add amazing feature'`)
6. **Push** в branch (`git push origin feature/amazing-feature`)
7. **Откройте** Pull Request

### Требования к коду

- ✅ Все тесты должны проходить
- ✅ Покрытие кода не менее 80%
- ✅ ESLint проверки без ошибок
- ✅ TypeScript компиляция без ошибок
- ✅ Добавлены тесты для новой функциональности

### Git hooks

Проект настроен с pre-commit hooks для автоматической проверки:

```bash
# Автоматически выполняется перед commit:
pnpm lint:fix        # Исправление lint ошибок
pnpm type-check      # TypeScript проверка
pnpm test:ci         # Быстрая проверка тестов
```

## 📊 Мониторинг и метрики

### Performance

```bash
# Lighthouse проверка
pnpm lighthouse

# Bundle анализ
pnpm analyze
```

### Coverage отчеты

```bash
# HTML отчет по покрытию
pnpm test:coverage
# Отчет доступен в coverage/index.html
```

## 🔍 Troubleshooting

### Частые проблемы

**❌ Deno тесты не запускаются**

```bash
# Убедитесь что Deno установлен и доступен
deno --version

# Установите Deno если нужно
curl -fsSL https://deno.land/install.sh | sh

# Проверьте deno.json конфигурацию
```

**❌ Coverage данные не генерируются**

```bash
# Создайте директорию для coverage
mkdir -p .deno/coverage coverage

# Запустите с explicitly указанным coverage directory
deno test --coverage=.deno/coverage src/**/*.test.ts

# Проверьте права доступа к директориям
chmod 755 .deno/coverage coverage
```

**❌ E2E тесты падают на CI/CD**

```bash
# Убедитесь что браузеры Playwright установлены
npx playwright install --with-deps

# Проверьте что preview сервер запускается
pnpm preview --host 0.0.0.0 --port 4173

# Запустите в debug режиме
pnpm test:e2e --debug
```

**❌ Build ошибки**

```bash
# Очистите кэш и переустановите зависимости
pnpm clean
pnpm install

# Проверьте TypeScript ошибки
pnpm type-check
```

**❌ Coverage ниже 80%**

```bash
# Запустите детальный анализ coverage
pnpm test:analyze

# Сгенерируйте HTML отчет для просмотра
pnpm coverage:serve

# Посмотрите какие файлы не покрыты
ls -la coverage/detailed/
```

**❌ GitHub Actions ошибки**

```bash
# Проверьте логи в GitHub Actions
# Убедитесь что secrets настроены:
# - CODECOV_TOKEN (опционально)

# Локально запустите тот же набор что в CI
pnpm test:ci
```

**❌ Memory/CPU высокие при тестах**

```bash
# Ограничьте параллельность тестов
pnpm test:unit --jobs=2

# Используйте отдельную директорию для coverage
export COVERAGE_DIR=.deno/coverage_unit_test
```

## 📞 Поддержка

- 📖 **[Документация](./docs/)** - полная документация проекта
- 🐛 **[Issues](https://github.com/DmitrL-dev/1cai-public/issues)** - баги и фича-реквесты
- 💬 **[Discussions](https://github.com/DmitrL-dev/1cai-public/discussions)** - обсуждения и вопросы
- 📧 **`Email`** - техническая поддержка

## 📄 Лицензия

Проект лицензирован под MIT License - подробности в файле [LICENSE](../../LICENSE).

---

**Made with ❤️ for 1C developers**

[![React](https://img.shields.io/badge/React-18.3.1-61DAFB.svg?style=flat&logo=react)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6.2-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0.1-646CFF.svg?style=flat&logo=vite)](https://vitejs.dev/)
[![Testing Library](https://img.shields.io/badge/Testing_Library-Latest-E33332.svg?style=flat&logo=testing-library)](https://testing-library.com/)
