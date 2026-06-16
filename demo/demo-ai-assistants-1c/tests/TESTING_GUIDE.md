# Тестовая инфраструктура для Deno Edge Functions

Полная тестовая инфраструктура для разработки и тестирования Deno Edge Functions в проекте demo-ai-assistants-1c.

## 📁 Структура проекта

```
tests/
├── unit/                  # Unit тесты (изоляция компонентов)
├── integration/          # Интеграционные тесты (взаимодействие компонентов)
├── e2e/                  # End-to-End тесты (полные пользовательские сценарии)
├── mocks/                # Моки и заглушки
├── utils/                # Вспомогательные функции
├── fixtures/             # Тестовые данные
├── config/               # Конфигурация тестов
└── .gitignore           # Игнорируемые файлы
```

## 🚀 Быстрый старт

### Установка зависимостей

```bash
# Установка Deno (если не установлен)
curl -fsSL https://deno.land/install.sh | sh

# Или через пакетный менеджер
brew install deno  # macOS
choco install deno # Windows
```

### Запуск тестов

```bash
# Все тесты
deno test

# Только unit тесты
deno test tests/unit/**/*.test.ts

# Только integration тесты
deno test tests/integration/**/*.test.ts

# Только e2e тесты
deno test tests/e2e/**/*.test.ts

# С покрытием кода
deno test --coverage=coverage

# С отчетом
deno test --coverage=coverage --coverage-include='supabase/functions/**/*'
```

### Настройка окружения

1. Создайте переменные окружения:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
STRIPE_SECRET_KEY=sk_test_...
```

## 🛠 Конфигурация

### deno.jsonc

Основной файл конфигурации Deno с настройками:
- **Test**: Настройки выполнения тестов
- **Lint**: Правила линтинга
- **Fmt**: Форматирование кода
- **Tasks**: Готовые команды для запуска

### tests/config/test.config.ts

Файл конфигурации тестового окружения:
- Настройки таймаутов
- Конфигурация моков
- Настройки покрытия кода
- Управление окружениями (dev/test/prod)

## 🧪 Типы тестов

### Unit Tests (`tests/unit/`)

Тестирование отдельных компонентов в изоляции:

```typescript
// Пример unit теста
Deno.test("User creation", async () => {
  const userData = createTestUser();
  const request = createMockRequest("/users", "POST", {}, userData);
  
  const response = await executeFunction(functionPath, "handler", request);
  
  assertEquals(response.status, 201);
  const result = await response.json();
  assertEquals(result.email, userData.email);
});
```

**Цели:**
- Проверка бизнес-логики
- Валидация входных данных
- Обработка ошибок
- Производительность

### Integration Tests (`tests/integration/`)

Тестирование взаимодействия между компонентами:

```typescript
// Пример integration теста
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

**Цели:**
- Проверка API интеграций
- Взаимодействие с базой данных
- Интеграция с внешними сервисами
- Сквозные сценарии

### End-to-End Tests (`tests/e2e/`)

Полные пользовательские сценарии:

```typescript
// Пример e2e теста
Deno.test("Complete purchase journey", async (t) => {
  // 1. Регистрация пользователя
  const user = await registerTestUser();
  
  // 2. Просмотр каталога
  const catalog = await browseCatalog();
  
  // 3. Добавление в корзину
  await addToCart(productId, quantity);
  
  // 4. Оформление заказа
  const order = await createOrder(orderData);
  
  // 5. Оплата
  const payment = await processPayment(paymentData);
  
  // 6. Подтверждение
  await sendConfirmationEmail(order.id);
});
```

**Цели:**
- Полные пользовательские сценарии
- Тестирование всей цепочки событий
- Проверка бизнес-процессов
- Валидация пользовательского опыта

## 🔧 Вспомогательные инструменты

### Моки (tests/mocks/)

#### Supabase мок (`tests/mocks/supabase.ts`)
- Мок Supabase клиента
- Имитация базы данных
- Поддержка CRUD операций
- Готовые тестовые данные

```typescript
// Использование мока Supabase
const mockSupabase = createMockSupabaseClient();
const user = createTestUser({ email: "test@example.com" });

// Симуляция запроса к БД
const result = await mockSupabase
  .from('users')
  .insert(user)
  .select()
  .single();
```

#### HTTP мок (`tests/mocks/requests.ts`)
- Мок HTTP запросов
- Имитация внешних API
- Поддержка различных статусов ответов
- Проверка вызовов

```typescript
// Установка HTTP моков
installMockFetch();
setupApiHandlers();

// Проверка HTTP запросов
expectRequest("https://api.example.com/users", "POST", userData);
```

### Утилиты (tests/utils/)

#### Test Helpers (`tests/utils/test-helpers.ts`)
- Создание тестовых данных
- Функции проверки (assertions)
- Профилировщик производительности
- Управление окружением

```typescript
// Использование утилит
const user = generateUser();
const request = createMockRequest(url, method, headers, body);

const startTime = performance.now();
// Выполнение функции
const responseTime = performance.now() - startTime;
assert(responseTime < 100, "Response too slow");
```

