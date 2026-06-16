/**
 * Пример интеграционного теста для проверки взаимодействия между компонентами
 * Тестирует интеграцию Edge Functions с базой данных и внешними сервисами
 */

import { assertEquals, assertExists } from "https://deno.land/std@0.208.0/testing/asserts.ts";
import { createMockSupabaseClient, createTestUser, createTestProduct } from "../mocks/supabase.ts";
import { createMockRequest, executeFunction, setEnv, createTempDir } from "../utils/test-helpers.ts";
import { installMockFetch, setupApiHandlers, expectRequest } from "../mocks/requests.ts";

/**
 * Интеграционные тесты для пользовательского сервиса
 */
Deno.test("User Service Integration Tests", async (t) => {
  let mockSupabase: any;
  let tempDir: string;

  await t.step.setup(async () => {
    // Подготовка окружения
    tempDir = await createTempDir();
    mockSupabase = createMockSupabaseClient();
    installMockFetch();
    setupApiHandlers();
    
    // Установка тестовых переменных окружения
    setEnv({
      SUPABASE_URL: "https://test.supabase.co",
      SUPABASE_ANON_KEY: "test-anon-key",
      SUPABASE_SERVICE_ROLE_KEY: "test-service-key",
      ENVIRONMENT: "test"
    });
  });

  await t.step.teardown(async () => {
    // Очистка после тестирования
    await Deno.remove(tempDir, { recursive: true });
  });

  await t.step("полный пользовательский workflow", async () => {
    // Сценарий: регистрация -> аутентификация -> создание профиля -> обновление данных

    // 1. Регистрация пользователя
    const registrationData = {
      email: "integration@example.com",
      password: "SecurePass123!",
      name: "Integration Test User"
    };

    const registrationRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/register",
      "POST",
      { "Content-Type": "application/json" },
      registrationData
    );

    const registrationResponse = await executeFunction(
      "../../supabase/functions/user-handler/index.ts",
      "userHandler",
      registrationRequest
    );

    assertEquals(registrationResponse.status, 201);
    const user = await registrationResponse.json();
    assertEquals(user.email, registrationData.email);
    assertExists(user.id);

    // 2. Аутентификация
    const authData = {
      email: registrationData.email,
      password: registrationData.password
    };

    const authRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/auth",
      "POST",
      { "Content-Type": "application/json" },
      authData
    );

    const authResponse = await executeFunction(
      "../../supabase/functions/auth-handler/index.ts",
      "authHandler",
      authRequest
    );

    assertEquals(authResponse.status, 200);
    const auth = await authResponse.json();
    assertExists(auth.session);
    assertExists(auth.session.access_token);

    // 3. Создание профиля пользователя
    const profileData = {
      user_id: user.id,
      bio: "Test bio for integration user",
      preferences: {
        theme: "dark",
        language: "ru",
        notifications: true
      }
    };

    const profileRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/profile",
      "POST",
      {
        "Authorization": `Bearer ${auth.session.access_token}`,
        "Content-Type": "application/json"
      },
      profileData
    );

    const profileResponse = await executeFunction(
      "../../supabase/functions/profile-handler/index.ts",
      "profileHandler",
      profileRequest
    );

    assertEquals(profileResponse.status, 201);
    const profile = await profileResponse.json();
    assertEquals(profile.user_id, user.id);
    assertEquals(profile.bio, profileData.bio);

    // 4. Обновление профиля
    const updateData = {
      bio: "Updated bio for integration user",
      preferences: {
        theme: "light",
        language: "en",
        notifications: false
      }
    };

    const updateRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/profile",
      "PUT",
      {
        "Authorization": `Bearer ${auth.session.access_token}`,
        "Content-Type": "application/json"
      },
      updateData
    );

    const updateResponse = await executeFunction(
      "../../supabase/functions/profile-handler/index.ts",
      "profileHandler",
      updateRequest
    );

    assertEquals(updateResponse.status, 200);
    const updatedProfile = await updateResponse.json();
    assertEquals(updatedProfile.bio, updateData.bio);
    assertEquals(updatedProfile.preferences.theme, "light");
  });
});

/**
 * Интеграционные тесты для сервиса продуктов
 */
