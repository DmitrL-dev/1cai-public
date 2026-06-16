# Руководство по тестированию

## Обзор

Данное руководство описывает подходы и стандарты тестирования для проекта AI Assistants для 1C. Мы используем многоуровневую стратегию тестирования для обеспечения качества и надежности системы.

## Содержание

- [Настройка тестового окружения](#настройка-тестового-окружения)
- [Структура тестов](#структура-тестов)
- [Запуск тестов](#запуск-тестов)
- [Написание тестов](#написание-тестов)
- [Best Practices](#best-practices)
- [Coverage требования](#coverage-требования)
- [CI/CD интеграция](#cicd-интеграция)

## Настройка тестового окружения

### Необходимые зависимости

Для полноценного тестирования необходимо установить следующие пакеты:

```bash
# Основные тестовые библиотеки
pnpm add -D vitest @vitest/ui jsdom
pnpm add -D @testing-library/react @testing-library/jest-dom
pnpm add -D @testing-library/user-event

# Типы и утилиты
pnpm add -D @types/testing-library__jest-dom
pnpm add -D happy-dom

# E2E тестирование
pnpm add -D @playwright/test

# Покрытие кода
pnpm add -D @vitest/coverage-v8
```

### Конфигурация Vitest

Создайте файл `vitest.config.ts` в корне проекта:

```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/coverage/**',
        'dist/'
      ]
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

### Настройка тестового окружения

Создайте файл `src/test/setup.ts`:

```typescript
import '@testing-library/jest-dom'

// Глобальные настройки для тестов
beforeAll(() => {
  // Инициализация тестового окружения
})

afterEach(() => {
  // Очистка после каждого теста
  jest.clearAllMocks()
})

afterAll(() => {
  // Финальная очистка
})
```

## Структура тестов

### Организация файлов

```
tests/
├── unit/               # Модульные тесты
│   ├── components/     # Тесты компонентов React
│   ├── hooks/         # Тесты хуков
│   ├── services/      # Тесты сервисов
│   └── utils/         # Тесты утилит
├── integration/       # Интеграционные тесты
│   ├── api/          # Тесты API
│   ├── pages/        # Тесты страниц
│   └── workflows/    # Тесты бизнес-процессов
├── e2e/              # End-to-End тесты
│   ├── auth/         # Тесты аутентификации
│   ├── navigation/   # Тесты навигации
│   └── scenarios/    # Пользовательские сценарии
└── fixtures/         # Тестовые данные
```

### Конвенции именования

- **Файлы тестов**: `*.test.ts` или `*.test.tsx` для unit-тестов
- **Спецификации**: `*.spec.ts` или `*.spec.tsx` как альтернатива
- **E2E тесты**: `*.e2e.ts` или в папке `e2e/`
- **Фикстуры**: `*.fixture.ts` или в папке `fixtures/`

### Пример структуры теста компонента

```typescript
// tests/unit/components/AssistantPanel.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AssistantPanel } from '@/components/AssistantPanel'
import { MockAssistantProvider } from '@/test/mocks/AssistantProvider'

describe('AssistantPanel', () => {
  const defaultProps = {
    assistantId: 'test-assistant',
    onMessage: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should render assistant interface', () => {
    render(
      <MockAssistantProvider>
        <AssistantPanel {...defaultProps} />
      </MockAssistantProvider>
    )

    expect(screen.getByTestId('assistant-panel')).toBeInTheDocument()
  })

  it('should handle user input', async () => {
    const user = userEvent.setup()
    const onMessage = jest.fn()

    render(
      <MockAssistantProvider>
        <AssistantPanel {...defaultProps} onMessage={onMessage} />
      </MockAssistantProvider>
    )

    const input = screen.getByPlaceholderText('Введите сообщение...')
    await user.type(input, 'Hello Assistant')
    
    const sendButton = screen.getByRole('button', { name: /отправить/i })
    await user.click(sendButton)

    await waitFor(() => {
      expect(onMessage).toHaveBeenCalledWith('Hello Assistant')
    })
  })

  it('should display error message on failure', async () => {
    const mockError = new Error('Assistant unavailable')
    const onMessage = jest.fn().mockRejectedValue(mockError)

    render(
      <MockAssistantProvider>
        <AssistantPanel {...defaultProps} onMessage={onMessage} />
      </MockAssistantProvider>
    )

    const input = screen.getByPlaceholderText('Введите сообщение...')
    const user = userEvent.setup()
    await user.type(input, 'Test message')
    await user.click(screen.getByRole('button', { name: /отправить/i }))

    await waitFor(() => {
      expect(screen.getByText(/assistant unavailable/i)).toBeInTheDocument()
    })
  })
})
```

## Запуск тестов

### Основные команды

```bash
# Запуск всех тестов
pnpm test

# Запуск тестов в watch режиме
pnpm test:watch

# Запуск с покрытием кода
pnpm test:coverage

# Запуск конкретного теста
pnpm test AssistantPanel

# Запуск в CI режиме
pnpm test:ci

# E2E тесты
pnpm test:e2e

# E2E тесты в headed режиме
pnpm test:e2e:ui
```

### Интеграция с npm скриптами

Добавьте в `package.json`:

```json
{
  "scripts": {
    "test": "vitest",
    "test:watch": "vitest --watch",
    "test:coverage": "vitest --coverage",
    "test:ci": "vitest --run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:all": "pnpm test:ci && pnpm test:e2e"
  }
}
```

## Написание тестов

### Unit тесты

#### Тестирование компонентов React

```typescript
// Используйте Testing Library для тестирования компонентов
import { render, screen, fireEvent } from '@testing-library/react'
import { Button } from './Button'

describe('Button', () => {
  it('should render with correct text', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
  })

  it('should call onClick when clicked', () => {
    const handleClick = jest.fn()
    render(<Button onClick={handleClick}>Click me</Button>)
    
    fireEvent.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })
})
```

#### Тестирование хуков

```typescript
import { renderHook, act } from '@testing-library/react'
import { useAssistant } from './useAssistant'

describe('useAssistant', () => {
  it('should manage assistant state', async () => {
    const { result } = renderHook(() => useAssistant('test-id'))

    expect(result.current.isLoading).toBe(false)

    act(() => {
      result.current.sendMessage('Hello')
    })

    expect(result.current.isLoading).toBe(true)
  })
})
```

#### Тестирование сервисов

```typescript
import { assistantService } from './assistantService'

describe('assistantService', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should send message to assistant', async () => {
    const mockResponse = { message: 'Hello!', timestamp: Date.now() }
    jest.spyOn(assistantService, 'sendMessage').mockResolvedValue(mockResponse)

    const result = await assistantService.sendMessage('test-id', 'Hello')

    expect(result).toEqual(mockResponse)
  })

  it('should handle network errors', async () => {
    const networkError = new Error('Network error')
    jest.spyOn(assistantService, 'sendMessage').mockRejectedValue(networkError)

    await expect(assistantService.sendMessage('test-id', 'Hello'))
      .rejects.toThrow('Network error')
  })
})
```

### Integration тесты

#### Тестирование API

```typescript
import { setupServer } from 'msw/node'
import { rest } from 'msw'
import { render, screen, waitFor } from '@testing-library/react'
import { AssistantPage } from '@/pages/AssistantPage'

const server = setupServer(
  rest.get('/api/assistants/:id', (req, res, ctx) => {
    return res(
      ctx.json({
        id: 'test-id',
        name: 'Test Assistant',
        status: 'active'
      })
    )
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('Assistant API integration', () => {
  it('should load assistant data from API', async () => {
    render(<AssistantPage assistantId="test-id" />)

    await waitFor(() => {
      expect(screen.getByText('Test Assistant')).toBeInTheDocument()
    })
  })
})
```

### E2E тесты

#### Пользовательские сценарии

```typescript
// tests/e2e/assistant-workflow.e2e.ts
import { test, expect } from '@playwright/test'

test.describe('Assistant Workflow', () => {
  test('should complete full assistant interaction', async ({ page }) => {
    // Переход на страницу
    await page.goto('/assistants/demo')

    // Проверка загрузки интерфейса
    await expect(page.locator('[data-testid=assistant-panel]')).toBeVisible()

    // Отправка сообщения
    await page.fill('[data-testid=message-input]', 'Привет! Как дела?')
    await page.click('[data-testid=send-button]')

    // Ожидание ответа
    await expect(page.locator('[data-testid=assistant-message]')).toContainText('Привет!')

    // Проверка истории сообщений
    await expect(page.locator('[data-testid=chat-history]')).toContainText('Привет! Как дела?')
  })

  test('should handle authentication', async ({ page }) => {
    await page.goto('/login')
    await page.fill('[name=email]', 'test@example.com')
    await page.fill('[name=password]', 'password123')
    await page.click('[type=submit]')

    await expect(page).toHaveURL('/dashboard')
    await expect(page.locator('[data-testid=user-menu]')).toBeVisible()
  })
})
```

## Best Practices

### Принципы тестирования

1. **Тестируйте поведение, а не реализацию**
   - Фокусируйтесь на том, что делает компонент, а не как он это делает
   - Избегайте тестирования внутренних деталей реализации

2. **Один тест - одна концепция**
   - Каждый тест должен проверять только одну функциональность
   - Используйте `describe` для группировки связанных тестов

3. **Изоляция тестов**
   - Каждый тест должен быть независимым
   - Используйте `beforeEach` для настройки и `afterEach` для очистки

4. **Достоверные тесты (Realistic Tests)**
   - Используйте реалистичные данные в тестах
   - Избегайте хардкодинга значений

### Mocking guidelines

```typescript
// Хорошо: мокайте только внешние зависимости
jest.mock('@/services/assistantService', () => ({
  assistantService: {
    sendMessage: jest.fn(),
    getAssistant: jest.fn(),
  }
}))

// Хорошо: используйте моки для API вызовов
const mockResponse = {
  id: 'test-id',
  name: 'Test Assistant',
  messages: []
}

// Плохо: не мокайте React компоненты
// jest.mock('react', () => ({
//   useState: jest.fn(),
//   useEffect: jest.fn(),
// }))
```

### Тестовые данные

```typescript
// tests/fixtures/assistants.ts
export const mockAssistants = {
  architect: {
    id: 'architect-assistant',
    name: 'Архитектор 1C',
    type: 'architect',
    capabilities: ['system_design', 'code_review'],
    isActive: true,
  },
  developer: {
    id: 'developer-assistant',
    name: 'Разработчик 1C',
    type: 'developer',
    capabilities: ['code_generation', 'debugging'],
    isActive: true,
  },
}

export const createMockAssistant = (overrides = {}) => ({
  ...mockAssistants.architect,
  ...overrides,
})
```

### Accessibility тестирование

```typescript
import { axe, toHaveNoViolations } from 'jest-axe'

expect.extend(toHaveNoViolations)

it('should not have accessibility violations', async () => {
  const { container } = render(<AssistantPanel {...props} />)
  const results = await axe(container)
  expect(results).toHaveNoViolations()
})
```

## Coverage требования

### Цели покрытия

- **Общее покрытие**: не менее 80%
- **Критические компоненты**: не менее 90%
- **Утилиты и хелперы**: не менее 95%
- **API сервисы**: не менее 85%

### Отчеты по покрытию

Генерируйте отчеты после запуска тестов:

```bash
pnpm test:coverage
```

Отчет будет сохранен в папке `coverage/` и доступен через браузер.

### Мониторинг покрытия

Используйте GitHub Actions для автоматической проверки покрытия:

```yaml
# .github/workflows/test-coverage.yml
name: Test Coverage
on: [push, pull_request]

jobs:
  coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: pnpm install
      - run: pnpm test:coverage
      - uses: codecov/codecov-action@v3
        with:
          fail_ci_if_error: true
```

## CI/CD интеграция

### Автоматический запуск тестов

Все тесты запускаются автоматически при:
- Создании Pull Request
- Push в main ветку
- Ежедневно в 02:00 UTC

### Качество кода

Перед merge в main ветку требуется:
- ✅ Все тесты проходят
- ✅ Покрытие кода не менее 80%
- ✅ Нет критических ошибок в ESLint
- ✅ Прохождение E2E тестов
- ✅ Accessibility проверки

### Отчеты

После каждого прогона тестов автоматически генерируются:
- Отчет о покрытии кода
- Результаты E2E тестов
- Performance метрики
- Accessibility аудит

## Полезные ссылки

- [Vitest Documentation](https://vitest.dev/)
- [Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Playwright Documentation](https://playwright.dev/)
- [React Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

## Поддержка

Если у вас есть вопросы по тестированию:
1. Обратитесь к этому руководству
2. Проверьте примеры в папке `tests/`
3. Создайте issue с меткой `testing`
4. Обратитесь к команде разработки
