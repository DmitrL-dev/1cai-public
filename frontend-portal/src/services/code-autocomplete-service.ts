/**
 * Code Autocomplete Service
 * Сервис для автодополнения кода и анализа кода
 */

export interface CodeCompletion {
  id: string;
  text: string;
  displayText: string;
  kind: 'function' | 'method' | 'property' | 'variable' | 'class' | 'interface' | 'keyword' | 'snippet';
  detail?: string;
  documentation?: string;
  insertText?: string;
  filterText?: string;
  sortText?: string;
  additionalTextEdits?: TextEdit[];
  command?: {
    title: string;
    command: string;
    arguments?: any[];
  };
  range?: Range;
}

export interface TextEdit {
  range: Range;
  newText: string;
  newEOL?: string;
}

export interface Range {
  startLine: number;
  startCharacter: number;
  endLine: number;
  endCharacter: number;
}

export interface Position {
  line: number;
  character: number;
}

export interface CodeContext {
  language: string;
  content: string;
  cursor: Position;
  fileName?: string;
  projectType?: '1c' | 'typescript' | 'javascript' | 'python' | 'java' | 'csharp' | 'other';
  framework?: string;
  dependencies?: string[];
  imports?: string[];
  variables?: CodeSymbol[];
  functions?: CodeSymbol[];
  classes?: CodeSymbol[];
  currentScope?: 'global' | 'function' | 'class' | 'block';
  recentChanges?: CodeChange[];
}

export interface CodeSymbol {
  name: string;
  kind: 'function' | 'method' | 'property' | 'variable' | 'class' | 'interface' | 'constant';
  detail?: string;
  documentation?: string;
  range: Range;
  fileName: string;
  isExported?: boolean;
  parameters?: CodeParameter[];
  returnType?: string;
  modifiers?: string[];
  namespace?: string;
}

export interface CodeParameter {
  name: string;
  type: string;
  isOptional: boolean;
  defaultValue?: string;
  isRest?: boolean;
}

export interface CodeChange {
  type: 'addition' | 'modification' | 'deletion';
  range: Range;
  oldText?: string;
  newText?: string;
  timestamp: Date;
}

export interface SnippetTemplate {
  id: string;
  name: string;
  description: string;
  prefix: string;
  body: string[];
  language: string;
  category: 'control' | 'function' | 'class' | 'test' | 'comment' | 'custom';
  variables?: SnippetVariable[];
}

export interface SnippetVariable {
  name: string;
  defaultValue: string;
  description?: string;
}

export interface Diagnostics {
  fileName: string;
  language: string;
  version: string;
  severity: 'error' | 'warning' | 'info' | 'hint';
  message: string;
  range: Range;
  source: string;
  code?: string;
  relatedInformation?: DiagnosticRelatedInformation[];
  tags?: number[];
}

export interface DiagnosticRelatedInformation {
  message: string;
  range: Range;
}

export interface HoverInfo {
  contents: Array<{
    kind: 'plaintext' | 'markdown';
    value: string;
  }>;
  range?: Range;
}

export interface SignatureHelp {
  activeParameter: number;
  activeSignature: number;
  signatures: Signature[];
}

export interface Signature {
  label: string;
  documentation?: string;
  parameters: ParameterInformation[];
}

export interface ParameterInformation {
  label: string;
  documentation?: string;
}

export interface CodeAction {
  title: string;
  kind?: string;
  isPreferred?: boolean;
  diagnostics?: Diagnostics[];
  edit?: {
    changes: Record<string, TextEdit[]>;
  };
  command?: {
    title: string;
    command: string;
    arguments?: any[];
  };
}

export interface CompletionRequest {
  context: CodeContext;
  triggerCharacter?: string;
  triggerKind: 'invoked' | 'triggerCharacter' | 'triggerForIncompleteCompletions';
}

export interface CompletionResponse {
  completions: CodeCompletion[];
  isIncomplete: boolean;
  filterText?: string;
}

export class CodeAutocompleteService {
  private snippets = new Map<string, SnippetTemplate[]>();
  private diagnosticsCache = new Map<string, Diagnostics[]>();
  private languageServers = new Map<string, any>();
  private completionHistory = new Map<string, CodeCompletion[]>();
  private codeAnalysisCache = new Map<string, {
    symbols: CodeSymbol[];
    lastUpdated: Date;
    version: number;
  }>();

  constructor() {
    this.initializeDefaultSnippets();
    this.initializeLanguageServers();
  }

