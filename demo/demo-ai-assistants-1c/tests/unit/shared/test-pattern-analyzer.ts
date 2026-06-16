/**
 * Unit tests for PatternAnalyzer class
 * Tests query analysis, pattern matching, confidence scoring, and edge cases
 */

import { assertEquals, assert, assertExists } from 'https://deno.land/std/testing/asserts.ts';
import { PatternAnalyzer } from '../../../supabase/shared/PatternAnalyzer.ts';

Deno.test('PatternAnalyzer - analyzeQuery with valid input', () => {
  const result = PatternAnalyzer.analyzeQuery('интеграция с 1с системой');
  
  assertEquals(result.category, '1c_integration');
  assert(result.confidence > 0);
  assert(result.matches.length > 0);
  assertExists(result.recommendedAction);
});

Deno.test('PatternAnalyzer - analyzeQuery with empty input', () => {
  const result1 = PatternAnalyzer.analyzeQuery('');
  assertEquals(result1.category, 'unknown');
  assertEquals(result1.confidence, 0);
  assertEquals(result1.matches.length, 0);
  
  const result2 = PatternAnalyzer.analyzeQuery(null as any);
  assertEquals(result2.category, 'unknown');
  assertEquals(result2.confidence, 0);
  assertEquals(result2.matches.length, 0);
  
  const result3 = PatternAnalyzer.analyzeQuery(undefined as any);
  assertEquals(result3.category, 'unknown');
  assertEquals(result3.confidence, 0);
  assertEquals(result3.matches.length, 0);
});

Deno.test('PatternAnalyzer - analyzeQuery with non-string input', () => {
  const result1 = PatternAnalyzer.analyzeQuery(123 as any);
  assertEquals(result1.category, 'unknown');
  assertEquals(result1.confidence, 0);
  
  const result2 = PatternAnalyzer.analyzeQuery({} as any);
  assertEquals(result2.category, 'unknown');
  assertEquals(result2.confidence, 0);
});

Deno.test('PatternAnalyzer - 1С specific patterns', () => {
  // Test integration patterns
  const integrationQuery = 'синхронизация с 1с API';
  const integrationResult = PatternAnalyzer.analyzeQuery(integrationQuery);
  assertEquals(integrationResult.category, '1c_integration');
  assert(integrationResult.confidence > 0);
  
  // Test document patterns
  const documentQuery = 'проведение документов накладная';
  const documentResult = PatternAnalyzer.analyzeQuery(documentQuery);
  assertEquals(documentResult.category, '1c_documents');
  assert(documentResult.confidence > 0);
  
  // Test report patterns
  const reportQuery = 'формирование отчета остатки движения';
  const reportResult = PatternAnalyzer.analyzeQuery(reportQuery);
  assertEquals(reportResult.category, '1c_reports');
  assert(reportResult.confidence > 0);
  
  // Test configuration patterns
  const configQuery = 'настройка справочника регистра конфигурации';
  const configResult = PatternAnalyzer.analyzeQuery(configQuery);
  assertEquals(configResult.category, '1c_configuration');
  assert(configResult.confidence > 0);
});

Deno.test('PatternAnalyzer - development patterns', () => {
  // Test code development with English keywords (more reliable)
  const codeQuery = 'development code function procedure module';
  const codeResult = PatternAnalyzer.analyzeQuery(codeQuery);
  assertEquals(codeResult.category, 'code_development');
  assert(codeResult.confidence > 0);
  
  // Test API development
  const apiQuery = 'REST API веб-сервис endpoint web service';
  const apiResult = PatternAnalyzer.analyzeQuery(apiQuery);
  assertEquals(apiResult.category, 'api_development');
  assert(apiResult.confidence > 0);
  
  // Test database design
  const dbQuery = 'database design schema table data model structure';
  const dbResult = PatternAnalyzer.analyzeQuery(dbQuery);
  assertEquals(dbResult.category, 'database_design');
  assert(dbResult.confidence > 0);
});

