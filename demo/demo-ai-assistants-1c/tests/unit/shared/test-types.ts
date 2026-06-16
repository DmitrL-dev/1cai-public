/**
 * Unit tests for shared types
 * Tests type definitions and structure validation
 */

import { assertEquals, assert, assertExists } from 'https://deno.land/std/testing/asserts.ts';
import {
  BaseRequest,
  ProgressStep,
  DemoResponse,
  ErrorResponse,
  ValidationResult,
  ServiceMetadata
} from '../../../supabase/shared/types.ts';

Deno.test('Types - BaseRequest interface', () => {
  // Test valid BaseRequest
  const validRequest: BaseRequest = {
    demoType: 'test',
    userQuery: 'test query'
  };
  
  assertEquals(validRequest.demoType, 'test');
  assertEquals(validRequest.userQuery, 'test query');
  
  // Test BaseRequest without optional field
  const minimalRequest: BaseRequest = {
    demoType: 'test'
  };
  
  assertEquals(minimalRequest.demoType, 'test');
  assertEquals(minimalRequest.userQuery, undefined);
});

Deno.test('Types - ProgressStep interface', () => {
  const validStep: ProgressStep = {
    progress: 50,
    message: 'Processing...',
    result: { data: 'processed' }
  };
  
  assertEquals(validStep.progress, 50);
  assertEquals(validStep.message, 'Processing...');
  assertEquals(validStep.result?.data, 'processed');
  
  // Test ProgressStep without optional result
  const minimalStep: ProgressStep = {
    progress: 25,
    message: 'Starting...'
  };
  
  assertEquals(minimalStep.progress, 25);
  assertEquals(minimalStep.message, 'Starting...');
  assertEquals(minimalStep.result, undefined);
});

Deno.test('Types - DemoResponse interface', () => {
  const validResponse: DemoResponse = {
    data: {
      steps: [
        { progress: 25, message: 'Step 1' },
        { progress: 75, message: 'Step 2' }
      ],
      finalResult: { success: true }
    }
  };
  
  assertExists(validResponse.data);
  assertEquals(validResponse.data.steps.length, 2);
  assertEquals(validResponse.data.finalResult.success, true);
  
  // Test with minimal data
  const minimalResponse: DemoResponse = {
    data: {
      steps: [],
      finalResult: null
    }
  };
  
  assertEquals(minimalResponse.data.steps.length, 0);
  assertEquals(minimalResponse.data.finalResult, null);
});

Deno.test('Types - ErrorResponse interface', () => {
  const errorResponse: ErrorResponse = {
    error: {
      code: 'TEST_ERROR',
      message: 'Test error message',
      timestamp: '2023-01-01T00:00:00Z',
      requestId: 'req-123',
      service: 'test-service',
      version: '1.0.0',
      field: 'additional field'
    }
  };
  
  assertEquals(errorResponse.error.code, 'TEST_ERROR');
  assertEquals(errorResponse.error.message, 'Test error message');
  assertEquals(errorResponse.error.timestamp, '2023-01-01T00:00:00Z');
  assertEquals(errorResponse.error.requestId, 'req-123');
  assertEquals(errorResponse.error.service, 'test-service');
  assertEquals(errorResponse.error.version, '1.0.0');
  assertEquals(errorResponse.error.field, 'additional field');
});

Deno.test('Types - ValidationResult interface', () => {
  const validResult: ValidationResult = {
    isValid: true,
    errors: []
  };
  
  assertEquals(validResult.isValid, true);
  assertEquals(validResult.errors.length, 0);
  
  // Test with errors
  const invalidResult: ValidationResult = {
    isValid: false,
    errors: ['Error 1', 'Error 2']
  };
  
  assertEquals(invalidResult.isValid, false);
  assertEquals(invalidResult.errors.length, 2);
  assertEquals(invalidResult.errors[0], 'Error 1');
  assertEquals(invalidResult.errors[1], 'Error 2');
});

