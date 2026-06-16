/**
 * Тестовые фикстуры - готовые тестовые данные для различных сценариев
 * Содержит структурированные наборы данных для быстрого тестирования
 */

// Пользователи
export const userFixtures = {
  // Базовый пользователь
  basic: {
    id: "user-basic-001",
    email: "basic@example.com",
    name: "Basic User",
    role: "user",
    email_verified: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Администратор
  admin: {
    id: "user-admin-001", 
    email: "admin@example.com",
    name: "Admin User",
    role: "admin",
    email_verified: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Неверифицированный пользователь
  unverified: {
    id: "user-unverified-001",
    email: "unverified@example.com", 
    name: "Unverified User",
    role: "user",
    email_verified: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Заблокированный пользователь
  blocked: {
    id: "user-blocked-001",
    email: "blocked@example.com",
    name: "Blocked User", 
    role: "user",
    email_verified: true,
    blocked: true,
    blocked_reason: "Spam reports",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Пользователь с профилем
  withProfile: {
    id: "user-profile-001",
    email: "profile@example.com",
    name: "Profile User",
    role: "user", 
    email_verified: true,
    profile: {
      first_name: "Profile",
      last_name: "User",
      bio: "Test user with profile",
      date_of_birth: "1990-05-15",
      phone: "+79001234567",
      avatar_url: "https://example.com/avatar.jpg",
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
    },
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  }
};

// Товары
export const productFixtures = {
  // Электроника
  electronics: {
    id: "product-electronics-001",
    name: "Смартфон Pro Max",
    description: "Флагманский смартфон с передовыми технологиями",
    price: 89990,
    currency: "RUB",
    category: "electronics",
    subcategory: "smartphones",
    brand: "TechBrand",
    sku: "PHONE-PROMAX-001",
    stock: 150,
    low_stock_threshold: 10,
    images: [
      "https://example.com/product1-main.jpg",
      "https://example.com/product1-side.jpg"
    ],
    specifications: {
      screen_size: "6.7 дюймов",
      processor: "A17 Pro",
      ram: "8GB",
      storage: "256GB",
      battery: "4441 mAh",
      camera: "48MP основная + 12MP ультраширокая + 12MP телефото"
    },
    tags: ["новый", "популярный", "рекомендуемый"],
    rating: 4.8,
    review_count: 1247,
    is_active: true,
    is_featured: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Одежда
  clothing: {
    id: "product-clothing-001",
    name: "Хлопковая футболка",
    description: "Качественная хлопковая футболка классического кроя",
    price: 1990,
    currency: "RUB", 
    category: "clothing",
    subcategory: "t-shirts",
    brand: "ComfortWear",
    sku: "TSHIRT-COTTON-001",
    stock: 75,
    low_stock_threshold: 5,
    images: [
      "https://example.com/tshirt-white.jpg",
      "https://example.com/tshirt-black.jpg"
    ],
    variants: [
      {
        color: "white",
        size: "S",
        sku: "TSHIRT-COTTON-WHITE-S"
      },
      {
        color: "white", 
        size: "M",
        sku: "TSHIRT-COTTON-WHITE-M"
      },
      {
        color: "black",
        size: "L", 
        sku: "TSHIRT-COTTON-BLACK-L"
      }
    ],
    tags: ["хлопок", "классический", "комфорт"],
    rating: 4.3,
    review_count: 89,
    is_active: true,
    is_featured: false,
    created_at: "2024-01-01T00:00:00Z", 
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Книга
  book: {
    id: "product-book-001",
    name: "Программирование на TypeScript",
    description: "Полное руководство по разработке приложений на TypeScript",
    price: 3990,
    currency: "RUB",
    category: "books",
    subcategory: "programming",
    author: "Иван Петров",
    publisher: "TechBooks",
    isbn: "978-5-699-12345-6",
    pages: 456,
    language: "ru",
    format: "paperback",
    stock: 25,
    low_stock_threshold: 3,
    images: [
      "https://example.com/typescript-book-cover.jpg"
    ],
    tags: ["программирование", "typescript", "разработка"],
    rating: 4.9,
    review_count: 156,
    is_active: true,
    is_featured: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Распродажа
  sale: {
    id: "product-sale-001",
    name: "Беспроводные наушники",
    description: "Наушники с активным шумоподавлением",
    original_price: 8990,
    sale_price: 5990,
    currency: "RUB",
    category: "electronics",
    subcategory: "headphones",
    brand: "AudioTech",
    sku: "HEADPHONES-WIRELESS-001",
    stock: 45,
    low_stock_threshold: 5,
    images: [
      "https://example.com/headphones-black.jpg"
    ],
    sale_start: "2024-12-01T00:00:00Z",
    sale_end: "2024-12-31T23:59:59Z",
    tags: ["скидка", "беспроводные", "шумоподавление"],
    rating: 4.6,
    review_count: 203,
    is_active: true,
    is_featured: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  }
};

// Заказы
export const orderFixtures = {
  // Базовый заказ
  basic: {
    id: "order-basic-001",
    user_id: "user-basic-001",
    status: "pending",
    items: [
      {
        product_id: "product-electronics-001",
        quantity: 1,
        price: 89990,
        total: 89990
      }
    ],
    subtotal: 89990,
    tax_amount: 1799.80, // 2% НДС
    shipping_cost: 500,
    discount_amount: 0,
    total: 92289.80,
    currency: "RUB",
    payment_status: "pending",
    shipping_status: "not_shipped",
    payment_method: "card",
    shipping_address: {
      first_name: "Иван",
      last_name: "Петров",
      street: "ул. Примерная, д. 123",
      city: "Москва",
      region: "Московская область",
      postal_code: "123456",
      country: "RU",
      phone: "+79001234567"
    },
    billing_address: {
      first_name: "Иван",
      last_name: "Петров", 
      street: "ул. Примерная, д. 123",
      city: "Москва",
      region: "Московская область", 
      postal_code: "123456",
      country: "RU",
      phone: "+79001234567"
    },
    notes: "Доставить после 18:00",
    tracking_number: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  // Оплаченный заказ
  paid: {
    id: "order-paid-001", 
    user_id: "user-basic-001",
    status: "processing",
    items: [
      {
        product_id: "product-clothing-001",
        quantity: 2,
        price: 1990,
        total: 3980
      }
    ],
    subtotal: 3980,
    tax_amount: 79.60,
    shipping_cost: 300,
    discount_amount: 200,
    total: 4159.60,
    currency: "RUB",
    payment_status: "paid",
    payment_method: "card",
    payment_details: {
      payment_intent_id: "pi_test_123456",
      transaction_id: "txn_789012",
      paid_at: "2024-01-01T12:00:00Z"
    },
    shipping_status: "processing",
    tracking_number: "TRACK123456789",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T12:00:00Z"
  },

  // Доставленный заказ
  delivered: {
    id: "order-delivered-001",
    user_id: "user-with-profile-001",
    status: "delivered",
    items: [
      {
        product_id: "product-book-001",
        quantity: 1,
        price: 3990,
        total: 3990
      }
    ],
    subtotal: 3990,
    tax_amount: 79.80,
    shipping_cost: 200,
    discount_amount: 0,
    total: 4269.80,
    currency: "RUB",
    payment_status: "paid",
    payment_method: "card",
    payment_details: {
      payment_intent_id: "pi_test_789012",
      transaction_id: "txn_345678",
      paid_at: "2024-01-01T10:00:00Z"
    },
    shipping_status: "delivered",
    tracking_number: "TRACK789012345",
    delivered_at: "2024-01-03T15:30:00Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-03T15:30:00Z"
  }
};

// Корзина
export const cartFixtures = {
  basic: {
    id: "cart-basic-001",
    user_id: "user-basic-001",
    items: [
      {
        id: "cart-item-001",
        product_id: "product-electronics-001",
        quantity: 1,
        price: 89990,
        total: 89990,
        added_at: "2024-01-01T00:00:00Z"
      },
      {
        id: "cart-item-002", 
        product_id: "product-clothing-001",
        quantity: 2,
        price: 1990,
        total: 3980,
        added_at: "2024-01-01T00:00:00Z"
      }
    ],
    subtotal: 93970,
    item_count: 3,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  empty: {
    id: "cart-empty-001",
    user_id: "user-basic-001", 
    items: [],
    subtotal: 0,
    item_count: 0,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  }
};

// Платежи
export const paymentFixtures = {
  basic: {
    id: "payment-basic-001",
    order_id: "order-basic-001",
    user_id: "user-basic-001",
    amount: 92289.80,
    currency: "RUB",
    status: "pending",
    payment_method: {
      type: "card",
      brand: "visa",
      last4: "4242",
      exp_month: 12,
      exp_year: 2025
    },
    payment_intent_id: "pi_test_123456",
    transaction_id: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  successful: {
    id: "payment-successful-001",
    order_id: "order-paid-001",
    user_id: "user-basic-001",
    amount: 4159.60,
    currency: "RUB",
    status: "succeeded",
    payment_method: {
      type: "card", 
      brand: "mastercard",
      last4: "5555",
      exp_month: 8,
      exp_year: 2026
    },
    payment_intent_id: "pi_test_789012",
    transaction_id: "txn_789012",
    paid_at: "2024-01-01T12:00:00Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T12:00:00Z"
  },

  failed: {
    id: "payment-failed-001",
    order_id: "order-basic-002",
    user_id: "user-unverified-001", 
    amount: 5000,
    currency: "RUB",
    status: "failed",
    payment_method: {
      type: "card",
      brand: "visa",
      last4: "1234",
      exp_month: 3,
      exp_year: 2024
    },
    payment_intent_id: "pi_test_failed",
    transaction_id: null,
    failure_reason: "insufficient_funds",
    failed_at: "2024-01-01T15:00:00Z",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T15:00:00Z"
  }
};

// Уведомления
export const notificationFixtures = {
  orderConfirmation: {
    id: "notification-order-001",
    user_id: "user-basic-001",
    type: "order_confirmation",
    title: "Заказ подтвержден",
    message: "Ваш заказ #order-basic-001 на сумму 922.89 ₽ успешно создан",
    data: {
      order_id: "order-basic-001",
      total: 92289.80,
      currency: "RUB"
    },
    channels: ["email", "push"],
    status: "sent",
    sent_at: "2024-01-01T00:00:00Z",
    read_at: null,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z"
  },

  paymentSuccess: {
    id: "notification-payment-001",
    user_id: "user-basic-001",
    type: "payment_success",
    title: "Платеж успешно обработан",
    message: "Платеж по заказу #order-paid-001 на сумму 41.60 ₽ успешно обработан",
    data: {
      order_id: "order-paid-001",
      amount: 4159.60,
      currency: "RUB",
      transaction_id: "txn_789012"
    },
    channels: ["email"],
    status: "sent",
    sent_at: "2024-01-01T12:00:00Z",
    read_at: "2024-01-01T13:00:00Z",
    created_at: "2024-01-01T12:00:00Z",
    updated_at: "2024-01-01T13:00:00Z"
  },

  shippingUpdate: {
    id: "notification-shipping-001",
    user_id: "user-with-profile-001",
    type: "shipping_update",
    title: "Заказ отправлен",
    message: "Ваш заказ #order-delivered-001 отправлен. Номер отслеживания: TRACK789012345",
    data: {
      order_id: "order-delivered-001",
      tracking_number: "TRACK789012345",
      carrier: "Почта России"
    },
    channels: ["email", "sms"],
    status: "sent",
    sent_at: "2024-01-02T10:00:00Z",
    read_at: null,
    created_at: "2024-01-02T10:00:00Z",
    updated_at: "2024-01-02T10:00:00Z"
  }
};

// Отзывы
export const reviewFixtures = {
  positive: {
    id: "review-positive-001",
    user_id: "user-basic-001",
    product_id: "product-electronics-001",
    order_id: "order-basic-001",
    rating: 5,
    title: "Отличный смартфон!",
    comment: "Очень доволен покупкой. Камера снимает превосходно, батареи хватает на весь день. Рекомендую!",
    images: [
      "https://example.com/review1-photo1.jpg"
    ],
    is_verified_purchase: true,
    helpful_votes: 12,
    not_helpful_votes: 1,
    created_at: "2024-01-05T00:00:00Z",
    updated_at: "2024-01-05T00:00:00Z"
  },

  negative: {
    id: "review-negative-001",
    user_id: "user-unverified-001",
    product_id: "product-clothing-001",
    rating: 2,
    title: "Размер не соответствует",
    comment: "Заказал размер M, пришел размер S. Качество ткани нормальное, но размер не подошел.",
    is_verified_purchase: false,
    helpful_votes: 3,
    not_helpful_votes: 0,
    created_at: "2024-01-03T00:00:00Z",
    updated_at: "2024-01-03T00:00:00Z"
  }
};

// Аналитика
export const analyticsFixtures = {
  userActivity: {
    user_id: "user-basic-001",
    events: [
      {
        event: "page_view",
        page: "/products",
        timestamp: "2024-01-01T10:00:00Z",
        properties: {
          category: "electronics"
        }
      },
      {
        event: "product_view",
        product_id: "product-electronics-001", 
        timestamp: "2024-01-01T10:05:00Z",
        properties: {
          category: "electronics",
          price: 89990
        }
      },
      {
        event: "add_to_cart",
        product_id: "product-electronics-001",
        timestamp: "2024-01-01T10:10:00Z",
        properties: {
          quantity: 1,
          price: 89990
        }
      },
      {
        event: "checkout_started",
        timestamp: "2024-01-01T11:00:00Z",
        properties: {
          cart_value: 93970
        }
      }
    ]
  },

  salesReport: {
    period: {
      start: "2024-01-01T00:00:00Z",
      end: "2024-01-31T23:59:59Z"
    },
    metrics: {
      total_orders: 156,
      total_revenue: 2456789.50,
      average_order_value: 15748.65,
      unique_customers: 89,
      conversion_rate: 3.2,
      top_products: [
        {
          product_id: "product-electronics-001",
          name: "Смартфон Pro Max",
          revenue: 899900,
          quantity_sold: 10
        }
      ]
    }
  }
};

// API ответы
export const apiResponseFixtures = {
  success: {
    success: true,
    data: {},
    message: "Операция выполнена успешно"
  },

  error: {
    success: false,
    error: {
      code: "VALIDATION_ERROR",
      message: "Некорректные данные",
      details: {
        field: "email",
        message: "Неверный формат email"
      }
    }
  },

  paginated: {
    success: true,
    data: {
      items: [],
      pagination: {
        page: 1,
        limit: 20,
        total: 100,
        total_pages: 5,
        has_next: true,
        has_prev: false
      }
    }
  }
};

// Переменные окружения для тестов
export const envFixtures = {
  test: {
    SUPABASE_URL: "https://test.supabase.co",
    SUPABASE_ANON_KEY: "test-anon-key",
    SUPABASE_SERVICE_ROLE_KEY: "test-service-key",
    STRIPE_SECRET_KEY: "sk_test_123456",
    STRIPE_WEBHOOK_SECRET: "whsec_test_123456",
    SENDGRID_API_KEY: "SG.test123456",
    OPENAI_API_KEY: "sk-test-openai-key",
    ENVIRONMENT: "test",
    LOG_LEVEL: "info"
  },

  development: {
    SUPABASE_URL: "https://dev.supabase.co",
    SUPABASE_ANON_KEY: "dev-anon-key",
    SUPABASE_SERVICE_ROLE_KEY: "dev-service-key",
    STRIPE_SECRET_KEY: "sk_test_dev",
    SENDGRID_API_KEY: "SG.dev123",
    OPENAI_API_KEY: "sk-dev-openai-key",
    ENVIRONMENT: "development",
    LOG_LEVEL: "debug"
  }
};

// Утилиты для работы с фикстурами
export const fixtureUtils = {
  /**
   * Получение фикстуры по имени
   */
  getFixture<T>(category: keyof typeof userFixtures, name: keyof any): T {
    return (category as any)[name];
  },

  /**
   * Создание кастомной фикстуры на основе базовой
   */
  createCustomFixture<T>(baseFixture: T, overrides: Partial<T>): T {
    return { ...baseFixture, ...overrides };
  },

  /**
   * Получение всех фикстур категории
   */
  getAllFixtures(category: string) {
    return (globalThis as any)[`${category}Fixtures`] || {};
  },

  /**
   * Генерация уникального ID для теста
   */
  generateTestId(prefix: string = "test"): string {
    return `${prefix}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  },

  /**
   * Создание временной метки для тестов
   */
  createTestTimestamp(offset: number = 0): string {
    const date = new Date();
    date.setHours(date.getHours() + offset);
    return date.toISOString();
  }
};