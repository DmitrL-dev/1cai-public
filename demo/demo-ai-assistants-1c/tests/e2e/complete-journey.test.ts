/**
 * End-to-End тесты для полного пользовательского сценария
 * Тестируют весь процесс от начала до конца
 */

import { assertEquals, assertExists } from "https://deno.land/std@0.208.0/testing/asserts.ts";
import { createMockSupabaseClient } from "../mocks/supabase.ts";
import { createMockRequest, executeFunction, setEnv } from "../utils/test-helpers.ts";
import { installMockFetch, setupApiHandlers, expectRequest } from "../mocks/requests.ts";

/**
 * E2E тест: Полный пользовательский journey
 * От регистрации до оформления заказа
 */
Deno.test("Complete User Journey E2E", async (t) => {
  let userId: string;
  let sessionToken: string;
  let productId: string;

  await t.step.setup(async () => {
    // Подготовка полного окружения
    installMockFetch();
    setupApiHandlers();
    
    setEnv({
      SUPABASE_URL: "https://test.supabase.co",
      SUPABASE_ANON_KEY: "test-anon-key",
      STRIPE_SECRET_KEY: "sk_test_123",
      SENDGRID_API_KEY: "SG.test123",
      ENVIRONMENT: "test"
    });
  });

  await t.step("1. Регистрация нового пользователя", async () => {
    const registrationData = {
      email: "e2e-test@example.com",
      password: "SecurePassword123!",
      name: "E2E Test User",
      phone: "+79001234567"
    };

    const registrationRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/register",
      "POST",
      { "Content-Type": "application/json" },
      registrationData
    );

    const registrationResponse = await executeFunction(
      "../../supabase/functions/auth/register.ts",
      "serve",
      registrationRequest
    );

    assertEquals(registrationResponse.status, 201);
    const user = await registrationResponse.json();
    
    userId = user.id;
    assertEquals(user.email, registrationData.email);
    assertEquals(user.email_verified, false);
    assertExists(user.created_at);
    
    console.log("✅ Пользователь зарегистрирован:", userId);
  });

  await t.step("2. Верификация email", async () => {
    const verificationRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/verify-email",
      "POST",
      { "Content-Type": "application/json" },
      { 
        user_id: userId,
        token: "verification-token-123"
      }
    );

    const verificationResponse = await executeFunction(
      "../../supabase/functions/auth/verify-email.ts",
      "serve",
      verificationRequest
    );

    assertEquals(verificationResponse.status, 200);
    const verificationResult = await verificationResponse.json();
    assertEquals(verificationResult.status, "verified");
    
    console.log("✅ Email верифицирован");
  });

  await t.step("3. Аутентификация пользователя", async () => {
    const authRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/login",
      "POST",
      { "Content-Type": "application/json" },
      {
        email: "e2e-test@example.com",
        password: "SecurePassword123!"
      }
    );

    const authResponse = await executeFunction(
      "../../supabase/functions/auth/login.ts",
      "serve",
      authRequest
    );

    assertEquals(authResponse.status, 200);
    const auth = await authResponse.json();
    
    sessionToken = auth.session.access_token;
    assertExists(sessionToken);
    assertEquals(auth.user.email_verified, true);
    
    console.log("✅ Пользователь аутентифицирован");
  });

  await t.step("4. Создание профиля пользователя", async () => {
    const profileData = {
      user_id: userId,
      first_name: "E2E",
      last_name: "Test",
      bio: "E2E test user profile",
      date_of_birth: "1990-01-01",
      preferences: {
        theme: "light",
        language: "ru",
        currency: "RUB",
        notifications: {
          email: true,
          sms: false,
          push: true
        }
      }
    };

    const profileRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/profile",
      "POST",
      {
        "Authorization": `Bearer ${sessionToken}`,
        "Content-Type": "application/json"
      },
      profileData
    );

    const profileResponse = await executeFunction(
      "../../supabase/functions/user/profile.ts",
      "serve",
      profileRequest
    );

    assertEquals(profileResponse.status, 201);
    const profile = await profileResponse.json();
    
    assertEquals(profile.user_id, userId);
    assertEquals(profile.first_name, profileData.first_name);
    assertEquals(profile.preferences.theme, "light");
    
    console.log("✅ Профиль создан");
  });

  await t.step("5. Просмотр каталога товаров", async () => {
    const catalogRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/products",
      "GET",
      { "Authorization": `Bearer ${sessionToken}` }
    );

    const catalogResponse = await executeFunction(
      "../../supabase/functions/products/catalog.ts",
      "serve",
      catalogRequest
    );

    assertEquals(catalogResponse.status, 200);
    const catalog = await catalogResponse.json();
    
    assertExists(catalog.products);
    assertEquals(Array.isArray(catalog.products), true);
    assertExists(catalog.pagination);
    
    // Сохраняем ID первого товара для следующих шагов
    if (catalog.products.length > 0) {
      productId = catalog.products[0].id;
    }
    
    console.log(`✅ Каталог загружен, найдено товаров: ${catalog.products.length}`);
  });

  await t.step("6. Добавление товара в корзину", async () => {
    const cartData = {
      user_id: userId,
      product_id: productId,
      quantity: 2,
      variant: "default"
    };

    const cartRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/cart",
      "POST",
      {
        "Authorization": `Bearer ${sessionToken}`,
        "Content-Type": "application/json"
      },
      cartData
    );

    const cartResponse = await executeFunction(
      "../../supabase/functions/cart/add.ts",
      "serve",
      cartRequest
    );

    assertEquals(cartResponse.status, 201);
    const cartItem = await cartResponse.json();
    
    assertEquals(cartItem.user_id, userId);
    assertEquals(cartItem.product_id, productId);
    assertEquals(cartItem.quantity, 2);
    assertExists(cartItem.added_at);
    
    console.log("✅ Товар добавлен в корзину");
  });

  await t.step("7. Просмотр корзины", async () => {
    const cartViewRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/cart",
      "GET",
      { "Authorization": `Bearer ${sessionToken}` }
    );

    const cartViewResponse = await executeFunction(
      "../../supabase/functions/cart/view.ts",
      "serve",
      cartViewRequest
    );

    assertEquals(cartViewResponse.status, 200);
    const cart = await cartViewResponse.json();
    
    assertExists(cart.items);
    assertEquals(cart.items.length, 1);
    assertEquals(cart.items[0].product_id, productId);
    assertEquals(cart.items[0].quantity, 2);
    assertExists(cart.total);
    
    console.log("✅ Корзина просмотрена");
  });

  await t.step("8. Оформление заказа", async () => {
    const orderData = {
      user_id: userId,
      items: [
        {
          product_id: productId,
          quantity: 2,
          price: 299.99
        }
      ],
      shipping_address: {
        street: "Test Street 123",
        city: "Test City",
        country: "Russia",
        postal_code: "123456"
      },
      payment_method: "card",
      notes: "E2E test order"
    };

    const orderRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/orders",
      "POST",
      {
        "Authorization": `Bearer ${sessionToken}`,
        "Content-Type": "application/json"
      },
      orderData
    );

    const orderResponse = await executeFunction(
      "../../supabase/functions/orders/create.ts",
      "serve",
      orderRequest
    );

    assertEquals(orderResponse.status, 201);
    const order = await orderResponse.json();
    
    assertEquals(order.user_id, userId);
    assertEquals(order.status, "pending");
    assertEquals(order.items.length, 1);
    assertExists(order.total);
    assertExists(order.tracking_number);
    
    console.log("✅ Заказ оформлен:", order.id);
  });

  await t.step("9. Обработка платежа", async () => {
    const paymentData = {
      order_id: "test-order-123",
      amount: 599.98,
      currency: "RUB",
      payment_method: {
        type: "card",
        token: "tok_test_123456"
      },
      billing_address: {
        name: "E2E Test User",
        line1: "Test Street 123",
        city: "Test City",
        country: "Russia",
        postal_code: "123456"
      }
    };

    const paymentRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/payments/process",
      "POST",
      {
        "Authorization": `Bearer ${sessionToken}`,
        "Content-Type": "application/json"
      },
      paymentData
    );

    const paymentResponse = await executeFunction(
      "../../supabase/functions/payments/stripe.ts",
      "serve",
      paymentRequest
    );

    assertEquals(paymentResponse.status, 200);
    const payment = await paymentResponse.json();
    
    assertEquals(payment.status, "succeeded");
    assertExists(payment.transaction_id);
    assertEquals(payment.amount, paymentData.amount);
    
    console.log("✅ Платеж обработан");
  });

  await t.step("10. Отправка подтверждения", async () => {
    const notificationRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/notifications/send",
      "POST",
      {
        "Authorization": `Bearer ${sessionToken}`,
        "Content-Type": "application/json"
      },
      {
        type: "order_confirmation",
        recipient: {
          email: "e2e-test@example.com",
          phone: "+79001234567"
        },
        data: {
          order_id: "test-order-123",
          total: 599.98,
          tracking_number: "TRACK123456"
        }
      }
    );

    const notificationResponse = await executeFunction(
      "../../supabase/functions/notifications/send.ts",
      "serve",
      notificationRequest
    );

    assertEquals(notificationResponse.status, 200);
    const notification = await notificationResponse.json();
    
    assertEquals(notification.status, "sent");
    assertExists(notification.message_id);
    
    console.log("✅ Уведомление отправлено");
  });

  await t.step("11. Получение статуса заказа", async () => {
    const statusRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/orders/test-order-123/status",
      "GET",
      { "Authorization": `Bearer ${sessionToken}` }
    );

    const statusResponse = await executeFunction(
      "../../supabase/functions/orders/status.ts",
      "serve",
      statusRequest
    );

    assertEquals(statusResponse.status, 200);
    const status = await statusResponse.json();
    
    assertEquals(status.order_id, "test-order-123");
    assertExists(status.status);
    assertEquals(status.status, "processing");
    assertExists(status.timeline);
    
    console.log("✅ Статус заказа получен");
  });

  await t.step("12. Генерация отчета для аналитики", async () => {
    const reportRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/analytics/report",
      "POST",
      {
        "Authorization": `Bearer ${sessionToken}`,
        "Content-Type": "application/json"
      },
      {
        type: "purchase_summary",
        user_id: userId,
        period: "last_30_days"
      }
    );

    const reportResponse = await executeFunction(
      "../../supabase/functions/analytics/report.ts",
      "serve",
      reportRequest
    );

    assertEquals(reportResponse.status, 200);
    const report = await reportResponse.json();
    
    assertEquals(report.type, "purchase_summary");
    assertEquals(report.user_id, userId);
    assertExists(report.data);
    assertExists(report.generated_at);
    
    console.log("✅ Аналитический отчет сгенерирован");
  });

  await t.step("финальная проверка всех интеграций", async () => {
    // Проверяем, что все необходимые HTTP запросы были сделаны
    expectRequest("https://api.openai.com/v1/chat/completions", "POST");
    expectRequest("https://api.stripe.com/v1/payment_intents", "POST");
    expectRequest("https://api.sendgrid.com/v3/mail/send", "POST");
    
    console.log("🎉 E2E тест успешно завершен! Все интеграции работают корректно.");
  });
});