Deno.test('Types - ServiceMetadata interface', () => {
  const metadata: ServiceMetadata = {
    service: 'test-service',
    version: '1.0.0',
    timestamp: '2023-01-01T00:00:00Z',
    processingTime: '100ms',
    supportedLanguages: ['ru', 'en'],
    capabilities: ['feature1', 'feature2']
  };
  
  assertEquals(metadata.service, 'test-service');
  assertEquals(metadata.version, '1.0.0');
  assertEquals(metadata.timestamp, '2023-01-01T00:00:00Z');
  assertEquals(metadata.processingTime, '100ms');
  assertEquals(metadata.supportedLanguages.length, 2);
  assertEquals(metadata.capabilities.length, 2);
  assert(metadata.supportedLanguages.includes('ru'));
  assert(metadata.supportedLanguages.includes('en'));
});

Deno.test('Types - Type compatibility and structure', () => {
  // Test that objects match expected interfaces
  const request: BaseRequest = { demoType: 'test' };
  const step: ProgressStep = { progress: 50, message: 'test' };
  const response: DemoResponse = { data: { steps: [step], finalResult: null } };
  const error: ErrorResponse = { error: { code: 'ERR', message: 'msg' } };
  const validation: ValidationResult = { isValid: true, errors: [] };
  const meta: ServiceMetadata = {
    service: 'svc',
    version: '1.0',
    timestamp: '2023-01-01T00:00:00Z',
    processingTime: '100ms',
    supportedLanguages: ['en'],
    capabilities: []
  };
  
  // Basic structure validation
  assert(typeof request.demoType === 'string');
  assert(typeof step.progress === 'number');
  assert(typeof step.message === 'string');
  assert(Array.isArray(response.data.steps));
  assert(typeof error.error.code === 'string');
  assert(typeof validation.isValid === 'boolean');
  assert(Array.isArray(validation.errors));
  assert(Array.isArray(meta.supportedLanguages));
  assert(Array.isArray(meta.capabilities));
});

Deno.test('Types - Extended ErrorResponse properties', () => {
  // Test that ErrorResponse can have additional properties
  const extendedError: ErrorResponse = {
    error: {
      code: 'EXTENDED_ERROR',
      message: 'Extended error details',
      timestamp: '2023-01-01T00:00:00Z',
      requestId: 'req-456',
      service: 'extended-service',
      version: '2.0.0',
      customField1: 'custom value 1',
      customField2: 42,
      customField3: { nested: 'object' }
    }
  };
  
  assertEquals(extendedError.error.customField1, 'custom value 1');
  assertEquals(extendedError.error.customField2, 42);
  assertEquals(extendedError.error.customField3.nested, 'object');
});

Deno.test('Types - Nested object structures', () => {
  // Test complex nested structures
  const complexResponse: DemoResponse = {
    data: {
      steps: [
        {
          progress: 10,
          message: 'Initializing',
          result: { status: 'started', data: { id: 1 } }
        },
        {
          progress: 50,
          message: 'Processing',
          result: { status: 'processing', data: { progress: 0.5 } }
        },
        {
          progress: 100,
          message: 'Completed',
          result: { status: 'completed', data: { result: 'success' } }
        }
      ],
      finalResult: {
        status: 'success',
        data: {
          processedItems: 100,
          errors: [],
          metadata: {
            duration: '1.2s',
            memoryUsed: '50MB'
          }
        }
      }
    }
  };
  
  assertEquals(complexResponse.data.steps.length, 3);
  assertEquals(complexResponse.data.steps[0].result?.data.id, 1);
  assertEquals(complexResponse.data.finalResult.data.metadata.duration, '1.2s');
  assertEquals(complexResponse.data.finalResult.data.metadata.memoryUsed, '50MB');
});

Deno.test('Types - ProgressStep validation', () => {
  // Test progress boundaries
  const step0: ProgressStep = { progress: 0, message: 'Start' };
  const step50: ProgressStep = { progress: 50, message: 'Middle' };
  const step100: ProgressStep = { progress: 100, message: 'Complete' };
  
  assertEquals(step0.progress, 0);
  assertEquals(step50.progress, 50);
  assertEquals(step100.progress, 100);
  
  // Test edge cases for progress
  const stepNegative: ProgressStep = { progress: -10, message: 'Invalid' };
  const stepOver100: ProgressStep = { progress: 150, message: 'Invalid' };
  
  assertEquals(stepNegative.progress, -10);
  assertEquals(stepOver100.progress, 150);
});