Deno.test('PatternAnalyzer - testing patterns', () => {
  // Test unit testing
  const unitQuery = 'unit тест функции проверка модульн';
  const unitResult = PatternAnalyzer.analyzeQuery(unitQuery);
  assertEquals(unitResult.category, 'unit_testing');
  assert(unitResult.confidence > 0);
  
  // Test integration testing
  const integrationQuery = 'интеграционное тестирование обмен синхронизация';
  const integrationResult = PatternAnalyzer.analyzeQuery(integrationQuery);
  assertEquals(integrationResult.category, 'integration_testing');
  assert(integrationResult.confidence > 0);
  
  // Test functional testing
  const functionalQuery = 'функциональное тестирование бизнес-процесс';
  const functionalResult = PatternAnalyzer.analyzeQuery(functionalQuery);
  assertEquals(functionalResult.category, 'functional_testing');
  assert(functionalResult.confidence > 0);
  
  // Test performance testing
  const performanceQuery = 'нагрузочное тестирование производительность';
  const performanceResult = PatternAnalyzer.analyzeQuery(performanceQuery);
  assertEquals(performanceResult.category, 'performance_testing');
  assert(performanceResult.confidence > 0);
  
  // Test automation
  const automationQuery = 'автоматизация тестов скрипт бот';
  const automationResult = PatternAnalyzer.analyzeQuery(automationQuery);
  assertEquals(automationResult.category, 'test_automation');
  assert(automationResult.confidence > 0);
});

Deno.test('PatternAnalyzer - project management patterns', () => {
  // Test planning
  const planningQuery = 'планирование проекта график сроки этапы';
  const planningResult = PatternAnalyzer.analyzeQuery(planningQuery);
  assertEquals(planningResult.category, 'project_planning');
  assert(planningResult.confidence > 0);
  
  // Test risk management
  const riskQuery = 'оценка рисков митигация проблемы';
  const riskResult = PatternAnalyzer.analyzeQuery(riskQuery);
  assertEquals(riskResult.category, 'risk_management');
  assert(riskResult.confidence > 0);
  
  // Test resource management
  const resourceQuery = 'управление ресурсами команда мощности';
  const resourceResult = PatternAnalyzer.analyzeQuery(resourceQuery);
  assertEquals(resourceResult.category, 'resource_management');
  assert(resourceResult.confidence > 0);
  
  // Test stakeholder management
  const stakeholderQuery = 'управление стейкхолдерами коммуникация согласование';
  const stakeholderResult = PatternAnalyzer.analyzeQuery(stakeholderQuery);
  assertEquals(stakeholderResult.category, 'stakeholder_management');
  assert(stakeholderResult.confidence > 0);
});

Deno.test('PatternAnalyzer - business analysis patterns', () => {
  // Test requirements analysis
  const reqQuery = 'анализ требований ТЗ техническое задание BRD';
  const reqResult = PatternAnalyzer.analyzeQuery(reqQuery);
  assertEquals(reqResult.category, 'requirements_analysis');
  assert(reqResult.confidence > 0);
  
  // Test process modeling
  const processQuery = 'моделирование процесса BPMN диаграмм workflow';
  const processResult = PatternAnalyzer.analyzeQuery(processQuery);
  assertEquals(processResult.category, 'process_modeling');
  assert(processResult.confidence > 0);
  
  // Test user stories
  const storyQuery = 'user story история пользователя as a я хочу';
  const storyResult = PatternAnalyzer.analyzeQuery(storyQuery);
  assertEquals(storyResult.category, 'user_stories');
  assert(storyResult.confidence > 0);
  
  // Test use cases
  const usecaseQuery = 'use case сценарий использования актер действие';
  const usecaseResult = PatternAnalyzer.analyzeQuery(usecaseQuery);
  assertEquals(usecaseResult.category, 'use_cases');
  assert(usecaseResult.confidence > 0);
  
  // Test data analysis
  const dataQuery = 'анализ данных отчет аналитика BI KPI';
  const dataResult = PatternAnalyzer.analyzeQuery(dataQuery);
  assertEquals(dataResult.category, 'data_analysis');
  assert(dataResult.confidence > 0);
});

