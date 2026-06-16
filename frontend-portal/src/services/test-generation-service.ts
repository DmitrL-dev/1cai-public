/**
 * Test Generation Service
 * Автоматическая генерация тестов для кода
 * Версия: 1.0.0
 */

import { getOpenAIService, OpenAIIntegrationService } from './openai-integration-service';

export interface TestCase {
  id: string;
  name: string;
  description: string;
  input: Record<string, any>;
  expectedOutput: any;
  type: 'unit' | 'integration' | 'e2e';
  category: 'positive' | 'negative' | 'edge' | 'boundary';
}

export interface GeneratedTest {
  id: string;
  functionName: string;
  testCases: TestCase[];
  code: string;
  language: 'bsl' | 'typescript' | 'python';
  framework: string;
  coverage: {
    lines: number;
    branches: number;
    functions: number;
  };
}

export interface TestGenerationRequest {
  code: string;
  language: 'bsl' | 'typescript' | 'python';
  functionName?: string;
  testType: 'unit' | 'integration' | 'e2e' | 'all';
  includeEdgeCases: boolean;
  framework?: string;
}

export class TestGenerationService {
  private openaiService: OpenAIIntegrationService | null = null;

  constructor(openaiService?: OpenAIIntegrationService) {
    this.openaiService = openaiService || null;
  }

  /**
   * Генерация тестов для кода
   */
  async generateTests(request: TestGenerationRequest): Promise<GeneratedTest[]> {
    const tests: GeneratedTest[] = [];

    if (request.language === 'bsl') {
      const bslTests = await this.generateBSLTests(request);
      tests.push(...bslTests);
    } else if (request.language === 'typescript') {
      const tsTests = await this.generateTypeScriptTests(request);
      tests.push(...tsTests);
    } else if (request.language === 'python') {
      const pyTests = await this.generatePythonTests(request);
      tests.push(...pyTests);
    }

    return tests;
  }

  /**
   * Генерация тестов для BSL
   */
  private async generateBSLTests(request: TestGenerationRequest): Promise<GeneratedTest[]> {
    const tests: GeneratedTest[] = [];

    // Извлечение функций из кода
    const functions = this.extractBSLFunctions(request.code);

    for (const func of functions) {
      const testCases = await this.generateTestCases(func, request);
      const testCode = this.generateBSLTestCode(func, testCases);

      tests.push({
        id: `test-${Date.now()}-${func.name}`,
        functionName: func.name,
        testCases,
        code: testCode,
        language: 'bsl',
        framework: 'xUnitFor1C',
        coverage: {
          lines: this.calculateCoverage(func.code, testCode),
          branches: 0, // TODO
          functions: 1
        }
      });
    }

    return tests;
  }

  /**
   * Извлечение функций из BSL кода
   */
  private extractBSLFunctions(code: string): Array<{ name: string; code: string; params: string[] }> {
    const functions: Array<{ name: string; code: string; params: string[] }> = [];
    const lines = code.split('\n');

    let currentFunction: { name: string; code: string; params: string[] } | null = null;
    let inFunction = false;
    let braceCount = 0;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      // Начало функции
      if (line.startsWith('Функция ') || line.startsWith('Процедура ')) {
        const match = line.match(/(?:Функция|Процедура)\s+(\w+)/);
        if (match) {
          currentFunction = {
            name: match[1],
            code: line + '\n',
            params: this.extractParameters(line)
          };
          inFunction = true;
          braceCount = 0;
        }
      } else if (inFunction && currentFunction) {
        currentFunction.code += line + '\n';

        // Подсчет скобок для определения конца функции
        braceCount += (line.match(/Конец(?:Функции|Процедуры)/) ? -1 : 0);
        
        if (line.includes('КонецФункции') || line.includes('КонецПроцедуры')) {
          functions.push(currentFunction);
          currentFunction = null;
          inFunction = false;
        }
      }
    }

