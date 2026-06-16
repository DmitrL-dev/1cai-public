# Структура тестов

## Обзор

Данная директория содержит все тесты для проекта AI Assistants для 1C. Тесты организованы по типам и следуют лучшим практикам тестирования современных React приложений.

## Структура директорий

```
tests/
├── unit/                   # Модульные тесты
│   ├── components/         # Тесты React компонентов
│   │   ├── AssistantPanel.test.tsx
│   │   ├── ChatInterface.test.tsx
│   │   └── NavigationMenu.test.tsx
│   ├── hooks/             # Тесты custom hooks
│   │   ├── useAssistant.test.ts
│   │   ├── useAuth.test.ts
│   │   └── useLocalStorage.test.ts
│   ├── services/          # Тесты сервисов
│   │   ├── AssistantService.test.ts
│   │   ├── APIService.test.ts
│   │   └── AuthService.test.ts
│   └── utils/             # Тесты утилитарных функций
│       ├── formatters.test.ts
│       └── validators.test.ts
├── integration/           # Интеграционные тесты
│   ├── api/              # Тесты интеграции с API
│   │   ├── assistant-endpoints.test.ts
│   │   └── auth-endpoints.test.ts
│   ├── pages/            # Тесты страниц
│   │   ├── DashboardPage.test.tsx
│   │   └── AssistantPage.test.tsx
│   └── workflows/        # Тесты бизнес-процессов
│       ├── user-onboarding.test.ts
│       └── assistant-workflow.test.ts
├── e2e/                   # End-to-End тесты
│   ├── auth/             # Тесты аутентификации
│   │   ├── login.spec.ts
│   │   └── logout.spec.ts
│   ├── navigation/       # Тесты навигации
│   │   ├── main-navigation.spec.ts
│   │   └── breadcrumb.spec.ts
│   ├── scenarios/        # Пользовательские сценарии
│   │   ├── assistant-interaction.spec.ts
│   │   └── dashboard-usage.spec.ts
│   └── support/          # Вспомогательные файлы для E2E
│       ├── fixtures.ts
│       └── helpers.ts
└── fixtures/             # Тестовые данные
    ├── mock-assistants.ts
    ├── mock-responses.ts
    └── test-users.ts
```

## Конвенции именования

### Файлы тестов

- **Unit тесты**: `*.test.ts` или `*.test.tsx`
- **Спецификации**: `*.spec.ts` или `*.spec.tsx` (альтернативный формат)
- **E2E тесты**: `*.spec.ts` в папке `e2e/`
- **Фикстуры**: `*.ts` в папке `fixtures/`
- **Вспомогательные**: `*.helper.ts` или `*.util.ts`

### Именование тестов

```typescript
// Хорошо: Описательное имя, отражающее поведение
describe('AssistantPanel', () => {
  it('should display loading state while fetching assistant data')
  it('should handle user input and send message to assistant')
  it('should show error message when assistant is unavailable')
})

// Плохо: Неясные имена
describe('AssistantPanel', () => {
  it('test 1')
  it('should work correctly')
})
```

### Именование тестовых функций

```typescript
// Используйте:
- describe() для группировки связанных тестов
- it() для отдельных test cases
- test() как альтернатива it()

// Пример:
describe('AssistantService', () => {
  describe('sendMessage', () => {
    it('should send message to correct assistant', async () => {
      // тест
    })
  })
})
```

## Типы тестов

### 1. Unit тесты

#### Цель
Тестирование отдельных функций, компонентов или модулей в изоляции.

#### Когда использовать
- Компоненты React
- Custom hooks
- Утилитарные функции
- Сервисы (с моками зависимостей)

#### Пример компонента

```typescript
// tests/unit/components/AssistantPanel.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
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
    
    render(
      <MockAssistantProvider>
        <AssistantPanel {...defaultProps} />
      </MockAssistantProvider>
    )

    const input = screen.getByPlaceholderText('Введите сообщение...')
    await user.type(input, 'Hello Assistant')
    await user.click(screen.getByRole('button', { name: /отправить/i }))

    expect(defaultProps.onMessage).toHaveBeenCalledWith('Hello Assistant')
  })
})
```

#### Пример хука

