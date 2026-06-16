// Примеры использования API Gateway
// Демонстрирует различные сценарии работы

// Пример 1: Простой GET запрос к архитектор сервису
export async function exampleArchitectRequest() {
  const response = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/architect/analyze', {
    method: 'GET',
    headers: {
      'Authorization': 'Bearer demo-jwt-token',
      'X-Request-ID': 'req-12345'
    }
  });
  
  console.log('Response:', response.status);
  console.log('Headers:', Object.fromEntries(response.headers.entries()));
  
  if (response.ok) {
    const data = await response.json();
    console.log('Data:', data);
  } else {
    const error = await response.json();
    console.error('Error:', error);
  }
}

// Пример 2: POST запрос с API ключом
export async function exampleDeveloperRequest() {
  const response = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/developer/generate', {
    method: 'POST',
    headers: {
      'x-api-key': 'sk-demo-key-123',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      prompt: 'Создай компонент React для формы входа',
      type: 'component',
      framework: 'react'
    })
  });
  
  console.log('Response:', response.status);
  const data = await response.json();
  console.log('Generated code:', data);
}

// Пример 3: Запрос с rate limiting
export async function exampleRateLimitedRequest() {
  for (let i = 1; i <= 5; i++) {
    const response = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/ba/analyze', {
      method: 'GET',
      headers: {
        'x-api-key': 'sk-admin-key-456'
      }
    });
    
    console.log(`Request ${i}:`, response.status);
    console.log('Rate Limit Headers:', {
      'X-RateLimit-Limit': response.headers.get('X-RateLimit-Limit'),
      'X-RateLimit-Remaining': response.headers.get('X-RateLimit-Remaining'),
      'X-RateLimit-Reset': response.headers.get('X-RateLimit-Reset')
    });
    
    if (response.status === 429) {
      console.log('Rate limit exceeded!');
      break;
    }
    
    await new Promise(resolve => setTimeout(resolve, 100));
  }
}

// Пример 4: Тестирование circuit breaker
export async function exampleCircuitBreakerTest() {
  // Симулируем неработающий сервис
  const brokenServiceUrl = 'https://broken-service.supabase.co/functions/v1/broken';
  
  console.log('Testing circuit breaker...');
  
  // Первые запросы должны пройти успешно, затем circuit breaker должен сработать
  for (let i = 1; i <= 10; i++) {
    try {
      const response = await fetch(`https://api-demo.supabase.co/functions/v1/api-gateway/v1/tester/test?service=${encodeURIComponent(brokenServiceUrl)}`);
      console.log(`Request ${i}:`, response.status);
      
      if (!response.ok) {
        console.log('Circuit breaker is working!');
      }
    } catch (error) {
      console.log(`Request ${i} failed:`, error.message);
    }
    
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}

// Пример 5: Тестирование кэширования
export async function exampleCachingTest() {
  const endpoint = 'https://api-demo.supabase.co/functions/v1/api-gateway/v1/pm/projects';
  
  console.log('Testing cache...');
  
  // Первый запрос (cache miss)
  console.log('\\n=== First Request (Cache Miss) ===');
  const start1 = Date.now();
  const response1 = await fetch(endpoint, {
    headers: { 'Authorization': 'Bearer demo-token' }
  });
  const time1 = Date.now() - start1;
  
  console.log('Status:', response1.status);
  console.log('Cache Header:', response1.headers.get('X-Cache'));
  console.log('Response Time:', time1 + 'ms');
  
  // Второй запрос (cache hit)
  console.log('\\n=== Second Request (Cache Hit) ===');
  const start2 = Date.now();
  const response2 = await fetch(endpoint, {
    headers: { 'Authorization': 'Bearer demo-token' }
  });
  const time2 = Date.now() - start2;
  
  console.log('Status:', response2.status);
  console.log('Cache Header:', response2.headers.get('X-Cache'));
  console.log('Response Time:', time2 + 'ms');
  
  console.log('\\nCache effectiveness:', time1 > time2 ? 'GOOD' : 'N/A');
}

// Пример 6: Load balancing тест
export async function exampleLoadBalancingTest() {
  const endpoint = 'https://api-demo.supabase.co/functions/v1/api-gateway/v1/developer/code';
  const requests = [];
  
  console.log('Testing load balancing...');
  
  // Отправляем несколько запросов одновременно
  for (let i = 1; i <= 5; i++) {
    const request = fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': 'sk-demo-key-123'
      },
      body: JSON.stringify({ requestId: i })
    }).then(async response => ({
      requestId: i,
      status: response.status,
      server: response.headers.get('Server') || 'Unknown'
    }));
    
    requests.push(request);
  }
  
  const results = await Promise.all(requests);
  results.forEach(result => {
    console.log(`Request ${result.requestId}: ${result.status} (Server: ${result.server})`);
  });
  
  // Проверяем, что запросы обрабатывались разными серверами
  const servers = results.map(r => r.server);
  const uniqueServers = new Set(servers);
  console.log(`\\nLoad balancing effective: ${uniqueServers.size > 1 ? 'YES' : 'NO'}`);
  console.log('Unique servers:', Array.from(uniqueServers));
}