    return functions;
  }

  /**
   * Извлечение параметров из сигнатуры функции
   */
  private extractParameters(signature: string): string[] {
    const paramMatch = signature.match(/\(([^)]*)\)/);
    if (!paramMatch) return [];

    return paramMatch[1]
      .split(',')
      .map(p => p.trim().split(/\s+/)[0])
      .filter(p => p);
  }

  /**
   * Генерация тест-кейсов
   */
  private async generateTestCases(
    func: { name: string; code: string; params: string[] },
    request: TestGenerationRequest
  ): Promise<TestCase[]> {
    const testCases: TestCase[] = [];

    if (this.openaiService && request.includeEdgeCases) {
      // Использование AI для генерации тест-кейсов
      try {
        const prompt = `Проанализируй следующую функцию и создай тестовые случаи:

\`\`\`bsl
${func.code}
\`\`\`

Создай тестовые случаи включая:
1. Положительные случаи (happy path)
2. Отрицательные случаи (validation errors)
3. Граничные случаи (boundary values)
4. Крайние случаи (edge cases)

Верни JSON массив:
[
  {
    "name": "название теста",
    "description": "описание",
    "input": {"param1": "value1"},
    "expectedOutput": "ожидаемый результат",
    "type": "positive|negative|edge|boundary"
  }
]`;

        const response = await this.openaiService.complete({
          messages: [
            {
              role: 'system',
              content: 'Ты эксперт по тестированию кода на языке 1С (BSL). Создавай качественные тест-кейсы.'
            },
            { role: 'user', content: prompt }
          ],
          temperature: 0.3,
          maxTokens: 2000
        });

        const parsedCases = this.parseTestCases(response.content);
        testCases.push(...parsedCases);
      } catch (error) {
        console.error('Ошибка AI генерации тестов:', error);
      }
    }

    // Базовая генерация без AI
    if (testCases.length === 0) {
      testCases.push({
        id: 'test-1',
        name: `${func.name}_Positive`,
        description: `Позитивный тест для функции ${func.name}`,
        input: this.generateDefaultInput(func.params),
        expectedOutput: 'OK',
        type: 'unit',
        category: 'positive'
      });

      if (func.params.length > 0) {
        testCases.push({
          id: 'test-2',
          name: `${func.name}_Negative`,
          description: `Негативный тест с невалидными данными`,
          input: this.generateInvalidInput(func.params),
          expectedOutput: null,
          type: 'unit',
          category: 'negative'
        });
      }
    }

    return testCases;
  }

  /**
   * Генерация кода теста для BSL
   */
  private generateBSLTestCode(
    func: { name: string; code: string; params: string[] },
    testCases: TestCase[]
  ): string {
    let testCode = `// Автоматически сгенерированные тесты для функции ${func.name}\n\n`;

    testCases.forEach((testCase, index) => {
      testCode += `Процедура Тест_${func.name}_${testCase.name}()\n`;
      testCode += `\n`;
      testCode += `\t// ${testCase.description}\n`;
      testCode += `\t\n`;
      
      // Подготовка входных данных
      Object.entries(testCase.input).forEach(([key, value]) => {
        testCode += `\t${key} = ${this.formatValue(value)};\n`;
      });
      
      testCode += `\t\n`;
      
      // Вызов функции
      const paramsStr = func.params.map(p => testCase.input[p] || p).join(', ');
      testCode += `\tРезультат = ${func.name}(${paramsStr});\n`;
      testCode += `\t\n`;
      
      // Проверка результата
      testCode += `\tОжидаемоИстина(Результат = ${this.formatValue(testCase.expectedOutput)}, "Ожидалось: ${testCase.expectedOutput}");\n`;
      testCode += `\n`;
      testCode += `КонецПроцедуры\n\n`;
    });

    return testCode;
  }

  /**
   * Генерация тестов для TypeScript
   */
  private async generateTypeScriptTests(request: TestGenerationRequest): Promise<GeneratedTest[]> {
    // TODO: Реализовать для TypeScript
    return [];
  }

  /**
   * Генерация тестов для Python
   */
  private async generatePythonTests(request: TestGenerationRequest): Promise<GeneratedTest[]> {
    // TODO: Реализовать для Python
    return [];
  }

  /**
   * Парсинг тест-кейсов из AI ответа
   */
  private parseTestCases(content: string): TestCase[] {
    try {
      const jsonMatch = content.match(/\[[\s\S]*\]/);
      if (!jsonMatch) return [];

      const cases = JSON.parse(jsonMatch[0]);
      return cases.map((c: any, index: number) => ({
        id: `ai-test-${index}`,
        name: c.name || `Test${index}`,
        description: c.description || '',
        input: c.input || {},
        expectedOutput: c.expectedOutput,
        type: 'unit',
        category: c.type || 'positive'
      }));
    } catch (error) {
      console.error('Ошибка парсинга тест-кейсов:', error);
      return [];
    }
  }

  /**
   * Генерация дефолтных входных данных
   */
  private generateDefaultInput(params: string[]): Record<string, any> {
    const input: Record<string, any> = {};
    params.forEach(param => {
      input[param] = 0; // Базовое значение
    });
    return input;
  }

  /**
   * Генерация невалидных входных данных
   */
  private generateInvalidInput(params: string[]): Record<string, any> {
    const input: Record<string, any> = {};
    params.forEach(param => {
      input[param] = null; // Невалидное значение
    });
    return input;
  }

  /**
   * Форматирование значения для кода
   */
  private formatValue(value: any): string {
    if (value === null || value === undefined) return 'Неопределено';
    if (typeof value === 'string') return `"${value}"`;
    if (typeof value === 'boolean') return value ? 'Истина' : 'Ложь';
    return String(value);
  }

  /**
   * Расчет покрытия кода
   */
  private calculateCoverage(originalCode: string, testCode: string): number {
    // Упрощенный расчет
    const originalLines = originalCode.split('\n').length;
    const testedLines = testCode.split('\n').length;
    return Math.min(100, Math.round((testedLines / originalLines) * 100));
  }
}

// Экспорт синглтона
let testGenServiceInstance: TestGenerationService | null = null;

export function getTestGenerationService(openaiService?: OpenAIIntegrationService): TestGenerationService {
  if (!testGenServiceInstance) {
    testGenServiceInstance = new TestGenerationService(openaiService);
  }
  return testGenServiceInstance;
}







