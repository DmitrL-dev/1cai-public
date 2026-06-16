import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const responseTime = new Trend('response_time');

// Test configuration
export const options = {
  stages: [
    // Ramp up from 0 to 100 VUs over 2 minutes
    { duration: '2m', target: 100 },
    // Stay at 100 VUs for 5 minutes
    { duration: '5m', target: 100 },
    // Ramp up from 100 to 500 VUs over 2 minutes
    { duration: '2m', target: 500 },
    // Stay at 500 VUs for 10 minutes
    { duration: '10m', target: 500 },
    // Ramp down from 500 to 0 VUs over 2 minutes
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    http_req_failed: ['rate<0.01'], // Error rate must be less than 1%
    checks: ['rate>0.95'], // 95% of checks must pass
  },
};

// Test data
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';
const API_TOKEN = __ENV.API_TOKEN || 'test-token';

// Test scenarios
export function setup() {
  console.log(`Starting load test against: ${BASE_URL}`);
  
  // Create test data
  const createResponse = http.post(`${BASE_URL}/api/v1/test-data`, {
    scenario: 'load_test',
    timestamp: Date.now(),
  }, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_TOKEN}`,
    },
  });
  
  return { testDataId: JSON.parse(createResponse.body).id };
}

// Main test function
export default function(data) {
  // Test scenario 1: Health check
  testHealthCheck();
  
  // Test scenario 2: AI Assistant requests
  testAssistantRequest(data);
  
  // Test scenario 3: Authentication
  testAuthentication();
  
  // Test scenario 4: Database queries
  testDatabaseQuery();
  
  // Test scenario 5: File upload
  testFileUpload();
  
  sleep(1);
}

// Test health check endpoint
function testHealthCheck() {
  const response = http.get(`${BASE_URL}/health`);
  
  const success = check(response, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 200ms': (r) => r.timings.duration < 200,
  });
  
  errorRate.add(!success);
  responseTime.add(response.timings.duration);
}

// Test AI Assistant requests
function testAssistantRequest(data) {
  const payload = {
    message: 'Test message for load testing',
    assistant: 'architect',
    context: {
      userId: 'test-user-123',
      sessionId: 'test-session-456',
      requestId: `test-${Date.now()}`,
    },
  };
  
  const response = http.post(
    `${BASE_URL}/api/v1/assistants/chat`,
    JSON.stringify(payload),
    {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_TOKEN}`,
      },
    }
  );
  
  const success = check(response, {
    'assistant request status is 200': (r) => r.status === 200,
    'assistant request response time < 1000ms': (r) => r.timings.duration < 1000,
    'assistant response contains content': (r) => JSON.parse(r.body).content !== undefined,
  });
  
  errorRate.add(!success);
  responseTime.add(response.timings.duration);
}

// Test authentication
function testAuthentication() {
  const response = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({
      username: 'testuser',
      password: 'testpass123',
    }),
    {
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );
  
  const success = check(response, {
    'login status is 200': (r) => r.status === 200,
    'login response time < 500ms': (r) => r.timings.duration < 500,
    'login returns token': (r) => JSON.parse(r.body).token !== undefined,
  });
  
  errorRate.add(!success);
  responseTime.add(response.timings.duration);
}

// Test database query
function testDatabaseQuery() {
  const response = http.get(
    `${BASE_URL}/api/v1/assistants/profile?userId=test-user-123`,
    {
      headers: {
        'Authorization': `Bearer ${API_TOKEN}`,
      },
    }
  );
  
  const success = check(response, {
    'profile query status is 200': (r) => r.status === 200,
    'profile query response time < 300ms': (r) => r.timings.duration < 300,
  });
  
  errorRate.add(!success);
  responseTime.add(response.timings.duration);
}

// Test file upload
function testFileUpload() {
  // Simulate file upload with small test data
  const testFile = 'data:text/plain;base64,' + btoa('This is test file content for load testing');
  
  const response = http.post(
    `${BASE_URL}/api/v1/files/upload`,
    {
      file: testFile,
      filename: 'test-load-file.txt',
      contentType: 'text/plain',
    },
    {
      headers: {
        'Authorization': `Bearer ${API_TOKEN}`,
      },
    }
  );
  
  const success = check(response, {
    'file upload status is 200': (r) => r.status === 200,
    'file upload response time < 2000ms': (r) => r.timings.duration < 2000,
  });
  
  errorRate.add(!success);
  responseTime.add(response.timings.duration);
}

// Teardown function
export function teardown(data) {
  console.log('Load test completed');
  console.log(`Total errors: ${__ENV.K6_ERRORS || 0}`);
  
  // Clean up test data
  if (data.testDataId) {
    http.del(`${BASE_URL}/api/v1/test-data/${data.testDataId}`, null, {
      headers: {
        'Authorization': `Bearer ${API_TOKEN}`,
      },
    });
  }
}

// Handle summary
export function handleSummary(data) {
  return {
    'load-test-summary.json': JSON.stringify(data),
    'load-test-summary.txt': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

function textSummary(data, options = {}) {
  const { indent = '', enableColors = false } = options;
  let summary = '';
  
  summary += `${indent}Load Test Results:\n`;
  summary += `${indent}==================\n`;
  summary += `${indent}Total Requests: ${data.metrics.http_reqs.values.count}\n`;
  summary += `${indent}Requests/sec: ${data.metrics.http_reqs.values.rate}\n`;
  summary += `${indent}Average Response Time: ${data.metrics.http_req_duration.values.avg}ms\n`;
  summary += `${indent}95th Percentile: ${data.metrics.http_req_duration.values['p(95)']}ms\n`;
  summary += `${indent}Max Response Time: ${data.metrics.http_req_duration.values.max}ms\n`;
  summary += `${indent}Error Rate: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%\n`;
  
  return summary;
}