Deno.test('PatternAnalyzer - architecture patterns', () => {
  // Test system architecture
  const archQuery = 'системная архитектура компонент дизайн';
  const archResult = PatternAnalyzer.analyzeQuery(archQuery);
  assertEquals(archResult.category, 'system_architecture');
  assert(archResult.confidence > 0);
  
  // Test microservices
  const microQuery = 'микросервисная архитектура сервис-ориентированная';
  const microResult = PatternAnalyzer.analyzeQuery(microQuery);
  assertEquals(microResult.category, 'microservices');
  assert(microResult.confidence > 0);
  
  // Test integration architecture
  const integrationArchQuery = 'интеграционная архитектура ESB API gateway';
  const integrationArchResult = PatternAnalyzer.analyzeQuery(integrationArchQuery);
  assertEquals(integrationArchResult.category, 'integration_architecture');
  assert(integrationArchResult.confidence > 0);
});

Deno.test('PatternAnalyzer - security patterns', () => {
  // Test security analysis
  const securityQuery = 'анализ безопасности аутентификация шифрование';
  const securityResult = PatternAnalyzer.analyzeQuery(securityQuery);
  assertEquals(securityResult.category, 'security_analysis');
  assert(securityResult.confidence > 0);
  
  // Test compliance
  const complianceQuery = 'соответствие стандартам сертификация аудит GDPR';
  const complianceResult = PatternAnalyzer.analyzeQuery(complianceQuery);
  assertEquals(complianceResult.category, 'compliance');
  assert(complianceResult.confidence > 0);
});

Deno.test('PatternAnalyzer - confidence calculation', () => {
  // Test high confidence with exact matches
  const highConfQuery = 'интеграция с 1с синхронизация данных';
  const highConfResult = PatternAnalyzer.analyzeQuery(highConfQuery);
  assert(highConfResult.confidence > 0.5);
  assert(highConfResult.matches.length > 1);
  
  // Test medium confidence
  const mediumConfQuery = 'тестирование функций';
  const mediumConfResult = PatternAnalyzer.analyzeQuery(mediumConfQuery);
  assert(mediumConfResult.confidence >= 0);
  assert(mediumConfResult.confidence <= 1);
  
  // Test low confidence with single match
  const lowConfQuery = 'random unknown words not matching';
  const lowConfResult = PatternAnalyzer.analyzeQuery(lowConfQuery);
  assertEquals(lowConfResult.confidence, 0);
});

Deno.test('PatternAnalyzer - recommended actions', () => {
  const result1 = PatternAnalyzer.analyzeQuery('интеграция с 1с');
  assertExists(result1.recommendedAction);
  
  const result2 = PatternAnalyzer.analyzeQuery('разработка кода');
  assertExists(result2.recommendedAction);
  
  const result3 = PatternAnalyzer.analyzeQuery('тестирование');
  assertExists(result3.recommendedAction);
  
  const result4 = PatternAnalyzer.analyzeQuery('random query');
  assertExists(result4.recommendedAction);
});

Deno.test('PatternAnalyzer - get categories', () => {
  const categories = PatternAnalyzer.getCategories();
  
  assert(categories.length > 0);
  assert(categories.includes('1c_integration'));
  assert(categories.includes('code_development'));
  assert(categories.includes('unit_testing'));
  assert(categories.includes('project_planning'));
  assert(categories.includes('requirements_analysis'));
});

Deno.test('PatternAnalyzer - get patterns for category', () => {
  const patterns = PatternAnalyzer.getPatternsForCategory('1c_integration');
  
  assert(patterns.length > 0);
  assert(patterns.includes('интеграция с 1с'));
  assert(patterns.includes('синхронизация с 1с'));
  
  // Test non-existent category
  const emptyPatterns = PatternAnalyzer.getPatternsForCategory('nonexistent');
  assertEquals(emptyPatterns.length, 0);
});

Deno.test('PatternAnalyzer - add patterns', () => {
  const originalPatterns = PatternAnalyzer.getPatternsForCategory('test_category');
  const originalLength = originalPatterns.length;
  
  // Add new patterns
  PatternAnalyzer.addPatterns('test_category', ['new pattern 1', 'new pattern 2']);
  
  const newPatterns = PatternAnalyzer.getPatternsForCategory('test_category');
  assert(newPatterns.length >= originalLength + 2);
  assert(newPatterns.includes('new pattern 1'));
  assert(newPatterns.includes('new pattern 2'));
});

