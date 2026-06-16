/**
 * Дополнительные скрипты и утилиты для тестирования
 * Содержит команды для быстрого запуска различных типов тестов
 */

// Основные команды для запуска тестов
export const testCommands = {
  // Все тесты
  all: "deno test",
  
  // Unit тесты
  unit: "deno test tests/unit/**/*.test.ts",
  
  // Integration тесты
  integration: "deno test tests/integration/**/*.test.ts",
  
  // E2E тесты
  e2e: "deno test tests/e2e/**/*.test.ts",
  
  // Тесты с покрытием
  coverage: "deno test --coverage=coverage --coverage-include='supabase/functions/**/*'",
  
  // Тесты в режиме наблюдения
  watch: "deno test --watch tests/**/*.test.ts",
  
  // Быстрые тесты (только unit)
  quick: "deno test tests/unit/**/*.test.ts --parallel",
  
  // Медленные тесты (integration + e2e)
  slow: "deno test tests/integration/**/*.test.ts tests/e2e/**/*.test.ts",
  
  // Форматирование кода
  fmt: "deno fmt",
  
  // Линтинг
  lint: "deno lint",
  
  // Проверка форматирования
  fmtCheck: "deno fmt --check",
  
  // Генерация отчета покрытия
  coverageReport: "deno test --coverage=coverage"
};

// NPM скрипты для package.json
export const npmScripts = {
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
};

// Git hooks для pre-commit
export const gitHooks = {
  // Pre-commit hook для запуска быстрых тестов
  preCommit: `#!/bin/sh
echo "🚀 Running pre-commit checks..."

# Проверка форматирования
echo "📝 Checking code formatting..."
deno fmt --check
if [ $? -ne 0 ]; then
  echo "❌ Code formatting check failed. Run 'deno fmt' to fix."
  exit 1
fi

# Линтинг
echo "🔍 Running linter..."
deno lint
if [ $? -ne 0 ]; then
  echo "❌ Linting failed. Please fix the issues."
  exit 1
fi

# Быстрые тесты
echo "🧪 Running quick tests..."
deno test tests/unit/**/*.test.ts --parallel
if [ $? -ne 0 ]; then
  echo "❌ Quick tests failed. Please fix the issues."
  exit 1
fi

echo "✅ All pre-commit checks passed!"`,

  // Pre-push hook для полной проверки
  prePush: `#!/bin/sh
echo "🚀 Running pre-push checks..."

# Полная проверка форматирования
echo "📝 Checking code formatting..."
deno fmt --check
if [ $? -ne 0 ]; then
  echo "❌ Code formatting check failed. Run 'deno fmt' to fix."
  exit 1
fi

# Линтинг
echo "🔍 Running linter..."
deno lint
if [ $? -ne 0 ]; then
  echo "❌ Linting failed. Please fix the issues."
  exit 1
fi

# Type checking
echo "🔍 Running type checker..."
deno check tests/**/*.ts
if [ $? -ne 0 ]; then
  echo "❌ Type checking failed. Please fix the issues."
  exit 1
fi

# Все тесты с покрытием
echo "🧪 Running all tests with coverage..."
deno test --coverage=coverage --coverage-include='supabase/functions/**/*'
if [ $? -ne 0 ]; then
  echo "❌ Tests failed. Please fix the issues."
  exit 1
fi

# Проверка минимального покрытия
echo "📊 Checking coverage thresholds..."
node scripts/check-coverage.js
if [ $? -ne 0 ]; then
  echo "❌ Coverage threshold not met. Please improve test coverage."
  exit 1
fi

echo "✅ All pre-push checks passed!"`
};

// GitHub Actions workflow
export const githubActionsWorkflow = `name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Setup Deno
      uses: denoland/setup-deno@v1
      with:
        deno-version: v1.37
        
    - name: Install dependencies
      run: deno cache deps.ts
      
    - name: Run linting
      run: deno lint
      
    - name: Check formatting
      run: deno fmt --check
      
    - name: Run type checking
      run: deno check tests/**/*.ts
      
    - name: Run unit tests
      run: deno test tests/unit/**/*.test.ts --parallel
      
    - name: Run integration tests
      run: deno test tests/integration/**/*.test.ts
      
    - name: Run E2E tests
      run: deno test tests/e2e/**/*.test.ts
      
    - name: Generate coverage report
      run: deno test --coverage=coverage --coverage-include='supabase/functions/**/*'
      
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: coverage/lcov.info
        flags: unittests
        name: codecov-umbrella
        fail_ci_if_error: false

  security:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
      
    - name: Setup Deno
      uses: denoland/setup-deno@v1
      with:
        deno-version: v1.37
        
    - name: Run security audit
      run: |
        deno cache --lock=lock.json
        deno task audit 2>/dev/null || echo "Security audit not configured"`;