Deno.test("Product Service Integration Tests", async (t) => {
  let mockSupabase: any;

  await t.step.setup(async () => {
    mockSupabase = createMockSupabaseClient();
    installMockFetch();
  });

  await t.step("workflow управления продуктами", async () => {
    // Сценарий: создание -> получение -> обновление -> удаление

    // 1. Создание продукта
    const productData = createTestProduct({
      name: "Integration Test Product",
      price: 299.99,
      category: "electronics",
      stock: 100
    });

    const createRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/products",
      "POST",
      { "Authorization": "Bearer admin-token", "Content-Type": "application/json" },
      productData
    );

    const createResponse = await executeFunction(
      "../../supabase/functions/product-handler/index.ts",
      "productHandler",
      createRequest
    );

    assertEquals(createResponse.status, 201);
    const product = await createResponse.json();
    assertEquals(product.name, productData.name);
    assertEquals(product.price, productData.price);
    assertExists(product.id);

    // 2. Получение продукта
    const getRequest = createMockRequest(
      `https://test.supabase.co/functions/v1/products/${product.id}`,
      "GET",
      { "Authorization": "Bearer user-token" }
    );

    const getResponse = await executeFunction(
      "../../supabase/functions/product-handler/index.ts",
      "productHandler",
      getRequest
    );

    assertEquals(getResponse.status, 200);
    const retrievedProduct = await getResponse.json();
    assertEquals(retrievedProduct.id, product.id);

    // 3. Обновление продукта
    const updateData = {
      name: "Updated Integration Test Product",
      price: 249.99,
      stock: 75
    };

    const updateRequest = createMockRequest(
      `https://test.supabase.co/functions/v1/products/${product.id}`,
      "PUT",
      { "Authorization": "Bearer admin-token", "Content-Type": "application/json" },
      updateData
    );

    const updateResponse = await executeFunction(
      "../../supabase/functions/product-handler/index.ts",
      "productHandler",
      updateRequest
    );

    assertEquals(updateResponse.status, 200);
    const updatedProduct = await updateResponse.json();
    assertEquals(updatedProduct.name, updateData.name);
    assertEquals(updatedProduct.price, updateData.price);

    // 4. Проверка HTTP запросов к внешним сервисам
    expectRequest("https://api.inventory-service.com/update-stock", "POST");
  });

  await t.step("интеграция с сервисом платежей", async () => {
    // Тестирование интеграции с внешним платежным сервисом

    const paymentData = {
      product_id: "test-product-1",
      amount: 199.99,
      currency: "RUB",
      payment_method: "card",
      card_token: "tok_test123456"
    };

    const paymentRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/payment",
      "POST",
      { 
        "Authorization": "Bearer user-token",
        "Content-Type": "application/json" 
      },
      paymentData
    );

    const paymentResponse = await executeFunction(
      "../../supabase/functions/payment-handler/index.ts",
      "paymentHandler",
      paymentRequest
    );

    assertEquals(paymentResponse.status, 200);
    const payment = await paymentResponse.json();
    assertEquals(payment.status, "succeeded");
    assertExists(payment.transaction_id);
  });
});

/**
 * Интеграционные тесты для системы уведомлений
 */
Deno.test("Notification System Integration Tests", async (t) => {
  await t.step.setup(async () => {
    installMockFetch();
  });

  await t.step("отправка уведомлений через различные каналы", async () => {
    // Тестирование отправки уведомлений через email, SMS и push

    const notificationData = {
      type: "order_confirmation",
      recipient: {
        email: "user@example.com",
        phone: "+79001234567"
      },
      template: "order_confirmation",
      data: {
        order_id: "order-12345",
        total: 599.99,
        items: ["Product 1", "Product 2"]
      }
    };

    // Email уведомление
    const emailRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/notify",
      "POST",
      { 
        "Authorization": "Bearer system-token",
        "Content-Type": "application/json" 
      },
      { ...notificationData, channel: "email" }
    );

    const emailResponse = await executeFunction(
      "../../supabase/functions/notification-handler/index.ts",
      "notificationHandler",
      emailRequest
    );

    assertEquals(emailResponse.status, 200);
    const emailResult = await emailResponse.json();
    assertEquals(emailResult.channel, "email");
    assertEquals(emailResult.status, "sent");

    // SMS уведомление
    const smsRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/notify",
      "POST",
      { 
        "Authorization": "Bearer system-token",
        "Content-Type": "application/json" 
      },
      { ...notificationData, channel: "sms" }
    );

    const smsResponse = await executeFunction(
      "../../supabase/functions/notification-handler/index.ts",
      "notificationHandler",
      smsRequest
    );

    assertEquals(smsResponse.status, 200);
    const smsResult = await smsResponse.json();
    assertEquals(smsResult.channel, "sms");
    assertEquals(smsResult.status, "sent");
  });
});

