// K6 Load Testing Script
// Нагрузочное тестирование API

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');

// Test configuration
export const options = {
  stages: [
    // Ramp-up
    { duration: '1m', target: 50 },   // Ramp to 50 users over 1 min
    { duration: '3m', target: 50 },   // Stay at 50 for 3 min
    { duration: '1m', target: 100 },  // Ramp to 100
    { duration: '5m', target: 100 },  // Stay at 100 for 5 min
    { duration: '1m', target: 200 },  // Spike to 200
    { duration: '3m', target: 200 },  // Stay at 200
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% < 500ms
    http_req_failed: ['rate<0.01'],   // Error rate < 1%
    errors: ['rate<0.05'],             // Custom error < 5%
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

// Tenant authentication (mock)
const TENANT_HEADERS = {
  'Content-Type': 'application/json',
  'X-Tenant-ID': 'test-tenant-123',
  'Authorization': 'Bearer test-token',
};

export default function () {
  // Test 1: AI Query
  const aiQuery = {
    query: 'Как создать документ Заказ покупателя?',
    role: 'developer',
  };
  
  let response = http.post(
    `${BASE_URL}/api/ai/query`,
    JSON.stringify(aiQuery),
    { headers: TENANT_HEADERS }
  );
  
  check(response, {
    'AI query status 200': (r) => r.status === 200,
    'AI response has content': (r) => r.json('response') !== undefined,
  });
  
  errorRate.add(response.status !== 200);
  apiLatency.add(response.timings.duration);
  
  sleep(1);
  
  // Test 2: Metadata search
  response = http.get(
    `${BASE_URL}/api/metadata/search?query=Документ.Заказ`,
    { headers: TENANT_HEADERS }
  );
  
  check(response, {
    'Metadata search status 200': (r) => r.status === 200,
    'Metadata results not empty': (r) => r.json('results')?.length > 0,
  });
  
  errorRate.add(response.status !== 200);
  
  sleep(0.5);
  
  // Test 3: Code Review
  const codeReviewRequest = {
    code: `
Функция РассчитатьСумму(А, Б)
    Возврат А + Б;
КонецФункции
    `,
    filename: 'test.bsl',
  };
  
  response = http.post(
    `${BASE_URL}/api/code-review`,
    JSON.stringify(codeReviewRequest),
    { headers: TENANT_HEADERS }
  );
  
  check(response, {
    'Code review status 200': (r) => r.status === 200,
    'Review has status': (r) => r.json('overall_status') !== undefined,
  });
  
  errorRate.add(response.status !== 200);
  
  sleep(2);
  
  // Test 4: Copilot completion
  const completionRequest = {
    code: 'Функция РассчитатьНДС(Сумма)',
    current_line: '    СуммаНДС = ',
    max_suggestions: 3,
  };
  
  response = http.post(
    `${BASE_URL}/api/copilot/complete`,
    JSON.stringify(completionRequest),
    { headers: TENANT_HEADERS }
  );
  
  check(response, {
    'Copilot status 200': (r) => r.status === 200,
    'Has suggestions': (r) => r.json('suggestions')?.length > 0,
  });
  
  errorRate.add(response.status !== 200);
  
  sleep(1);
}

// Stress test scenario
export function stressTest() {
  const scenarios = {
    stress: {
      executor: 'ramping-arrival-rate',
      startRate: 10,
      timeUnit: '1s',
      preAllocatedVUs: 500,
      maxVUs: 1000,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 200 },
        { duration: '2m', target: 500 },
        { duration: '5m', target: 1000 },
        { duration: '5m', target: 0 },
      ],
    },
  };
}

// Spike test scenario
export function spikeTest() {
  const scenarios = {
    spike: {
      executor: 'constant-arrival-rate',
      duration: '2m',
      rate: 500,
      timeUnit: '1s',
      preAllocatedVUs: 1000,
    },
  };
}