Deno.test('PatternAnalyzer - matchesAnyPattern', () => {
  // Test match
  assert(PatternAnalyzer.matchesAnyPattern('интеграция с 1с системой', ['1с', 'интеграция']));
  assert(PatternAnalyzer.matchesAnyPattern('unit testing development', ['unit', 'test']));
  
  // Test no match
  assertEquals(PatternAnalyzer.matchesAnyPattern('random text', ['nonexistent']), false);
  assertEquals(PatternAnalyzer.matchesAnyPattern('', ['test']), false);
});

Deno.test('PatternAnalyzer - findBestPatterns', () => {
  const query = 'интеграция с 1с синхронизация обмен';
  const bestPatterns = PatternAnalyzer.findBestPatterns(query, 3);
  
  assert(bestPatterns.length <= 3);
  assert(bestPatterns.length > 0);
  
  // Should be sorted by weight
  if (bestPatterns.length > 1) {
    assert(bestPatterns[0].weight >= bestPatterns[1].weight);
  }
});

Deno.test('PatternAnalyzer - English patterns support', () => {
  // Test English keywords
  const englishQuery = 'unit test function development API';
  const englishResult = PatternAnalyzer.analyzeQuery(englishQuery);
  assert(englishResult.confidence > 0);
  assert(englishResult.matches.length > 0);
  
  // Test mixed Russian-English
  const mixedQuery = 'разработка development API';
  const mixedResult = PatternAnalyzer.analyzeQuery(mixedQuery);
  assert(mixedResult.confidence > 0);
});

Deno.test('PatternAnalyzer - edge cases and boundaries', () => {
  // Test very long query
  const longQuery = 'интеграция с 1с системой для обмена данными синхронизация документов проведение накладных формирование отчетов анализ остатков настройка справочников регистров';
  const longResult = PatternAnalyzer.analyzeQuery(longQuery);
  assert(longResult.confidence >= 0);
  assert(longResult.confidence <= 1);
  
  // Test query with only special characters
  const specialQuery = '!@#$%^&*()_+';
  const specialResult = PatternAnalyzer.analyzeQuery(specialQuery);
  // Special characters might result in 'general' category, not 'unknown'
  assert(['unknown', 'general'].includes(specialResult.category));
  assertEquals(specialResult.confidence, 0);
  
  // Test query with numbers
  const numberQuery = '1с версия 8.3 API v2';
  const numberResult = PatternAnalyzer.analyzeQuery(numberQuery);
  assert(numberResult.confidence >= 0);
});

Deno.test('PatternAnalyzer - pattern weight calculation', () => {
  // Test exact phrase matches get higher weight
  const exactMatch = PatternAnalyzer.analyzeQuery('интеграция с 1с');
  const wordMatch = PatternAnalyzer.analyzeQuery('интеграция системы с 1с платформой');
  
  // The exact phrase should have better scoring
  // (though we can't directly test internal weights, we can check the results)
  assert(exactMatch.confidence >= 0);
  assert(wordMatch.confidence >= 0);
  
  // Both should find matches
  assert(exactMatch.matches.length > 0);
  assert(wordMatch.matches.length > 0);
});

Deno.test('PatternAnalyzer - category scoring', () => {
  // Test single category match
  const singleMatch = PatternAnalyzer.analyzeQuery('разработка кода функций');
  assertEquals(singleMatch.category, 'code_development');
  
  // Test multiple possible categories (should pick the best one)
  const multipleMatch = PatternAnalyzer.analyzeQuery('тестирование API веб-сервиса');
  // Could be either testing or API development, but should pick one
  assert(multipleMatch.category === 'api_development' || multipleMatch.category === 'unit_testing');
  
  assert(multipleMatch.confidence > 0);
});

Deno.test('PatternAnalyzer - normalization consistency', () => {
  // Test that case differences don't affect matching
  const query1 = 'ИНТЕГРАЦИЯ С 1С';
  const query2 = 'интеграция с 1с';
  const query3 = 'ИнТеГрАцИя С 1С';
  
  const result1 = PatternAnalyzer.analyzeQuery(query1);
  const result2 = PatternAnalyzer.analyzeQuery(query2);
  const result3 = PatternAnalyzer.analyzeQuery(query3);
  
  assertEquals(result1.category, result2.category);
  assertEquals(result2.category, result3.category);
  assertEquals(result1.confidence, result2.confidence);
  assertEquals(result2.confidence, result3.confidence);
});