  /**
   * Получение автодополнений
   */
  async getCompletions(request: CompletionRequest): Promise<CompletionResponse> {
    const { context, triggerCharacter, triggerKind } = request;

    // Определяем контекст автодополнения
    const completionType = this.determineCompletionType(context, triggerCharacter, triggerKind);

    let completions: CodeCompletion[] = [];

    switch (completionType) {
      case 'word':
        completions = await this.getWordCompletions(context);
        break;
      case 'import':
        completions = await this.getImportCompletions(context);
        break;
      case 'function':
        completions = await this.getFunctionCompletions(context);
        break;
      case 'property':
        completions = await this.getPropertyCompletions(context);
        break;
      case 'keyword':
        completions = await this.getKeywordCompletions(context);
        break;
      case 'snippet':
        completions = await this.getSnippetCompletions(context);
        break;
      default:
        completions = await this.getGeneralCompletions(context);
    }

    // Фильтрация и сортировка
    completions = this.filterAndSortCompletions(completions, context);

    // Кэширование
    const cacheKey = this.generateCacheKey(context);
    this.completionHistory.set(cacheKey, completions);

    return {
      completions,
      isIncomplete: false,
      filterText: this.extractFilterText(context)
    };
  }

  /**
   * Получение информации при наведении
   */
  async getHover(context: CodeContext): Promise<HoverInfo | null> {
    const symbols = await this.analyzeCode(context);
    
    // Находим символ под курсором
    const symbol = symbols.find(s => this.isPositionInRange(context.cursor, s.range));
    
    if (!symbol) {
      return null;
    }

    const contents = [
      {
        kind: 'markdown' as const,
        value: this.formatSymbolDocumentation(symbol)
      }
    ];

    return {
      contents,
      range: symbol.range
    };
  }

  /**
   * Получение информации о подписях функций
   */
  async getSignatureHelp(context: CodeContext): Promise<SignatureHelp | null> {
    const symbols = await this.analyzeCode(context);
    
    // Находим функцию, на которой курсор
    const functionSymbol = symbols.find(s => 
      s.kind === 'function' && 
      this.isPositionInRange(context.cursor, s.range) &&
      s.parameters && s.parameters.length > 0
    );

    if (!functionSymbol) {
      return null;
    }

    const signature: Signature = {
      label: this.formatFunctionSignature(functionSymbol),
      documentation: functionSymbol.documentation,
      parameters: functionSymbol.parameters.map(param => ({
        label: param.name,
        documentation: `${param.type}${param.isOptional ? '?' : ''}`
      }))
    };

    return {
      activeParameter: 0,
      activeSignature: 0,
      signatures: [signature]
    };
  }

  /**
   * Получение действий кода
   */
  async getCodeActions(context: CodeContext): Promise<CodeAction[]> {
    const diagnostics = await this.getDiagnostics(context);
    const actions: CodeAction[] = [];

    // Создаем действия на основе диагностик
    diagnostics.forEach(diagnostic => {
      if (diagnostic.severity === 'error' && diagnostic.code) {
        switch (diagnostic.code) {
          case 'UNUSED_VARIABLE':
            actions.push(this.createRemoveUnusedVariableAction(diagnostic));
            break;
          case 'MISSING_IMPORT':
            actions.push(this.createAddImportAction(diagnostic));
            break;
          case 'DEAD_CODE':
            actions.push(this.createRemoveDeadCodeAction(diagnostic));
            break;
        }
      }
    });

    // Добавляем действия для улучшения кода
    actions.push(...await this.getRefactoringActions(context));

    return actions;
  }

  /**
   * Получение диагностик
   */
  async getDiagnostics(context: CodeContext): Promise<Diagnostics[]> {
    const cacheKey = `${context.fileName}_${context.version || '0'}`;
    const cached = this.diagnosticsCache.get(cacheKey);

    if (cached) {
      return cached;
    }

    // Анализируем код и генерируем диагностики
    const diagnostics = await this.analyzeCodeForDiagnostics(context);
    
    this.diagnosticsCache.set(cacheKey, diagnostics);
    return diagnostics;
  }

  /**
   * Добавление сниппета
   */
  addSnippet(snippet: SnippetTemplate): void {
    if (!this.snippets.has(snippet.language)) {
      this.snippets.set(snippet.language, []);
    }
    this.snippets.get(snippet.language)!.push(snippet);
  }

