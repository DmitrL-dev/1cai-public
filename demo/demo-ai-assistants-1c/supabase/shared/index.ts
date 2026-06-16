/**
 * Shared library for Edge Functions
 * Centralized exports for all common components
 */

// Core classes
export { BaseEdgeFunction } from './BaseEdgeFunction.ts';
export { EdgeFunctionTemplate } from './EdgeFunctionTemplate.ts';

// Types
export * from './types.ts';

// Utilities
export { TextAnalyzer, ResponseBuilder, ValidationUtils, TimeUtils, Constants } from './utils.ts';
export { PatternAnalyzer } from './PatternAnalyzer.ts';

// Re-export commonly used functions for convenience
export { BaseRequest, ProgressStep, DemoResponse, ErrorResponse } from './types.ts';
export { Constants } from './utils.ts';

// Service metadata helper
export const getServiceInfo = (serviceName: string, version: string = '1.0.0') => ({
  service: serviceName,
  version,
  timestamp: new Date().toISOString(),
  sharedLibrary: '1.0.0',
  capabilities: [
    'Common request handling',
    'Pattern analysis',
    'Response building',
    'Validation utilities',
    'Progress tracking'
  ]
});

// Error types for consistent error handling
export const ErrorTypes = {
  VALIDATION: 'VALIDATION_ERROR',
  PARSING: 'JSON_PARSE_ERROR', 
  INTERNAL: 'INTERNAL_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  UNAUTHORIZED: 'UNAUTHORIZED'
} as const;

// Common patterns for different AI assistants
export const AssistantPatterns = {
  DEVELOPER: {
    'code_generation': ['код', 'генерация', 'создать', 'development'],
    'api_design': ['api', 'интерфейс', 'endpoint', 'веб-сервис'],
    'architecture': ['архитектура', 'структура', 'дизайн']
  },
  ARCHITECT: {
    'system_design': ['архитектура', 'проектирование', 'system design'],
    'integration': ['интеграция', 'обмен', 'синхронизация'],
    'scalability': ['масштабирование', 'производительность']
  },
  PM: {
    'planning': ['планирование', 'план', 'график', 'сроки'],
    'resource_management': ['ресурсы', 'команда', 'мощности'],
    'risk_analysis': ['риски', 'оценка', 'митигация']
  },
  TESTER: {
    'test_cases': ['тест', 'тестирование', 'test case'],
    'automation': ['автоматизация', 'автотест', 'скрипт'],
    'coverage': ['покрытие', 'coverage', 'анализ']
  },
  BA: {
    'requirements': ['требования', 'requirements', 'тз'],
    'modeling': ['моделирование', 'диаграмм', 'bpmn'],
    'analysis': ['анализ', 'бизнес-процесс']
  }
} as const;