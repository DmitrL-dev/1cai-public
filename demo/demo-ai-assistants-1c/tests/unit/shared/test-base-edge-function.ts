/**
 * Unit tests for BaseEdgeFunction class
 * Tests CORS handling, request validation, error handling, and response creation
 */

import { assertEquals, assertThrows, assertExists, assert } from 'https://deno.land/std/testing/asserts.ts';
import { BaseEdgeFunction } from '../../../supabase/shared/BaseEdgeFunction.ts';

// Concrete implementation for testing
class TestEdgeFunction extends BaseEdgeFunction {
  constructor() {
    super('TestService', '1.0.0');
  }

  protected async executeDemo(request: any) {
    return {
      steps: [
        { progress: 25, message: 'Step 1' },
        { progress: 75, message: 'Step 2' }
      ],
      finalResult: { result: 'success' }
    };
  }
}

Deno.test('BaseEdgeFunction - CORS handling', async () => {
  const edgeFunction = new TestEdgeFunction();

  // Test OPTIONS request handling
  const corsRequest = new Request('http://localhost:8000', {
    method: 'OPTIONS'
  });

  const response = await edgeFunction.handleRequest(corsRequest);
  
  assertEquals(response.status, 200);
  assertExists(response.headers.get('Access-Control-Allow-Origin'));
  assertEquals(response.headers.get('Access-Control-Allow-Headers'), 'authorization, x-client-info, apikey, content-type');
  assertEquals(response.headers.get('Access-Control-Allow-Methods'), 'POST, GET, OPTIONS');
});

Deno.test('BaseEdgeFunction - Request validation', async () => {
  const edgeFunction = new TestEdgeFunction();

  // Test unsupported method
  const deleteRequest = new Request('http://localhost:8000', {
    method: 'DELETE'
  });

  const deleteValidation = await edgeFunction.validateRequest(deleteRequest);
  assertEquals(deleteValidation.isValid, false);
  assertEquals(deleteValidation.errors.length, 1);
  assert(deleteValidation.errors[0].includes('Unsupported method'));

  // Test POST without JSON content-type
  const postRequest = new Request('http://localhost:8000', {
    method: 'POST',
    headers: {
      'Content-Type': 'text/plain'
    }
  });

  const postValidation = await edgeFunction.validateRequest(postRequest);
  assertEquals(postValidation.isValid, false);
  assertEquals(postValidation.errors.length, 1);
  assert(postValidation.errors[0].includes('Content-Type'));

  // Test valid POST request
  const validRequest = new Request('http://localhost:8000', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  });

  const validValidation = await edgeFunction.validateRequest(validRequest);
  assertEquals(validValidation.isValid, true);
  assertEquals(validValidation.errors.length, 0);
});

Deno.test('BaseEdgeFunction - Request parsing', async () => {
  const edgeFunction = new TestEdgeFunction();

  // Test invalid request data
  assertThrows(() => {
    edgeFunction.parseRequest(null);
  });

  assertThrows(() => {
    edgeFunction.parseRequest('invalid');
  });

  // Test missing demoType
  assertThrows(() => {
    edgeFunction.parseRequest({ userQuery: 'test query' });
  });

  // Test valid request parsing
  const validRequest = edgeFunction.parseRequest({
    demoType: 'test',
    userQuery: 'test query'
  });

  assertEquals(validRequest.demoType, 'test');
  assertEquals(validRequest.userQuery, 'test query');
});

Deno.test('BaseEdgeFunction - Progress steps creation', async () => {
  const edgeFunction = new TestEdgeFunction();

  const steps = edgeFunction.createProgressSteps([
    { message: 'Step 1', delay: 100 },
    { message: 'Step 2', delay: 200 },
    { message: 'Step 3', delay: 300 }
  ]);

  assertEquals(steps.length, 3);
  assertEquals(steps[0].progress, 30); // 90/3 = 30
  assertEquals(steps[1].progress, 60);
  assertEquals(steps[2].progress, 90);
  assertEquals(steps[0].message, 'Step 1');
});