  /**
   * Удаление сниппета
   */
  removeSnippet(language: string, snippetId: string): boolean {
    const snippets = this.snippets.get(language);
    if (!snippets) return false;

    const index = snippets.findIndex(s => s.id === snippetId);
    if (index === -1) return false;

    snippets.splice(index, 1);
    return true;
  }

  /**
   * Получение сниппетов для языка
   */
  getSnippets(language: string): SnippetTemplate[] {
    return this.snippets.get(language) || [];
  }

  /**
   * Экспорт сниппетов
   */
  exportSnippets(): string {
    const exportData: Record<string, SnippetTemplate[]> = {};
    
    this.snippets.forEach((snippets, language) => {
      exportData[language] = snippets;
    });

    return JSON.stringify(exportData, null, 2);
  }

  /**
   * Импорт сниппетов
   */
  importSnippets(snippetsJson: string): { success: boolean; imported: number; errors: string[] } {
    try {
      const data = JSON.parse(snippetsJson);
      let imported = 0;
      const errors: string[] = [];

      Object.entries(data).forEach(([language, snippets]) => {
        if (!Array.isArray(snippets)) {
          errors.push(`Неверный формат для языка ${language}`);
          return;
        }

        snippets.forEach((snippet: any) => {
          try {
            this.validateSnippet(snippet);
            this.addSnippet(snippet);
            imported++;
          } catch (error) {
            errors.push(`Ошибка в сниппете ${snippet.name}: ${error}`);
          }
        });
      });

      return { success: true, imported, errors };
    } catch (error) {
      return { success: false, imported: 0, errors: [error instanceof Error ? error.message : 'Неизвестная ошибка'] };
    }
  }

  /**
   * Анализ кода
   */
  async analyzeCode(context: CodeContext): Promise<CodeSymbol[]> {
    const cacheKey = this.generateAnalysisCacheKey(context);
    const cached = this.codeAnalysisCache.get(cacheKey);

    if (cached && cached.version === (context as any).version) {
      return cached.symbols;
    }

    // Парсим код и извлекаем символы
    const symbols = this.parseCodeForSymbols(context);
    
    this.codeAnalysisCache.set(cacheKey, {
      symbols,
      lastUpdated: new Date(),
      version: (context as any).version || 1
    });

    return symbols;
  }

  /**
   * Очистка кэша
   */
  clearCache(): void {
    this.completionHistory.clear();
    this.diagnosticsCache.clear();
    this.codeAnalysisCache.clear();
  }

  /**
   * Получение статистики сервиса
   */
  getServiceStats(): {
    totalSnippets: number;
    snippetsByLanguage: Record<string, number>;
    averageCompletions: number;
    cachedAnalyses: number;
    supportedLanguages: string[];
  } {
    const totalSnippets = Array.from(this.snippets.values())
      .reduce((sum, snippets) => sum + snippets.length, 0);

    const snippetsByLanguage: Record<string, number> = {};
    this.snippets.forEach((snippets, language) => {
      snippetsByLanguage[language] = snippets.length;
    });

    const averageCompletions = Array.from(this.completionHistory.values())
      .reduce((sum, completions) => sum + completions.length, 0) / 
      Math.max(this.completionHistory.size, 1);

    return {
      totalSnippets,
      snippetsByLanguage,
      averageCompletions: Math.round(averageCompletions * 100) / 100,
      cachedAnalyses: this.codeAnalysisCache.size,
      supportedLanguages: Array.from(this.snippets.keys())
    };
  }

  // Private methods

  private initializeDefaultSnippets(): void {
    // TypeScript сниппеты
    this.addSnippet({
      id: 'ts_function',
      name: 'Function',
      description: 'Creates a function declaration',
      prefix: 'fun',
      body: [
        'function ${1:functionName}(${2:params}): ${3:void} {',
        '\t${4:// function body}',
        '}'
      ],
      language: 'typescript',
      category: 'function',
      variables: [
        { name: 'functionName', defaultValue: 'myFunction' },
        { name: 'params', defaultValue: '' },
        { name: 'void', defaultValue: 'void' }
      ]
    });

    this.addSnippet({
      id: 'ts_class',
      name: 'Class',
      description: 'Creates a class declaration',
      prefix: 'class',
      body: [
        'class ${1:ClassName} {',
        '\tconstructor(${2:params}) {',
        '\t\t${3:// constructor body}',
        '\t}',
        '\t${4:// methods}',
        '}'
      ],
      language: 'typescript',
      category: 'class'
    });

    // 1C сниппеты
    this.addSnippet({
      id: '1c_procedure',
      name: 'Procedure',
      description: 'Creates a 1C procedure',
      prefix: 'proc',
      body: [
        'Процедура ${1:ProcedureName}(${2:params}) Экспорт',
        '\t${3:// procedure body}',
        'КонецПроцедуры'
      ],
      language: '1c',
      category: 'function'
    });

    this.addSnippet({
      id: '1c_function',
      name: 'Function',
      description: 'Creates a 1C function',
      prefix: 'func',
      body: [
        'Функция ${1:FunctionName}(${2:params}) Экспорт',
        '\t${3:// function body}',
        '\tВозврат ${4:result};',
        'КонецФункции'
      ],
      language: '1c',
      category: 'function'
    });
  }