// Пример 7: Authentication тесты
export async function exampleAuthTests() {
  console.log('Testing authentication...');
  
  // Тест 1: Без аутентификации (публичный endpoint)
  console.log('\\n=== Public Endpoint Test ===');
  const publicResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/health');
  console.log('Public endpoint status:', publicResponse.status);
  
  // Тест 2: Защищенный endpoint без токена
  console.log('\\n=== Protected Endpoint Without Auth ===');
  const protectedResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/architect/data');
  console.log('Protected endpoint status:', protectedResponse.status);
  
  if (protectedResponse.status === 401) {
    const error = await protectedResponse.json();
    console.log('Expected auth error:', error.error.message);
  }
  
  // Тест 3: Защищенный endpoint с токеном
  console.log('\\n=== Protected Endpoint With Auth ===');
  const authResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/architect/data', {
    headers: {
      'Authorization': 'Bearer demo-jwt-token'
    }
  });
  console.log('Authenticated endpoint status:', authResponse.status);
}

// Пример 8: Мониторинг метрик
export async function exampleMetricsMonitoring() {
  console.log('Collecting metrics...');
  
  const metricsResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/metrics');
  
  if (metricsResponse.ok) {
    const metrics = await metricsResponse.text();
    console.log('\\nMetrics Report:');
    console.log(metrics);
  } else {
    console.log('Failed to fetch metrics:', metricsResponse.status);
  }
  
  // Получение логов
  console.log('\\nCollecting logs...');
  const logsResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/logs');
  
  if (logsResponse.ok) {
    const logs = await logsResponse.json();
    console.log('\\nRecent logs count:', logs.logs.length);
    if (logs.logs.length > 0) {
      console.log('Latest log:', logs.logs[logs.logs.length - 1]);
    }
  } else {
    console.log('Failed to fetch logs:', logsResponse.status);
  }
}

// Пример 9: Error handling тесты
export async function exampleErrorHandling() {
  console.log('Testing error handling...');
  
  // Тест 1: 404 ошибка
  console.log('\\n=== 404 Error Test ===');
  const notFoundResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/nonexistent/endpoint');
  console.log('404 status:', notFoundResponse.status);
  if (notFoundResponse.status === 404) {
    const error = await notFoundResponse.json();
    console.log('404 error message:', error.error.message);
  }
  
  // Тест 2: Validation error
  console.log('\\n=== Validation Error Test ===');
  const validationResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/developer/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': 'sk-demo-key-123'
    },
    body: JSON.stringify({
      // Неполные данные для тестирования валидации
      invalid: 'data'
    })
  });
  console.log('Validation status:', validationResponse.status);
  
  if (validationResponse.status === 400) {
    const error = await validationResponse.json();
    console.log('Validation error:', error.error.message);
  }
}

// Пример 10: Полный workflow тест
export async function exampleFullWorkflow() {
  console.log('Running full workflow test...');
  
  // 1. Health check
  console.log('\\n1. Health Check');
  const healthResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/health');
  console.log('Health status:', healthResponse.status);
  
  // 2. Аутентификация
  console.log('\\n2. Authentication');
  const authResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/architect/profile', {
    headers: {
      'Authorization': 'Bearer demo-jwt-token'
    }
  });
  console.log('Auth status:', authResponse.status);
  
  // 3. Выполнение бизнес-операции
  console.log('\\n3. Business Operation');
  const businessResponse = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/v1/ba/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': 'sk-demo-key-123'
    },
    body: JSON.stringify({
      type: 'requirements_analysis',
      project: 'demo-project'
    })
  });
  console.log('Business operation status:', businessResponse.status);
  
  // 4. Мониторинг
  console.log('\\n4. Monitoring');
  const finalMetrics = await fetch('https://api-demo.supabase.co/functions/v1/api-gateway/metrics');
  if (finalMetrics.ok) {
    const metrics = await finalMetrics.text();
    const totalRequests = metrics.match(/Total Requests: (\\d+)/)?.[1];
    console.log('Total requests processed:', totalRequests || 'Unknown');
  }
  
  console.log('\\n✅ Full workflow test completed');
}

// Экспорт всех примеров
export const examples = {
  architect: exampleArchitectRequest,
  developer: exampleDeveloperRequest,
  rateLimit: exampleRateLimitedRequest,
  circuitBreaker: exampleCircuitBreakerTest,
  caching: exampleCachingTest,
  loadBalancing: exampleLoadBalancingTest,
  authentication: exampleAuthTests,
  monitoring: exampleMetricsMonitoring,
  errorHandling: exampleErrorHandling,
  fullWorkflow: exampleFullWorkflow
};

// Запуск всех примеров
export async function runAllExamples() {
  console.log('🚀 Running all API Gateway examples...\\n');
  
  const runExample = async (name: string, func: () => Promise<void>) => {
    try {
      console.log(`\\n${'='.repeat(50)}`);
      console.log(`🔄 Running: ${name}`);
      console.log('='.repeat(50));
      
      await func();
      
      console.log(`\\n✅ ${name} completed successfully\\n`);
    } catch (error) {
      console.error(`\\n❌ ${name} failed:`, error.message);
      console.error(error.stack);
    }
  };
  
  // Запускаем примеры последовательно
  await runExample('Authentication Tests', examples.authentication);
  await runExample('Caching Test', examples.caching);
  await runExample('Load Balancing Test', examples.loadBalancing);
  await runExample('Rate Limiting Test', examples.rateLimit);
  await runExample('Error Handling Test', examples.errorHandling);
  await runExample('Monitoring Test', examples.monitoring);
  
  console.log('\\n🎉 All examples completed!');
}

// Если файл запускается напрямую
if (import.meta.main) {
  runAllExamples();
}