Deno.test('Types - ServiceMetadata language support', () => {
  // Test different language configurations
  const russianMeta: ServiceMetadata = {
    service: 'ru-service',
    version: '1.0.0',
    timestamp: '2023-01-01T00:00:00Z',
    processingTime: '50ms',
    supportedLanguages: ['ru'],
    capabilities: ['localization']
  };
  
  const englishMeta: ServiceMetadata = {
    service: 'en-service',
    version: '1.0.0',
    timestamp: '2023-01-01T00:00:00Z',
    processingTime: '50ms',
    supportedLanguages: ['en'],
    capabilities: ['global']
  };
  
  const multilingualMeta: ServiceMetadata = {
    service: 'multi-service',
    version: '1.0.0',
    timestamp: '2023-01-01T00:00:00Z',
    processingTime: '50ms',
    supportedLanguages: ['ru', 'en', 'de', 'fr'],
    capabilities: ['multilingual']
  };
  
  assertEquals(russianMeta.supportedLanguages.length, 1);
  assertEquals(englishMeta.supportedLanguages.length, 1);
  assertEquals(multilingualMeta.supportedLanguages.length, 4);
});

Deno.test('Types - ValidationResult error scenarios', () => {
  // Test various validation scenarios
  const emptyErrors: ValidationResult = {
    isValid: true,
    errors: []
  };
  
  const singleError: ValidationResult = {
    isValid: false,
    errors: ['Missing required field']
  };
  
  const multipleErrors: ValidationResult = {
    isValid: false,
    errors: [
      'Field1 is required',
      'Field2 must be a string',
      'Field3 has invalid format'
    ]
  };
  
  assertEquals(emptyErrors.errors.length, 0);
  assertEquals(singleError.errors.length, 1);
  assertEquals(multipleErrors.errors.length, 3);
  assert(emptyErrors.isValid);
  assert(!singleError.isValid);
  assert(!multipleErrors.isValid);
});

Deno.test('Types - Interface extensibility', () => {
  // Test that interfaces can be extended with additional properties
  const extendedRequest: BaseRequest = {
    demoType: 'extended',
    userQuery: 'extended query',
    additionalField: 'additional value',
    metadata: { key: 'value' }
  };
  
  const extendedStep: ProgressStep = {
    progress: 75,
    message: 'Extended step',
    result: 'extended result',
    customData: { custom: 'data' }
  };
  
  assertEquals(extendedRequest.additionalField, 'additional value');
  assertEquals(extendedRequest.metadata?.key, 'value');
  assertEquals(extendedStep.customData?.custom, 'data');
});

Deno.test('Types - Type safety and compilation', () => {
  // These tests ensure TypeScript compilation succeeds
  // and that the types work as expected
  
  const request: BaseRequest = { demoType: 'test' };
  const step: ProgressStep = { progress: 100, message: 'done' };
  const response: DemoResponse = { data: { steps: [step], finalResult: {} } };
  
  // Type assertions that should compile without errors
  const demoType: string = request.demoType;
  const progress: number = step.progress;
  const message: string = step.message;
  const steps: ProgressStep[] = response.data.steps;
  
  assertEquals(demoType, 'test');
  assertEquals(progress, 100);
  assertEquals(message, 'done');
  assertEquals(steps.length, 1);
});

Deno.test('Types - Optional vs required fields', () => {
  // Test which fields are optional vs required
  const minimalRequest: BaseRequest = { demoType: 'test' };
  const fullRequest: BaseRequest = { 
    demoType: 'test', 
    userQuery: 'query' 
  };
  
  // Both should be valid
  assert(minimalRequest.demoType !== undefined);
  assert(fullRequest.userQuery !== undefined);
  
  const minimalStep: ProgressStep = { progress: 0, message: 'start' };
  const fullStep: ProgressStep = { 
    progress: 100, 
    message: 'complete', 
    result: 'success' 
  };
  
  assert(minimalStep.progress !== undefined);
  assert(minimalStep.message !== undefined);
  assert(fullStep.result !== undefined);
});