/**
 * E2E тест: Процесс возврата товара
 */
Deno.test("Return Process E2E", async (t) => {
  let orderId: string;

  await t.step.setup(async () => {
    installMockFetch();
    setupApiHandlers();
  });

  await t.step("1. Создание заявки на возврат", async () => {
    const returnRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/returns",
      "POST",
      { 
        "Authorization": "Bearer user-token",
        "Content-Type": "application/json" 
      },
      {
        order_id: "test-order-123",
        items: [
          {
            product_id: "product-1",
            quantity: 1,
            reason: "damaged"
          }
        ],
        reason: "Товар пришел поврежденным",
        images: ["damage-photo-1.jpg"]
      }
    );

    const returnResponse = await executeFunction(
      "../../supabase/functions/returns/create.ts",
      "serve",
      returnRequest
    );

    assertEquals(returnResponse.status, 201);
    const returnData = await returnResponse.json();
    
    orderId = returnData.id;
    assertEquals(returnData.status, "pending_review");
    assertEquals(returnData.items.length, 1);
    
    console.log("✅ Заявка на возврат создана:", orderId);
  });

  await t.step("2. Обработка возврата", async () => {
    const processRequest = createMockRequest(
      `https://test.supabase.co/functions/v1/returns/${orderId}/process`,
      "POST",
      { 
        "Authorization": "Bearer admin-token",
        "Content-Type": "application/json" 
      },
      {
        action: "approve",
        refund_amount: 299.99,
        notes: "Возврат одобрен"
      }
    );

    const processResponse = await executeFunction(
      "../../supabase/functions/returns/process.ts",
      "serve",
      processRequest
    );

    assertEquals(processResponse.status, 200);
    const result = await processResponse.json();
    
    assertEquals(result.status, "approved");
    assertEquals(result.refund_amount, 299.99);
    assertExists(result.refund_id);
    
    console.log("✅ Возврат обработан");
  });

  await t.step("3. Возврат средств", async () => {
    const refundRequest = createMockRequest(
      `https://test.supabase.co/functions/v1/returns/${orderId}/refund`,
      "POST",
      { 
        "Authorization": "Bearer system-token",
        "Content-Type": "application/json" 
      },
      {
        payment_intent_id: "pi_test_123",
        amount: 29999, // в копейках
        reason: "requested_by_customer"
      }
    );

    const refundResponse = await executeFunction(
      "../../supabase/functions/refunds/process.ts",
      "serve",
      refundRequest
    );

    assertEquals(refundResponse.status, 200);
    const refund = await refundResponse.json();
    
    assertEquals(refund.status, "succeeded");
    assertExists(refund.id);
    
    console.log("✅ Средства возвращены");
  });
});

