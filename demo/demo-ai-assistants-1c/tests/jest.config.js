/**
 * Jest конфигурация для тестирования Edge Functions
 */

module.exports = {
  // Базовые настройки
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests'],
  testMatch: [
    '**/__tests__/**/*.test.ts',
    '**/?(*.)+(spec|test).ts'
  ],

  // Модули и трансформация
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  transform: {
    '^.+\\.tsx?$': 'ts-jest'
  },

  // Игнорируемые файлы и директории
  testPathIgnorePatterns: [
    '/node_modules/',
    '/dist/',
    '/build/'
  ],

  // Настройки покрытия
  collectCoverage: false,
  collectCoverageFrom: [
    'supabase/functions/**/*.{ts,js}',
    '!supabase/functions/**/index.ts', // Исключаем main файлы функций
    'supabase/shared/**/*.{ts,js}'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 70,
      lines: 70,
      statements: 70
    }
  },

  // Настройки для тестирования Edge Functions
  setupFilesAfterEnv: ['<rootDir>/tests/setup.ts'],
  
  // Глобальные переменные для тестов
  globals: {
    'ts-jest': {
      tsconfig: '<rootDir>/tests/tsconfig.json'
    }
  },

  // Максимальное время выполнения теста
  testTimeout: 30000,

  // Настройки моков
  clearMocks: true,
  restoreMocks: true,

  // Настройки для Edge Functions тестов
  testEnvironmentOptions: {
    url: 'http://localhost:54321'
  },

  // Verbose output для отладки
  verbose: process.env.NODE_ENV === 'development',

  // Настройки для CI
  ci: process.env.CI === 'true',

  // Дополнительные настройки
  testResultsProcessor: undefined,
  reporters: [
    'default',
    ['jest-junit', {
      outputDirectory: 'test-results',
      outputName: 'junit.xml'
    }]
  ],

  // Игнорируемые пути для coverage
  coveragePathIgnorePatterns: [
    '/node_modules/',
    '/dist/',
    '/build/',
    '/tests/',
    '/coverage/'
  ],

  // Настройки для моков Deno
  testEnvironment: 'jsdom', // Для браузерных API
  setupFiles: ['<rootDir>/tests/setup-deno.ts'],

  // Настройки для параллельного выполнения
  maxWorkers: '50%',

  // Настройки для watch mode
  watchPathIgnorePatterns: [
    '/node_modules/',
    '/dist/',
    '/coverage/'
  ],

  // Дополнительные переменные окружения для тестов
  testEnvironmentVariables: {
    NODE_ENV: 'test',
    EDGE_FUNCTION_URL: 'http://localhost:54321/functions/v1',
    SUPABASE_URL: 'http://localhost:54321',
    SUPABASE_ANON_KEY: 'test-anon-key'
  },

  // Настройки для TypeScript
  globals: {
    'ts-jest': {
      tsconfig: {
        target: 'ES2020',
        module: 'ESNext',
        moduleResolution: 'node',
        allowSyntheticDefaultImports: true,
        esModuleInterop: true,
        strict: true,
        skipLibCheck: true,
        forceConsistentCasingInFileNames: true
      }
    }
  }
};