  private initializeLanguageServers(): void {
    // Инициализация языковых серверов (заглушки)
    this.languageServers.set('typescript', { available: true });
    this.languageServers.set('1c', { available: true });
    this.languageServers.set('javascript', { available: true });
  }

  private determineCompletionType(
    context: CodeContext, 
    triggerCharacter?: string, 
    triggerKind?: CompletionRequest['triggerKind']
  ): 'word' | 'import' | 'function' | 'property' | 'keyword' | 'snippet' | 'general' {
    if (triggerCharacter === '.') return 'property';
    if (triggerCharacter === '(') return 'function';
    if (triggerCharacter === '[') return 'property';
    if (triggerCharacter === ' ' && triggerKind === 'triggerCharacter') return 'keyword';
    if (triggerCharacter === '<' && context.projectType === '1c') return 'snippet';
    if (context.content.includes('import') || context.content.includes('Включить')) return 'import';
    
    return 'general';
  }

  private async getWordCompletions(context: CodeContext): Promise<CodeCompletion[]> {
    // Извлекаем текущее слово
    const currentLine = context.content.split('\n')[context.cursor.line];
    const beforeCursor = currentLine.substring(0, context.cursor.character);
    const wordMatch = beforeCursor.match(/(\w+)$/);
    
    if (!wordMatch) return [];

    const word = wordMatch[1];
    const symbols = await this.analyzeCode(context);
    
    return symbols
      .filter(symbol => symbol.name.startsWith(word))
      .map(symbol => ({
        id: this.generateId(),
        text: symbol.name,
        displayText: symbol.name,
        kind: symbol.kind,
        detail: symbol.detail,
        documentation: symbol.documentation
      }));
  }

  private async getImportCompletions(context: CodeContext): Promise<CodeCompletion[]> {
    // Генерируем дополнения для импортов
    return [
      {
        id: this.generateId(),
        text: 'import { Component } from "react"',
        displayText: 'import { Component } from "react"',
        kind: 'keyword',
        detail: 'React Component'
      },
      {
        id: this.generateId(),
        text: 'import { useState, useEffect } from "react"',
        displayText: 'import { useState, useEffect } from "react"',
        kind: 'keyword',
        detail: 'React Hooks'
      }
    ];
  }

  private async getFunctionCompletions(context: CodeContext): Promise<CodeCompletion[]> {
    return [
      {
        id: this.generateId(),
        text: 'functionName(',
        displayText: 'functionName(params)',
        kind: 'function',
        detail: 'Custom function',
        insertText: 'functionName(${1:params})',
        command: {
          title: 'Trigger Parameter Hints',
          command: 'editor.action.triggerParameterHints'
        }
      }
    ];
  }

  private async getPropertyCompletions(context: CodeContext): Promise<CodeCompletion[]> {
    return [
      {
        id: this.generateId(),
        text: 'length',
        displayText: 'length',
        kind: 'property',
        detail: 'number',
        documentation: 'The number of elements in the array'
      },
      {
        id: this.generateId(),
        text: 'map',
        displayText: 'map(callback)',
        kind: 'method',
        detail: 'Array<any>',
        documentation: 'Creates a new array with the results of calling a provided function'
      }
    ];
  }

  private async getKeywordCompletions(context: CodeContext): Promise<CodeCompletion[]> {
    const keywords = [
      { keyword: 'if', detail: 'Conditional statement' },
      { keyword: 'for', detail: 'Loop statement' },
      { keyword: 'while', detail: 'Loop statement' },
      { keyword: 'try', detail: 'Exception handling' }
    ];

    return keywords.map(({ keyword, detail }) => ({
      id: this.generateId(),
      text: keyword,
      displayText: keyword,
      kind: 'keyword' as const,
      detail
    }));
  }

