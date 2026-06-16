import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './coverage/playwright',
  
  // Максимальное время на тест
  timeout: 30000,
  
  // Ожидания по умолчанию
  expect: {
    timeout: 10000,
  },
  
  // Запуск тестов параллельно
  fullyParallel: true,
  
  // Репортер для CI/CD
  reporter: [
    ['html'],
    ['json', { outputFile: './coverage/playwright/results.json' }],
    ['junit', { outputFile: './coverage/playwright/results.xml' }],
  ],
  
  // Глобальные настройки для всех тестов
  use: {
    // Базовая URL для относительных путей
    baseURL: 'http://localhost:4173',
    
    // Сбор данных для coverage
    contextOptions: {
      recordHar: {
        path: './coverage/playwright/har/page-load.har',
        omitContent: true,
      },
    },
    
    // Скриншоты при ошибках
    screenshot: 'only-on-failure',
    
    // Видео при ошибках
    video: 'retain-on-failure',
    
    // Трейсы при ошибках
    trace: 'retain-on-failure',
  },

  // Проекты для разных браузеров
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],

  // Локальный запуск веб-сервера для тестов
  webServer: {
    command: 'pnpm preview --host 0.0.0.0 --port 4173',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },

  // Глобальная настройка и разборка
  globalSetup: require.resolve('./tests/e2e/global-setup.ts'),
  globalTeardown: require.resolve('./tests/e2e/global-teardown.ts'),

  // Настройки для отдельных файлов
  grep: {
    // Включить только тесты с определенными тегами в CI
    ...(process.env.CI && {
      includeTags: ['@critical', '@smoke'],
      excludeTags: ['@slow', '@manual'],
    }),
  },
});