/**
 * Интеграционные тесты для системы аналитики
 */
Deno.test("Analytics System Integration Tests", async (t) => {
  await t.step("трекинг пользовательских событий", async () => {
    // Тестирование системы аналитики и трекинга событий

    const analyticsEvents = [
      {
        event: "user_registration",
        user_id: "user-12345",
        properties: {
          source: "website",
          campaign: "summer_sale"
        }
      },
      {
        event: "purchase",
        user_id: "user-12345",
        properties: {
          value: 299.99,
          currency: "RUB",
          products: ["product-1", "product-2"]
        }
      }
    ];

    const analyticsRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/analytics",
      "POST",
      { 
        "Authorization": "Bearer system-token",
        "Content-Type": "application/json" 
      },
      { events: analyticsEvents }
    );

    const analyticsResponse = await executeFunction(
      "../../supabase/functions/analytics-handler/index.ts",
      "analyticsHandler",
      analyticsRequest
    );

    assertEquals(analyticsResponse.status, 200);
    const result = await analyticsResponse.json();
    assertEquals(result.processed, analyticsEvents.length);
    assertEquals(result.status, "success");
  });

  await t.step("генерация отчетов", async () => {
    // Тестирование генерации аналитических отчетов

    const reportRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/reports",
      "GET",
      { 
        "Authorization": "Bearer admin-token",
        "Content-Type": "application/json" 
      }
    );

    const reportResponse = await executeFunction(
      "../../supabase/functions/report-handler/index.ts",
      "reportHandler",
      reportRequest
    );

    assertEquals(reportResponse.status, 200);
    const report = await reportResponse.json();
    assertExists(report.summary);
    assertExists(report.metrics);
    assertExists(report.period);
  });
});

/**
 * Тестирование интеграции с внешними API
 */
Deno.test("External API Integration Tests", async (t) => {
  await t.step("интеграция с внешними сервисами", async () => {
    // Тестирование интеграции с внешними сервисами
    // (OpenAI, Stripe, SendGrid и т.д.)

    const externalApiRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/external-integration",
      "POST",
      { 
        "Authorization": "Bearer system-token",
        "Content-Type": "application/json" 
      },
      {
        service: "openai",
        action: "generate_text",
        prompt: "Создай описание продукта"
      }
    );

    const externalApiResponse = await executeFunction(
      "../../supabase/functions/external-handler/index.ts",
      "externalHandler",
      externalApiRequest
    );

    assertEquals(externalApiResponse.status, 200);
    const result = await externalApiResponse.json();
    assertEquals(result.service, "openai");
    assertExists(result.response);
  });
});

/**
 * Нагрузочные тесты
 */
Deno.test("Load Testing Integration Tests", async (t) => {
  await t.step("проверка производительности при нагрузке", async () => {
    // Создание множественных запросов для проверки производительности

    const requests = Array.from({ length: 50 }, (_, i) => 
      createMockRequest(
        `https://test.supabase.co/functions/v1/products?page=${i}`,
        "GET",
        { "Authorization": "Bearer user-token" }
      )
    );

    const startTime = performance.now();
    const responses = await Promise.all(
      requests.map(request => 
        executeFunction(
          "../../supabase/functions/product-handler/index.ts",
          "productHandler",
          request
        )
      )
    );
    const endTime = performance.now();

    // Проверка результатов
    const successfulResponses = responses.filter(r => r.status === 200);
    assertEquals(successfulResponses.length, 50);

    const totalTime = endTime - startTime;
    const averageTime = totalTime / requests.length;
    
    // Среднее время ответа должно быть менее 100ms
    assertEquals(averageTime < 100, true, 
      `Average response time was ${averageTime}ms, expected < 100ms`);
  });
});