Deno.test('BaseEdgeFunction - Error response creation', async () => {
  const edgeFunction = new TestEdgeFunction();

  const errorResponse = edgeFunction.createErrorResponse(
    'TEST_ERROR',
    'Test error message',
    400,
    { field: 'testField' }
  );

  assertEquals(errorResponse.status, 400);
  
  const responseBody = await errorResponse.json();
  assertEquals(responseBody.error.code, 'TEST_ERROR');
  assertEquals(responseBody.error.message, 'Test error message');
  assertExists(responseBody.error.timestamp);
  assertExists(responseBody.error.requestId);
  assertEquals(responseBody.error.service, 'TestService');
  assertEquals(responseBody.error.version, '1.0.0');
  assertEquals(responseBody.error.field, 'testField');
});

Deno.test('BaseEdgeFunction - Success response creation', async () => {
  const edgeFunction = new TestEdgeFunction();

  const result = {
    steps: [{ progress: 50, message: 'Test step' }],
    finalResult: { success: true }
  };

  const response = edgeFunction.createSuccessResponse(result);
  assertEquals(response.status, 200);

  const responseBody = await response.json();
  assertEquals(responseBody.data.steps.length, 1);
  assertEquals(responseBody.data.finalResult.success, true);
});

Deno.test('BaseEdgeFunction - Metadata creation', async () => {
  const edgeFunction = new TestEdgeFunction();

  const metadata = edgeFunction.getMetadata('100ms', ['feature1', 'feature2']);

  assertEquals(metadata.service, 'TestService');
  assertEquals(metadata.version, '1.0.0');
  assertExists(metadata.timestamp);
  assertEquals(metadata.processingTime, '100ms');
  assertEquals(metadata.supportedLanguages.length, 2);
  assertEquals(metadata.capabilities.length, 2);
});

Deno.test('BaseEdgeFunction - Full request handling flow', async () => {
  const edgeFunction = new TestEdgeFunction();

  // Test successful request handling
  const successRequest = new Request('http://localhost:8000', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      demoType: 'test',
      userQuery: 'Test query'
    })
  });

  const response = await edgeFunction.handleRequest(successRequest);
  assertEquals(response.status, 200);

  const responseBody = await response.json();
  assertExists(responseBody.data);
  assertEquals(responseBody.data.steps.length, 2);
  assertEquals(responseBody.data.finalResult.result, 'success');
});

Deno.test('BaseEdgeFunction - Invalid request handling', async () => {
  const edgeFunction = new TestEdgeFunction();

  // Test request with missing demoType
  const invalidRequest = new Request('http://localhost:8000', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      userQuery: 'Test query'
    })
  });

  const response = await edgeFunction.handleRequest(invalidRequest);
  assertEquals(response.status, 500);

  const responseBody = await response.json();
  assertEquals(responseBody.error.code, 'INTERNAL_ERROR');
  assert(responseBody.error.message.includes('demoType'));
});

Deno.test('BaseEdgeFunction - Service name and version', async () => {
  const edgeFunction = new TestEdgeFunction();
  
  // The constructor sets these values, test they are accessible
  assertEquals((edgeFunction as any).serviceName, 'TestService');
  assertEquals((edgeFunction as any).serviceVersion, '1.0.0');
});

Deno.test('BaseEdgeFunction - CORS headers consistency', async () => {
  const edgeFunction = new TestEdgeFunction();

  const request = new Request('http://localhost:8000', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      demoType: 'test',
      userQuery: 'Test query'
    })
  });

  const response = await edgeFunction.handleRequest(request);
  
  // Check CORS headers are present in response
  assertExists(response.headers.get('Access-Control-Allow-Origin'));
  assertExists(response.headers.get('Access-Control-Allow-Headers'));
  assertExists(response.headers.get('Access-Control-Allow-Methods'));
  assertEquals(response.headers.get('Content-Type'), 'application/json');
});