// ESLint конфигурация для тестов
export const eslintConfig = `module.exports = {
  env: {
    deno: true,
    browser: true,
    es2021: true
  },
  extends: [
    'eslint:recommended'
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module'
  },
  rules: {
    // Специфичные правила для тестов
    'no-unused-vars': ['error', { 
      'argsIgnorePattern': '^_',
      'varsIgnorePattern': '^_' 
    }],
    'prefer-const': 'error',
    'no-var': 'error',
    
    // Правила для тестовых файлов
    'no-console': 'off',
    '@typescript-eslint/no-unused-vars': ['error', { 
      'argsIgnorePattern': '^_' 
    }]
  },
  overrides: [
    {
      files: ['tests/**/*.test.ts'],
      rules: {
        'no-console': 'off'
      }
    }
  ]
};`;

// Пре-commit хуки скрипт
export const setupGitHooks = `#!/bin/bash

echo "🔧 Setting up git hooks..."

# Создаем директорию для hooks
mkdir -p .git/hooks

# Устанавливаем pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/sh
${gitHooks.preCommit}
EOF

# Делаем файл исполняемым
chmod +x .git/hooks/pre-commit

# Устанавливаем pre-push hook
cat > .git/hooks/pre-push << 'EOF'
#!/bin/sh
${gitHooks.prePush}
EOF

chmod +x .git/hooks/pre-push

echo "✅ Git hooks installed successfully!"
echo "📝 Pre-commit hook will run quick tests before each commit"
echo "🚀 Pre-push hook will run full test suite before each push"`;

// Coverage checker скрипт
export const coverageChecker = `const fs = require('fs');
const path = require('path');

const COVERAGE_THRESHOLDS = {
  statements: 80,
  branches: 70,
  functions: 80,
  lines: 80
};

function parseCoverageReport(coverageDir) {
  const coverageFile = path.join(coverageDir, 'lcov.info');
  
  if (!fs.existsSync(coverageFile)) {
    console.error('❌ Coverage file not found:', coverageFile);
    process.exit(1);
  }

  const content = fs.readFileSync(coverageFile, 'utf8');
  const lines = content.split('\\n');
  
  let totalStatements = 0;
  let coveredStatements = 0;
  let totalBranches = 0;
  let coveredBranches = 0;
  let totalFunctions = 0;
  let coveredFunctions = 0;
  let totalLines = 0;
  let coveredLines = 0;

  for (const line of lines) {
    if (line.startsWith('TN:')) continue;
    
    if (line.startsWith('SF:')) {
      // Новая функция
      totalFunctions++;
      continue;
    }
    
    if (line.startsWith('FNF:')) {
      totalFunctions += parseInt(line.split(':')[1]);
      continue;
    }
    
    if (line.startsWith('FNH:')) {
      coveredFunctions += parseInt(line.split(':')[1]);
      continue;
    }
    
    if (line.startsWith('LF:')) {
      totalLines += parseInt(line.split(':')[1]);
      continue;
    }
    
    if (line.startsWith('LH:')) {
      coveredLines += parseInt(line.split(':')[1]);
      continue;
    }
    
    if (line.startsWith('DA:')) {
      const parts = line.split(':');
      const count = parseInt(parts[1]);
      if (count > 0) {
        coveredLines++;
      }
      totalLines++;
      continue;
    }
    
    if (line.startsWith('BRDA:')) {
      totalBranches++;
      const parts = line.split(',');
      const count = parseInt(parts[2]);
      if (count > 0) {
        coveredBranches++;
      }
      continue;
    }
  }

  return {
    statements: totalStatements > 0 ? (coveredStatements / totalStatements) * 100 : 100,
    branches: totalBranches > 0 ? (coveredBranches / totalBranches) * 100 : 100,
    functions: totalFunctions > 0 ? (coveredFunctions / totalFunctions) * 100 : 100,
    lines: totalLines > 0 ? (coveredLines / totalLines) * 100 : 100
  };
}

function checkThresholds(coverage) {
  const results = {
    statements: coverage.statements >= COVERAGE_THRESHOLDS.statements,
    branches: coverage.branches >= COVERAGE_THRESHOLDS.branches,
    functions: coverage.functions >= COVERAGE_THRESHOLDS.functions,
    lines: coverage.lines >= COVERAGE_THRESHOLDS.lines
  };

  console.log('\\n📊 Coverage Report:');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(\`Statements: \${coverage.statements.toFixed(2)}% (min: \${COVERAGE_THRESHOLDS.statements}%) \${results.statements ? '✅' : '❌'}\`);
  console.log(\`Branches:   \${coverage.branches.toFixed(2)}% (min: \${COVERAGE_THRESHOLDS.branches}%) \${results.branches ? '✅' : '❌'}\`);
  console.log(\`Functions:  \${coverage.functions.toFixed(2)}% (min: \${COVERAGE_THRESHOLDS.functions}%) \${results.functions ? '✅' : '❌'}\`);
  console.log(\`Lines:      \${coverage.lines.toFixed(2)}% (min: \${COVERAGE_THRESHOLDS.lines}%) \${results.lines ? '✅' : '❌'}\`);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

  const allPassed = Object.values(results).every(result => result);
  
  if (!allPassed) {
    console.log('\\n❌ Coverage threshold not met! Please improve test coverage.');
    process.exit(1);
  } else {
    console.log('\\n✅ All coverage thresholds met!');
  }
}

// Основная функция
const coverageDir = process.argv[2] || 'coverage';
const coverage = parseCoverageReport(coverageDir);
checkThresholds(coverage);`;