/**
 * E2E тест: Система уведомлений
 */
Deno.test("Notification System E2E", async (t) => {
  await t.step("комплексная система уведомлений", async () => {
    // Тестирование всей системы уведомлений в действии

    const events = [
      {
        event: "user_registered",
        user_id: "user-123",
        data: { email: "user@example.com" }
      },
      {
        event: "order_placed",
        user_id: "user-123", 
        data: { order_id: "order-123", total: 299.99 }
      },
      {
        event: "payment_completed",
        order_id: "order-123",
        data: { amount: 299.99, transaction_id: "txn_123" }
      },
      {
        event: "order_shipped",
        order_id: "order-123",
        data: { tracking_number: "TRACK123" }
      }
    ];

    const notificationRequest = createMockRequest(
      "https://test.supabase.co/functions/v1/notifications/process-events",
      "POST",
      { 
        "Authorization": "Bearer system-token",
        "Content-Type": "application/json" 
      },
      { events }
    );

    const notificationResponse = await executeFunction(
      "../../supabase/functions/notifications/events.ts",
      "serve",
      notificationRequest
    );

    assertEquals(notificationResponse.status, 200);
    const result = await notificationResponse.json();
    
    assertEquals(result.processed, events.length);
    assertExists(result.results);
    assertEquals(result.results.every((r: any) => r.status === "sent"), true);
    
    console.log("✅ Система уведомлений работает корректно");
  });
});