```typescript
// tests/unit/hooks/useAssistant.test.ts
import { renderHook, act } from '@testing-library/react'
import { useAssistant } from '@/hooks/useAssistant'

describe('useAssistant', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('should manage assistant state', async () => {
    const { result } = renderHook(() => useAssistant('test-id'))

    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()

    act(() => {
      result.current.sendMessage('Hello')
    })

    expect(result.current.isLoading).toBe(true)

    // Дождитесь завершения асинхронной операции
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0))
    })

    expect(result.current.isLoading).toBe(false)
  })
})
```

### 2. Integration тесты

#### Цель
Тестирование взаимодействия между компонентами, модулями или внешними сервисами.

#### Когда использовать
- Интеграция между компонентами
- API endpoints
- Пользовательские workflows
- Database операции (с test database)

#### Пример API теста

```typescript
// tests/integration/api/assistant-endpoints.test.ts
import { setupServer } from 'msw/node'
import { rest } from 'msw'

const server = setupServer(
  rest.get('/api/assistants/:id', (req, res, ctx) => {
    return res(
      ctx.json({
        id: req.params.id,
        name: 'Test Assistant',
        status: 'active',
        capabilities: ['chat', 'code_generation']
      })
    )
  }),

  rest.post('/api/assistants/:id/messages', (req, res, ctx) => {
    return res(
      ctx.json({
        message: 'Hello! How can I help you?',
        timestamp: Date.now()
      })
    )
  })
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('Assistant API Integration', () => {
  it('should fetch and display assistant data', async () => {
    const { getAssistant } = await import('@/services/AssistantService')
    
    const assistant = await getAssistant('test-id')
    
    expect(assistant).toEqual({
      id: 'test-id',
      name: 'Test Assistant',
      status: 'active',
      capabilities: ['chat', 'code_generation']
    })
  })
})
```

#### Пример workflow теста

```typescript
// tests/integration/workflows/user-onboarding.test.ts
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { OnboardingFlow } from '@/components/OnboardingFlow'
import { createTestUser } from '@/test/fixtures/test-users'

describe('User Onboarding Workflow', () => {
  it('should complete full onboarding process', async () => {
    const user = userEvent.setup()
    
    render(<OnboardingFlow />)

    // Step 1: Welcome
    expect(screen.getByText('Добро пожаловать!')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Начать' }))

    // Step 2: Profile setup
    await waitFor(() => {
      expect(screen.getByText('Настройте ваш профиль')).toBeInTheDocument()
    })

    const nameInput = screen.getByLabelText('Имя')
    const emailInput = screen.getByLabelText('Email')
    
    await user.type(nameInput, 'Test User')
    await user.type(emailInput, 'test@example.com')
    await user.click(screen.getByRole('button', { name: 'Продолжить' }))

    // Step 3: Preferences
    await waitFor(() => {
      expect(screen.getByText('Выберите предпочтения')).toBeInTheDocument()
    })

    const notificationsCheckbox = screen.getByLabelText('Уведомления')
    await user.click(notificationsCheckbox)
    await user.click(screen.getByRole('button', { name: 'Завершить' }))

    // Final: Dashboard
    await waitFor(() => {
      expect(screen.getByText('Добро пожаловать в панель управления')).toBeInTheDocument()
    })
  })
})
```

### 3. E2E тесты

#### Цель
Тестирование полных пользовательских сценариев в реальном браузере.

#### Когда использовать
- Критические пользовательские пути
- Интеграция с внешними сервисами
- Кросс-браузерное тестирование
- Performance тестирование

#### Пример E2E теста