  private async getSnippetCompletions(context: CodeContext): Promise<CodeCompletion[]> {
    const languageSnippets = this.snippets.get(context.language) || [];
    
    return languageSnippets.map(snippet => ({
      id: this.generateId(),
      text: snippet.body.join('\n'),
      displayText: snippet.name,
      kind: 'snippet' as const,
      detail: snippet.description,
      insertText: this.expandSnippetVariables(snippet)
    }));
  }

  private async getGeneralCompletions(context: CodeContext): Promise<CodeCompletion[]> {
    const symbols = await this.analyzeCode(context);
    const snippets = await this.getSnippetCompletions(context);
    
    const symbolCompletions = symbols.map(symbol => ({
      id: this.generateId(),
      text: symbol.name,
      displayText: symbol.name,
      kind: symbol.kind,
      detail: symbol.detail,
      documentation: symbol.documentation
    }));

    return [...snippets, ...symbolCompletions];
  }

  private filterAndSortCompletions(completions: CodeCompletion[], context: CodeContext): CodeCompletion[] {
    const currentLine = context.content.split('\n')[context.cursor.line];
    const beforeCursor = currentLine.substring(0, context.cursor.character);
    
    // Фильтрация по текущему вводу
    const filtered = completions.filter(completion => {
      if (!completion.filterText) return true;
      return completion.filterText.toLowerCase().includes(beforeCursor.toLowerCase());
    });

    // Сортировка по релевантности
    return filtered.sort((a, b) => {
      // Приоритет сниппетам
      if (a.kind === 'snippet' && b.kind !== 'snippet') return -1;
      if (b.kind === 'snippet' && a.kind !== 'snippet') return 1;
      
      // Сортировка по алфавиту
      return a.displayText.localeCompare(b.displayText);
    });
  }

  private extractFilterText(context: CodeContext): string | undefined {
    const currentLine = context.content.split('\n')[context.cursor.line];
    const beforeCursor = currentLine.substring(0, context.cursor.character);
    const wordMatch = beforeCursor.match(/(\w+)$/);
    
    return wordMatch ? wordMatch[1] : undefined;
  }