### Фикстуры (tests/fixtures/)

Готовые тестовые данные:
- `userFixtures` - Пользователи разных типов
- `productFixtures` - Товары различных категорий  
- `orderFixtures` - Заказы в разных статусах
- `paymentFixtures` - Платежи с разными исходами

```typescript
// Использование фикстур
const basicUser = userFixtures.basic;
const electronicsProduct = productFixtures.electronics;
const paidOrder = orderFixtures.paid;
```

## 📊 Покрытие кода

### Настройка

В `deno.jsonc` настроено покрытие кода:

```json
{
  "test": {
    "coverage": {
      "include": ["supabase/functions/**/*"],
      "exclude": ["**/*.d.ts", "**/*.test.ts"],
      "reportDir": "coverage",
      "type": "html"
    }
  }
}
```

### Минимальные пороги

- **Statements**: 80%
- **Branches**: 70%
- **Functions**: 80%  
- **Lines**: 80%

### Просмотр отчета

```bash
# Генерация отчета
deno test --coverage=coverage

# Открытие HTML отчета
open coverage/index.html  # macOS
start coverage/index.html # Windows
```

## 🔒 Безопасность

### Проверки безопасности

- **SQL Injection**: Валидация входных данных
- **XSS Prevention**: Экранирование выходных данных
- **Authentication**: Проверка токенов
- **Authorization**: Проверка прав доступа

### Тестовые данные

- Используйте только тестовые данные
- Не включайте реальные персональные данные
- Регулярно очищайте тестовые базы данных

## 🚀 CI/CD интеграция

### GitHub Actions пример

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: denoland/setup-deno@v1
        with:
          deno-version: v1.37
      - name: Run tests
        run: deno test --coverage=coverage
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Запуск в CI

```bash
# В CI среде
export ENVIRONMENT=test
export SUPABASE_URL=${{ secrets.SUPABASE_URL }}
export SUPABASE_ANON_KEY=${{ secrets.SUPABASE_ANON_KEY }}

deno test --coverage=coverage --allow-net
```

## 📈 Мониторинг и отладка

### Логирование

Включите подробное логирование для разработки:

```typescript
// В тестовом окружении
setEnv({ LOG_LEVEL: "debug" });
```

### Профилирование

```typescript
// Измерение производительности
PerformanceProfiler.start("function-execution");
await executeFunction(...);
PerformanceProfiler.end("function-execution");

// Просмотр отчета
const report = PerformanceProfiler.getReport();
console.log(report);
```

### Отладка моков

```typescript
// Включение трассировки HTTP запросов
mockFetchService.onRequest((url, method) => {
  console.log(`HTTP ${method} ${url}`);
});

// Проверка вызовов
const requests = mockFetchService.getRequests();
console.log(requests);
```

## 📝 Лучшие практики

### Организация тестов

1. **Один файл = одна функциональность**
2. **Группируйте связанные тесты в describe блоки**
3. **Используйте описательные имена тестов**
4. **Следуйте паттерну Arrange-Act-Assert**

### Производительность

1. **Запускайте быстрые тесты первыми**
2. **Используйте параллельное выполнение**
3. **Кэшируйте модули**
4. **Очищайте ресурсы после тестов**

### Надежность

1. **Изолируйте тесты друг от друга**
2. **Используйте фикстуры для тестовых данных**
3. **Обрабатывайте асинхронные операции корректно**
4. **Проверяйте граничные случаи**

## 🆘 Решение проблем

### Частые ошибки

**Ошибка: Module not found**
```bash
# Убедитесь, что пути корректны
import { testHelper } from "../utils/test-helpers.ts";
```

**Ошибка: Timeout exceeded**
```typescript
// Увеличьте таймаут для интеграционных тестов
Deno.test({
  name: "Long running test",
  timeout: 60000, // 1 минута
  async fn() {
    // Ваш тест
  }
});
```

**Ошибка: Network request failed**
```typescript
// Убедитесь, что моки настроены
installMockFetch();
setupApiHandlers();
```

### Отладка

```bash
# Запуск с подробными логами
deno test --log-level debug

# Запуск одного теста
deno test tests/unit/specific.test.ts

# Режим наблюдения (autoreload)
deno test --watch
```

## 📚 Дополнительные ресурсы

- [Deno Testing Guide](https://deno.land/manual/testing)
- [Supabase Testing Best Practices](https://supabase.com/docs/guides/testing)
- [Edge Functions Documentation](https://deno.com/manual)
- [Testing Assertions Reference](https://deno.land/std/testing)

## 🤝 Участие в разработке

1. Создавайте тесты для новой функциональности
2. Поддерживайте высокое покрытие кода (≥80%)
3. Регулярно обновляйте фикстуры
4. Документируйте сложные тестовые сценарии

---

**Важно**: Всегда запускайте тесты перед пушем кода и следите за покрытием! 🧪✨