```typescript
// tests/e2e/scenarios/assistant-interaction.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Assistant Interaction', () => {
  test.beforeEach(async ({ page }) => {
    // Авторизация перед каждым тестом
    await page.goto('/login')
    await page.fill('[name=email]', 'test@example.com')
    await page.fill('[name=password]', 'password123')
    await page.click('[type=submit]')
    await expect(page).toHaveURL('/dashboard')
  })

  test('should interact with architect assistant', async ({ page }) => {
    // Переход к ассистенту
    await page.click('[data-testid=architect-assistant-card]')
    await expect(page).toHaveURL('/assistants/architect')

    // Отправка сообщения
    await page.fill('[data-testid=message-input]', 'Создай архитектуру системы для CRM')
    await page.click('[data-testid=send-button]')

    // Проверка отправки
    await expect(page.locator('[data-testid=message-list]')).toContainText('Создай архитектуру системы для CRM')

    // Ожидание ответа ассистента
    await expect(page.locator('[data-testid=assistant-message]')).toContainText('Архитектура системы')

    // Проверка истории
    const messageCount = await page.locator('[data-testid=message-item]').count()
    expect(messageCount).toBeGreaterThan(1)
  })

  test('should switch between assistants', async ({ page }) => {
    // Начать с архитектора
    await page.click('[data-testid=architect-assistant-card]')
    await page.fill('[data-testid=message-input]', 'Привет архитектор!')
    await page.click('[data-testid=send-button]')

    // Переключиться на разработчика
    await page.click('[data-testid=developer-assistant-card]')
    await page.fill('[data-testid=message-input]', 'Привет разработчик!')
    await page.click('[data-testid=send-button]')

    // Проверить переключение
    await expect(page.locator('[data-testid=current-assistant]')).toContainText('Разработчик')
    
    // Проверить что контекст не пересекается
    const architectMessages = await page.locator('[data-testid="assistant-message"]').count()
    expect(architectMessages).toBe(0)
  })
})
```

## Mock usage guidelines

### 1. Когда использовать моки

✅ **Используйте моки для:**
- Внешние API вызовы
- Browser APIs (localStorage, sessionStorage)
- Third-party библиотеки
- Database операции
- Complex asynchronous operations

❌ **Не используйте моки для:**
- React компоненты (тестируйте их реально)
- Внутренние функции вашего кода
- Простые utility функции
- State management (если возможно)

### 2. Мокирование API

```typescript
// Хорошо: Мокайте только внешние API
jest.mock('@/services/assistantService', () => ({
  assistantService: {
    sendMessage: jest.fn(),
    getAssistant: jest.fn(),
    getHistory: jest.fn(),
  }
}))

// Использование в тесте
beforeEach(() => {
  jest.clearAllMocks()
})

it('should handle API response', async () => {
  const mockResponse = { message: 'Hello!', timestamp: Date.now() }
  ;(assistantService.sendMessage as jest.Mock).mockResolvedValue(mockResponse)

  // Тестирование логики, которая использует API
})
```

### 3. Мокирование компонентов

```typescript
// Избегайте этого подхода
jest.mock('@/components/HeavyComponent', () => ({
  HeavyComponent: () => <div data-testid="mocked-component">Mocked</div>
}))

// Лучше используйте Dependency Injection
const HeavyComponent = lazy(() => import('@/components/HeavyComponent'))

// Или тестируйте с реальным компонентом, но с моками его зависимостей
jest.mock('@/services/dataService', () => ({
  dataService: {
    getData: jest.fn().mockResolvedValue([])
  }
}))
```

### 4. Мокирование browser APIs

```typescript
// Мокирование localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
})

// Использование в тесте
beforeEach(() => {
  localStorageMock.getItem.mockClear()
  localStorageMock.setItem.mockClear()
})
```

## Тестовые данные и фикстуры

### 1. Создание фикстур

```typescript
// tests/fixtures/mock-assistants.ts
export const mockAssistants = {
  architect: {
    id: 'architect-assistant',
    name: 'Архитектор 1C',
    type: 'architect',
    status: 'active',
    capabilities: ['system_design', 'architecture_review', 'best_practices'],
    avatar: '/images/architect-avatar.png',
    description: 'Помогает с проектированием архитектуры 1C систем',
  },
  developer: {
    id: 'developer-assistant',
    name: 'Разработчик 1C',
    type: 'developer',
    status: 'active',
    capabilities: ['code_generation', 'debugging', 'optimization'],
    avatar: '/images/developer-avatar.png',
    description: 'Помогает с разработкой и отладкой 1C кода',
  },
}

export const createMockAssistant = (overrides = {}) => ({
  ...mockAssistants.architect,
  ...overrides,
})

export const mockMessage = {
  id: 'msg-123',
  content: 'Привет! Как дела?',
  sender: 'user',
  timestamp: Date.now(),
  assistantId: 'test-assistant',
}
```