// Дополнительные команды для разработки
export const devCommands = {
  // Запуск в режиме разработки
  dev: "deno test --watch tests/**/*.test.ts --allow-net --allow-env",
  
  // Запуск с подробным логированием
  debug: "deno test --log-level debug",
  
  // Проверка производительности
  benchmark: "deno test --allow-net tests/performance/**/*.test.ts",
  
  // Генерация отчета покрытия в разных форматах
  coverageReport: "deno test --coverage=coverage --coverage-include='supabase/functions/**/*' && open coverage/index.html",
  
  // Очистка кэша
  clean: "deno cache --reload",
  
  // Проверка типов
  typecheck: "deno check tests/**/*.ts",
  
  // Обновление зависимостей
  update: "deno cache --reload deps.ts",
  
  // Генерация документации
  docs: "deno doc --output=docs",
  
  // Безопасность
  security: "deno lint --rules-tags=recommended && deno check tests/**/*.ts"
};

// Утилиты для создания тестовых данных
export const testDataGenerators = {
  // Генерация случайного пользователя
  generateUser: (overrides = {}) => ({
    id: \`user_\${Date.now()}_\${Math.random().toString(36).substr(2, 9)}\`,
    email: \`test\${Date.now()}@example.com\`,
    name: \`Test User \${Date.now()}\`,
    role: 'user',
    email_verified: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides
  }),

  // Генерация случайного товара
  generateProduct: (overrides = {}) => ({
    id: \`product_\${Date.now()}_\${Math.random().toString(36).substr(2, 9)}\`,
    name: \`Test Product \${Date.now()}\`,
    description: 'Generated test product',
    price: Math.floor(Math.random() * 10000) + 100,
    currency: 'RUB',
    category: 'test-category',
    stock: Math.floor(Math.random() * 100) + 1,
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides
  }),

  // Генерация случайного заказа
  generateOrder: (userId, productIds = [], overrides = {}) => ({
    id: \`order_\${Date.now()}_\${Math.random().toString(36).substr(2, 9)}\`,
    user_id: userId,
    status: 'pending',
    items: productIds.map((productId, index) => ({
      product_id: productId,
      quantity: Math.floor(Math.random() * 5) + 1,
      price: Math.floor(Math.random() * 1000) + 100,
      total: Math.floor(Math.random() * 5000) + 100
    })),
    subtotal: Math.floor(Math.random() * 10000) + 1000,
    tax_amount: 0,
    shipping_cost: 500,
    discount_amount: 0,
    total: 0,
    currency: 'RUB',
    payment_status: 'pending',
    shipping_status: 'not_shipped',
    payment_method: 'card',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides
  })
};

// Экспорт всех команд
export const scripts = {
  commands: testCommands,
  npm: npmScripts,
  hooks: gitHooks,
  githubActions: githubActionsWorkflow,
  eslint: eslintConfig,
  dev: devCommands,
  generators: testDataGenerators,
  setupHooks: setupGitHooks,
  coverageChecker: coverageChecker
};

export default scripts;