  private async analyzeCodeForDiagnostics(context: CodeContext): Promise<Diagnostics[]> {
    const diagnostics: Diagnostics[] = [];
    
    // Простейшие диагностики
    const lines = context.content.split('\n');
    lines.forEach((line, index) => {
      // Проверка незакрытых скобок
      const openBrackets = (line.match(/[({[]/g) || []).length;
      const closeBrackets = (line.match(/[)}]\s*$/g) || []).length;
      
      if (openBrackets !== closeBrackets && closeBrackets > 0) {
        diagnostics.push({
          fileName: context.fileName || 'unknown',
          language: context.language,
          version: '1.0',
          severity: 'error',
          message: 'Незакрытая скобка',
          range: {
            startLine: index,
            startCharacter: line.length - 1,
            endLine: index,
            endCharacter: line.length
          },
          source: 'CodeAutocompleteService',
          code: 'UNCLOSED_BRACKET'
        });
      }
    });

    return diagnostics;
  }

  private createRemoveUnusedVariableAction(diagnostic: Diagnostics): CodeAction {
    return {
      title: 'Удалить неиспользуемую переменную',
      kind: 'quickfix',
      diagnostics: [diagnostic],
      edit: {
        changes: {
          [diagnostic.fileName]: [{
            range: diagnostic.range,
            newText: ''
          }]
        }
      }
    };
  }

  private createAddImportAction(diagnostic: Diagnostics): CodeAction {
    return {
      title: 'Добавить импорт',
      kind: 'quickfix',
      diagnostics: [diagnostic],
      edit: {
        changes: {
          [diagnostic.fileName]: [{
            range: {
              startLine: 0,
              startCharacter: 0,
              endLine: 0,
              endCharacter: 0
            },
            newText: 'import { Component } from "react";\n'
          }]
        }
      }
    };
  }

  private createRemoveDeadCodeAction(diagnostic: Diagnostics): CodeAction {
    return {
      title: 'Удалить мертвый код',
      kind: 'quickfix',
      diagnostics: [diagnostic]
    };
  }

  private async getRefactoringActions(context: CodeContext): Promise<CodeAction[]> {
    const symbols = await this.analyzeCode(context);
    const actions: CodeAction[] = [];

    // Поиск длинных функций для рефакторинга
    symbols.forEach(symbol => {
      if (symbol.kind === 'function') {
        const functionLines = symbol.range.endLine - symbol.range.startLine;
        if (functionLines > 50) {
          actions.push({
            title: `Разделить функцию ${symbol.name}`,
            kind: 'refactor',
            diagnostics: []
          });
        }
      }
    });

    return actions;
  }

  private parseCodeForSymbols(context: CodeContext): CodeSymbol[] {
    const symbols: CodeSymbol[] = [];
    const lines = context.content.split('\n');

    lines.forEach((line, index) => {
      // Простой парсинг функций
      const functionMatch = line.match(/function\s+(\w+)|(\w+)\s*=\s*function|const\s+(\w+)\s*=/);
      if (functionMatch) {
        const functionName = functionMatch[1] || functionMatch[2] || functionMatch[3];
        symbols.push({
          name: functionName,
          kind: 'function',
          range: {
            startLine: index,
            startCharacter: 0,
            endLine: index,
            endCharacter: line.length
          },
          fileName: context.fileName || 'unknown'
        });
      }

      // Простой парсинг переменных
      const variableMatch = line.match(/(?:const|let|var)\s+(\w+)/);
      if (variableMatch) {
        symbols.push({
          name: variableMatch[1],
          kind: 'variable',
          range: {
            startLine: index,
            startCharacter: 0,
            endLine: index,
            endCharacter: line.length
          },
          fileName: context.fileName || 'unknown'
        });
      }
    });

    return symbols;
  }

  private isPositionInRange(position: Position, range: Range): boolean {
    return position.line >= range.startLine && 
           position.line <= range.endLine &&
           position.character >= range.startCharacter &&
           position.character <= range.endCharacter;
  }

  private formatSymbolDocumentation(symbol: CodeSymbol): string {
    let doc = `**${symbol.name}**`;
    
    if (symbol.detail) {
      doc += `\n\n${symbol.detail}`;
    }
    
    if (symbol.documentation) {
      doc += `\n\n${symbol.documentation}`;
    }
    
    if (symbol.parameters && symbol.parameters.length > 0) {
      doc += `\n\n**Параметры:**`;
      symbol.parameters.forEach(param => {
        doc += `\n- \`${param.name}\`: ${param.type}${param.isOptional ? ' (опциональный)' : ''}`;
      });
    }
    
    if (symbol.returnType) {
      doc += `\n\n**Возвращает:** ${symbol.returnType}`;
    }

    return doc;
  }

  private formatFunctionSignature(symbol: CodeSymbol): string {
    const params = symbol.parameters?.map(p => 
      `${p.name}${p.isOptional ? '?' : ''}: ${p.type}`
    ).join(', ') || '';

    return `${symbol.name}(${params})${symbol.returnType ? `: ${symbol.returnType}` : ''}`;
  }

  private expandSnippetVariables(snippet: SnippetTemplate): string {
    let body = snippet.body.join('\n');
    
    // Заменяем переменные на placeholder'ы
    snippet.variables?.forEach((variable, index) => {
      const placeholder = `$${index + 1}`;
      const defaultValue = variable.defaultValue || variable.name;
      body = body.replace(new RegExp(`\\$\\{${index + 1}\\}`, 'g'), placeholder);
      body = body.replace(new RegExp(`\\$\\{${variable.name}\\}`, 'g'), defaultValue);
    });

    return body;
  }

  private validateSnippet(snippet: any): void {
    if (!snippet.id || !snippet.name || !snippet.body || !snippet.language) {
      throw new Error('Неполные данные сниппета');
    }

    if (!Array.isArray(snippet.body) || snippet.body.length === 0) {
      throw new Error('Тело сниппета должно быть непустым массивом');
    }

    if (snippet.variables && !Array.isArray(snippet.variables)) {
      throw new Error('Переменные сниппета должны быть массивом');
    }
  }

  private generateCacheKey(context: CodeContext): string {
    const key = `${context.fileName}_${context.language}_${context.cursor.line}_${context.cursor.character}`;
    return btoa(key).replace(/[^a-zA-Z0-9]/g, '');
  }

  private generateAnalysisCacheKey(context: CodeContext): string {
    const key = `${context.fileName}_${context.version || '0'}_${context.content.length}`;
    return btoa(key).replace(/[^a-zA-Z0-9]/g, '');
  }

  private generateId(): string {
    return `completion_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}

// Экспортируем instance по умолчанию
export const codeAutocompleteService = new CodeAutocompleteService();