### 2. Factory функции

```typescript
// tests/fixtures/factories.ts
export const createMockUser = (overrides = {}) => ({
  id: 'user-123',
  email: 'test@example.com',
  name: 'Test User',
  role: 'developer',
  preferences: {
    theme: 'light',
    language: 'ru',
  },
  ...overrides,
})

export const createMockChatSession = (overrides = {}) => ({
  id: 'session-123',
  assistantId: 'architect-assistant',
  messages: [],
  startedAt: Date.now(),
  ...overrides,
})
```

## Тестовые утилиты

### 1. Custom render функция

```typescript
// tests/test-utils/render.tsx
import { render, RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { AssistantProvider } from '@/contexts/AssistantContext'
import { ThemeProvider } from '@/contexts/ThemeContext'

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <BrowserRouter>
      <AssistantProvider>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </AssistantProvider>
    </BrowserRouter>
  )
}

const customRender = (
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
```

### 2. Test hooks

```typescript
// tests/test-utils/hooks.ts
import { renderHook, RenderHookOptions } from '@testing-library/react'

export const renderHookWithProviders = <TProps, TResult>(
  hook: (props: TProps) => TResult,
  options?: RenderHookOptions<TProps>
) => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <BrowserRouter>
      <AssistantProvider>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </AssistantProvider>
    </BrowserRouter>
  )

  return renderHook(hook, { wrapper, ...options })
}
```

## Запуск тестов

### Команды

```bash
# Все тесты
pnpm test

# Watch режим
pnpm test:watch

# Покрытие кода
pnpm test:coverage

# E2E тесты
pnpm test:e2e

# E2E в UI режиме
pnpm test:e2e:ui

# Только изменившиеся тесты
pnpm test --changed

# Конкретный тест
pnpm test AssistantPanel

# Конкретный E2E тест
pnpm test:e2e assistant-interaction
```

### Отладка тестов

```typescript
// Включение debug output
it('should debug something', () => {
  console.log('Debug info:', someData)
  console.dir(someObject)
  // Тест продолжится
})
```

```typescript
// Debug с break
it('should debug with break', async () => {
  // Поставьте breakpoint здесь
  debugger
  
  // Код остановится в dev tools
  expect(something).toBeDefined()
})
```

## Continuous Integration

### Настройка в CI

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      - run: pnpm install
      - run: pnpm test:ci
      - run: pnpm test:e2e
      - uses: codecov/codecov-action@v3
```

### Coverage gates

```bash
# Установка минимального coverage
pnpm test:coverage --coverage.threshold.global=80

# Проверка coverage в CI
if pnpm test:coverage --silent; then
  echo "✅ Coverage requirements met"
else
  echo "❌ Coverage below 80%"
  exit 1
fi
```

## Дополнительные ресурсы

### Документация
- [Vitest Guide](https://vitest.dev/guide/)
- [Testing Library](https://testing-library.com/docs/)
- [Playwright](https://playwright.dev/)

### Лучшие практики
- [React Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Test-Driven Development](https://tddmanifesto.com/)
- [Testing Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)

### Поддержка команды
Если у вас есть вопросы по тестированию:
1. Проверьте этот README
2. Посмотрите примеры в соответствующих папках
3. Обратитесь к team lead
4. Создайте issue с меткой `testing`

---

## Тестирование Edge Functions

### Обзор

Проект содержит комплексную систему тестирования для 5 Edge Functions:
- `developer-demo` - Генерация кода 1С
- `architect-demo` - Проектирование архитектуры
- `ba-demo` - Бизнес-анализ
- `pm-demo` - Управление проектами
- `tester-demo` - Тестирование и QA

### Структура Edge Functions тестов

```
tests/
├── unit/functions/           # Unit тесты функций
│   └── developer-demo.test.ts
├── integration/functions/    # Интеграционные тесты
│   └── developer-demo-integration.test.ts
├── e2e/                      # End-to-end тесты
│   └── edge-functions-e2e.test.ts
├── fixtures/                 # Тестовые данные
│   ├── sampleRequests.ts     # Примеры запросов
│   └── mockData.ts           # Mock данные
├── jest.config.js           # Конфигурация Jest
├── setup.ts                 # Настройки тестового окружения
└── setup-deno.ts            # Настройки Deno совместимости
```

### Запуск Edge Functions тестов

```bash
# Все Edge Functions тесты
npm run test:functions

