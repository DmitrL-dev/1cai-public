# 🧪 Тестовая инфраструктура для Deno Edge Functions

**Полная тестовая инфраструктура** для разработки и тестирования Deno Edge Functions в проекте demo-ai-assistants-1c.

## 📋 Содержание

- [🚀 Быстрый старт](#-быстрый-старт)
- [🏗️ Архитектура](#архитектура)
- [📁 Структура проекта](#-структура-проекта)
- [⚡ Доступные команды](#-доступные-команды)
- [🧪 Типы тестов](#-типы-тестов)
- [🔧 Инструменты](#-инструменты)
- [📊 Покрытие кода](#-покрытие-кода)
- [⚙️ Конфигурация](#конфигурация)
- [📈 CI/CD](#-cicd)
- [📚 Документация](#-документация)

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
# Установка Deno
curl -fsSL https://deno.land/install.sh | sh

# Или через пакетный менеджер
brew install deno    # macOS
choco install deno   # Windows
```

### 2. Настройка переменных окружения

Создайте файл `.env.test` в корне проекта:

```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
STRIPE_SECRET_KEY=sk_test_...
SENDGRID_API_KEY=SG.test123
OPENAI_API_KEY=sk-test-openai-key
ENVIRONMENT=test
LOG_LEVEL=info
```

### 3. Запуск тестов

```bash
# Все тесты
deno test

# Быстрые тесты (unit)
deno test tests/unit/**/*.test.ts

# С покрытием кода
deno test --coverage=coverage --coverage-include='supabase/functions/**/*'

# Режим наблюдения
deno test --watch tests/**/*.test.ts
```

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    ТЕСТОВАЯ ИНФРАСТРУКТУРА                   │
├─────────────────────────────────────────────────────────────┤
│  🔧 Configuration (deno.jsonc, test.config.ts)              │
│  📊 Coverage & Reports (coverage/, reports/)               │
│  🔒 Security Tests (XSS, SQL injection, Auth)              │
├─────────────────────────────────────────────────────────────┤
│                    ТИПЫ ТЕСТОВ                             │
│  ┌─────────────┐ ┌─────────────────┐ ┌─────────────────┐   │
│  │    UNIT     │ │  INTEGRATION    │ │      E2E        │   │
│  │  Isolated   │ │ Components      │ │ Full Workflows  │   │
│  │ components  │ │ interaction     │ │ User journeys   │   │
│  └─────────────┘ └─────────────────┘ └─────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                  ВСПОМОГАТЕЛЬНЫЕ ИНСТРУМЕНТЫ                │
│  🎭 Mocks (Supabase, HTTP, Database)                       │
│  🛠️ Utils (Helpers, Generators, Profilers)                │
│  📦 Fixtures (Test data, API responses)                    │
├─────────────────────────────────────────────────────────────┤
│                     CI/CD ИНТЕГРАЦИЯ                        │
│  🐙 GitHub Actions                                         │
│  🔄 Pre-commit hooks                                       │
│  📊 Coverage reporting (Codecov)                           │
│  🚀 Automated testing                                      │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Структура проекта

```
tests/
├── 📂 unit/                          # Unit тесты
│   ├── edge-function.test.ts         # Тесты Edge Functions
│   ├── utils.test.ts                 # Тесты утилит
│   └── validation.test.ts            # Тесты валидации
│
├── 📂 integration/                   # Интеграционные тесты
│   ├── workflow.test.ts              # Пользовательские сценарии
│   ├── api.test.ts                   # API интеграции
│   └── database.test.ts              # Интеграция с БД
│
├── 📂 e2e/                           # End-to-End тесты
│   ├── complete-journey.test.ts      # Полный пользовательский путь
│   ├── purchase.test.ts              # Процесс покупки
│   └── return-process.test.ts        # Процесс возврата
│
├── 📂 mocks/                         # Моки и заглушки
│   ├── supabase.ts                   # Мок Supabase клиента
│   └── requests.ts                   # Мок HTTP запросов
│
├── 📂 utils/                         # Вспомогательные функции
│   ├── test-helpers.ts               # Основные утилиты
│   └── scripts.ts                    # Команды и скрипты
│
├── 📂 fixtures/                      # Тестовые данные
│   └── test-data.ts                  # Готовые фикстуры
│
├── 📂 config/                        # Конфигурация
│   └── test.config.ts                # Настройки тестов
│
├── 📂 .gitignore                     # Игнорируемые файлы
├── 📄 TESTING_GUIDE.md               # Подробное руководство
└── 📄 README_TESTS.md                # Этот файл
```

## ⚡ Доступные команды

### Основные команды

```bash
# Запуск тестов
deno test                    # Все тесты
deno test --watch            # Режим наблюдения
deno test --coverage         # С покрытием кода
deno test --parallel         # Параллельное выполнение

# По типам тестов
deno test tests/unit/**/*.test.ts        # Unit тесты
deno test tests/integration/**/*.test.ts # Integration тесты  
deno test tests/e2e/**/*.test.ts         # E2E тесты

# Проверка кода
deno lint                    # Линтинг
deno fmt                     # Форматирование
deno fmt --check             # Проверка форматирования
deno check tests/**/*.ts     # Проверка типов

# Очистка
deno cache --reload          # Очистка кэша
rm -rf coverage .deno        # Очистка артефактов
```

### NPM скрипты

Добавьте в `package.json`:

```json
{
  "scripts": {
    "test": "deno test",
    "test:unit": "deno test tests/unit/**/*.test.ts",
    "test:integration": "deno test tests/integration/**/*.test.ts",
    "test:e2e": "deno test tests/e2e/**/*.test.ts",
    "test:coverage": "deno test --coverage=coverage --coverage-include='supabase/functions/**/*'",
    "test:watch": "deno test --watch tests/**/*.test.ts",
    "test:quick": "deno test tests/unit/**/*.test.ts --parallel",
    "test:slow": "deno test tests/integration/**/*.test.ts tests/e2e/**/*.test.ts",
    "test:ci": "deno test --coverage=coverage --allow-net --allow-env",
    "lint": "deno lint",
    "fmt": "deno fmt",
    "fmt:check": "deno fmt --check",
    "typecheck": "deno check tests/**/*.ts",
    "clean": "rm -rf coverage .deno deno.lock"
  }
}
```

## 🧪 Типы тестов

### 📦 Unit Tests
**Цель**: Тестирование отдельных компонентов в изоляции

**Характеристики:**
- ⚡ Быстрые (1-5 секунд)
- 🎯 Тестируют одну функцию/компонент
- 🔒 Изолированы от внешних зависимостей
- 📊 Высокое покрытие кода

**Пример:**
```typescript
Deno.test("User validation", async () => {
  const userData = { email: "invalid-email", name: "" };
  const request = createMockRequest("/users", "POST", {}, userData);
  
  const response = await executeFunction("user-handler", request);
  
  assertEquals(response.status, 400);
  const result = await response.json();
  assertEquals(result.error, "Validation failed");
});
```

### 🔗 Integration Tests
**Цель**: Тестирование взаимодействия между компонентами

**Характеристики:**
- 🐌 Более медленные (5-30 секунд)
- 🌐 Тестируют интеграции с внешними сервисами
- 🗄️ Взаимодействие с базой данных
- 📡 Тестирование API

**Пример:**
```typescript
Deno.test("Complete user workflow", async () => {
  // 1. Регистрация
  const registerResponse = await registerUser(userData);
  assertEquals(registerResponse.status, 201);
  
  // 2. Аутентификация
  const authResponse = await loginUser(credentials);
  assertEquals(authResponse.status, 200);
  
  // 3. Создание профиля
  const profileResponse = await createProfile(profileData);
  assertEquals(profileResponse.status, 201);
});
```

### 🎭 End-to-End Tests
**Цель**: Тестирование полных пользовательских сценариев

**Характеристики:**
- 🐌 Самые медленные (30+ секунд)
- 🎭 Полные пользовательские сценарии
- 🔄 Тестирование бизнес-процессов
- 📱 Валидация пользовательского опыта

**Пример:**
```typescript
Deno.test("Complete purchase journey", async () => {
  // Полный процесс от регистрации до получения товара
  const user = await registerTestUser();
  const catalog = await browseCatalog();
  await addToCart(productId, quantity);
  const order = await createOrder(orderData);
  const payment = await processPayment(paymentData);
  await sendConfirmationEmail(order.id);
});
```

## 🔧 Инструменты

### 🎭 Моки (Mocks)

#### Supabase Mock
```typescript
// Имитация базы данных
const mockSupabase = createMockSupabaseClient();
const result = await mockSupabase.from('users').select().single();
```

#### HTTP Mock
```typescript
// Имитация внешних API
installMockFetch();
setupApiHandlers();
expectRequest("https://api.example.com/users", "POST", userData);
```

### 🛠️ Утилиты (Utils)

#### Test Helpers
```typescript
// Генерация тестовых данных
const user = generateUser({ email: "test@example.com" });
const request = createMockRequest(url, method, headers, body);

// Профилирование
PerformanceProfiler.start("operation");
await executeFunction(...);
PerformanceProfiler.end("operation");
```

#### Assertions
```typescript
// Кастомные проверки
assertions.toBeEqual(actual, expected);
assertions.toBeTypeOf(value, "string");
assertions.toThrowError(fn, "error message");
```

### 📦 Фикстуры (Fixtures)

#### Готовые тестовые данные
```typescript
// Пользователи
const adminUser = userFixtures.admin;
const basicUser = userFixtures.basic;

// Товары
const electronicsProduct = productFixtures.electronics;
const clothingProduct = productFixtures.clothing;

// Заказы
const paidOrder = orderFixtures.paid;
const deliveredOrder = orderFixtures.delivered;
```

## 📊 Покрытие кода

### Настройка покрытия

В `deno.jsonc` настроено автоматическое покрытие:

```json
{
  "test": {
    "coverage": {
      "include": ["supabase/functions/**/*"],
      "exclude": [
        "**/*.d.ts",
        "**/*.test.ts",
        "**/mocks/**/*",
        "**/fixtures/**/*"
      ],
      "reportDir": "coverage",
      "type": "html"
    }
  }
}
```

### Минимальные пороги

| Метрика | Порог | Описание |
|---------|-------|----------|
| **Statements** | 80% | Покрытие операторов |
| **Branches** | 70% | Покрытие ветвлений |
| **Functions** | 80% | Покрытие функций |
| **Lines** | 80% | Покрытие строк кода |

### Просмотр отчета

```bash
# Генерация отчета
deno test --coverage=coverage

# Открытие в браузере
open coverage/index.html  # macOS
start coverage/index.html # Windows
```

## ⚙️ Конфигурация

### deno.jsonc
Основной файл конфигурации Deno с настройками:
- Compiler options
- Linting rules  
- Testing configuration
- Import mappings
- Custom tasks

### test.config.ts
Конфигурация тестового окружения:
- Timeout настройки
- Mock конфигурация
- Coverage thresholds
- Environment variables
- Performance settings

### Environment Variables

| Переменная | Описание | Пример |
|------------|----------|--------|
| `SUPABASE_URL` | URL Supabase проекта | `https://xxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Анонимный ключ | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `ENVIRONMENT` | Окружение | `test`, `development`, `staging` |
| `LOG_LEVEL` | Уровень логирования | `debug`, `info`, `warn`, `error` |

## 📈 CI/CD

### GitHub Actions

Создайте `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: denoland/setup-deno@v1
        with:
          deno-version: v1.37
      - name: Run all tests
        run: deno test --coverage=coverage --allow-net --allow-env
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Git Hooks

Автоматическая установка хуков:

```bash
# Pre-commit: быстрые тесты + линтинг
# Pre-push: полные тесты + покрытие
```

### Автоматические проверки

- ✅ Code formatting
- ✅ Linting
- ✅ Type checking
- ✅ Unit tests
- ✅ Integration tests
- ✅ Coverage thresholds
- ✅ Security scan

## 📚 Документация

### Подробные руководства

- **[TESTING_GUIDE.md](TESTING_GUIDE.md)** - Полное руководство по тестированию
- **[API Reference](TESTING_GUIDE.md#api-reference)** - Справочник по API
- **[Best Practices](TESTING_GUIDE.md#best-practices)** - Лучшие практики
- **[Troubleshooting](TESTING_GUIDE.md#troubleshooting)** - Решение проблем

### Дополнительные ресурсы

- [Deno Testing Manual](https://deno.land/manual/testing)
- [Supabase Testing Guide](https://supabase.com/docs/guides/testing)
- [Edge Functions Documentation](https://deno.com/manual)

## 🎯 Метрики качества

### Покрытие тестами
- **Unit Tests**: 80%+ покрытие
- **Integration Tests**: 70%+ покрытие
- **E2E Tests**: Критические сценарии

### Производительность
- **Unit Tests**: < 1 сек
- **Integration Tests**: < 10 сек
- **E2E Tests**: < 30 сек

### Качество кода
- ✅ 0 ESLint ошибок
- ✅ 0 TypeScript ошибок
- ✅ 100% форматирование
- ✅ Security scan passed

## 🤝 Участие в разработке

### Как добавить тесты

1. **Выберите тип теста** (Unit/Integration/E2E)
2. **Создайте файл** в соответствующей директории
3. **Используйте моки** для изоляции
4. **Следуйте паттерну** Arrange-Act-Assert
5. **Проверьте покрытие** кода

### Пример добавления теста

```typescript
// tests/unit/my-feature.test.ts
import { createMockRequest, executeFunction } from "../utils/test-helpers.ts";
import { createTestUser } from "../fixtures/test-data.ts";

Deno.test("My Feature - Unit Test", async () => {
  // Arrange
  const testData = createTestUser();
  const request = createMockRequest("/my-feature", "POST", {}, testData);
  
  // Act
  const response = await executeFunction(
    "../../supabase/functions/my-feature/index.ts",
    "handler",
    request
  );
  
  // Assert
  assertEquals(response.status, 200);
  const result = await response.json();
  assertEquals(result.success, true);
});
```

## 🏆 Заключение

Данная тестовая инфраструктура обеспечивает:

- ✅ **Полное покрытие** тестированием всех компонентов
- ✅ **Автоматизированные проверки** качества кода
- ✅ **Интеграцию с CI/CD** для непрерывного тестирования
- ✅ **Профилирование производительности** и оптимизацию
- ✅ **Безопасность** через автоматические проверки
- ✅ **Документированные** процессы и лучшие практики

---

**🚀 Готово к использованию!** Начните с запуска `deno test` и добавления первого теста! 🧪✨

## ️ Архитектура

TODO: Добавить содержание раздела.


## ️ Конфигурация

TODO: Добавить содержание раздела.