# Unit тесты
npm run test:unit

# Интеграционные тесты  
npm run test:integration

# E2E тесты
npm run test:e2e

# С покрытием
npm run test:coverage
```

### Конфигурация тестирования

Создайте `.env.test`:
```env
NODE_ENV=test
EDGE_FUNCTION_URL=http://localhost:54321/functions/v1
SUPABASE_URL=http://localhost:54321
SUPABASE_ANON_KEY=test-anon-key
SUPABASE_SERVICE_ROLE_KEY=test-service-role-key
```

### Примеры Edge Functions тестов

#### Unit тест функции

```typescript
// tests/unit/functions/developer-demo.test.ts
describe('DeveloperDemo', () => {
  it('должен обрабатывать валидный пользовательский запрос', async () => {
    const request: BaseRequest = {
      demoType: 'custom',
      userQuery: 'создать справочник товаров'
    };
    
    const result = await demoFunction.executeDemo(request);
    
    expect(result).toHaveProperty('steps');
    expect(result).toHaveProperty('finalResult');
    expect(result.steps[4].progress).toBe(100);
    expect(result.finalResult.language).toBe('1C');
  });
});
```

#### Интеграционный тест

```typescript
// tests/integration/functions/developer-demo-integration.test.ts
describe('Developer Demo Integration', () => {
  it('должен обрабатывать POST запрос через API', async () => {
    const requestData = {
      demoType: 'custom',
      userQuery: 'создать документ продажи'
    };
    
    const { response, data } = await tester.makeRequest('POST', requestData);
    
    expect(response.status).toBe(200);
    expect(data.data.steps).toHaveLength(5);
    expect(data.data.finalResult.code).toContain('Документ');
  });
});
```

#### E2E тест всех функций

```typescript
// tests/e2e/edge-functions-e2e.test.ts
DEMO_FUNCTIONS.forEach(functionName => {
  describe(`${functionName}`, () => {
    it('должен обрабатывать валидные запросы', async () => {
      const validRequest = E2E_TEST_DATA[functionName].validRequests[0];
      const { response } = await tester.testFunction(functionName, validRequest);
      
      expect(response.status).toBe(200);
    });
  });
});
```

### Тестовые сценарии

#### 1. Валидация запросов
- Корректные типы demoType
- Некорректные входные данные
- Отсутствующие обязательные поля
- Граничные случаи

#### 2. Генерация кода 1С
- Справочники (catalog)
- Документы (document)  
- Регистры накопления/сведений (register)
- Отчеты (report)
- Обработки (processing)

#### 3. Производительность
- Время отклика < 10 сек
- Потребление памяти < 100 MB
- Стабильность под нагрузкой

#### 4. CORS и безопасность
- CORS заголовки
- Rate limiting
- Обработка SQL инъекций
- XSS защита

### Debug Edge Functions тестов

```bash
# С подробными логами
DEBUG=* npm test:functions

# Конкретный тест
npx jest tests/unit/functions/developer-demo.test.ts --verbose

# Покрытие конкретной функции
npx jest --coverage --collectCoverageFrom="supabase/functions/developer-demo/index.ts"
```

### Известные проблемы

1. **Edge Function недоступна**: Тесты автоматически адаптируются и используют mock данные
2. **Deno API в Node.js**: Используются моки для совместимости
3. **Timeout настройки**: 
   - Общий: 30 секунд
   - E2E: 60 секунд
   - Настраивается через переменные окружения

### Метрики покрытия

- **Branches**: 70%
- **Functions**: 70%  
- **Lines**: 70%
- **Statements**: 70%

### Дополнительные ресурсы

- [Supabase Edge Functions](https://supabase.com/docs/guides/functions)
- [Deno Runtime](https://deno.land/)
- [Jest Testing](https://jestjs.io/docs/tutorial-async)
