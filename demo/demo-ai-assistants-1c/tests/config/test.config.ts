/**
 * Конфигурация тестового окружения
 * Настройки для различных типов тестов и окружений
 */

export interface TestConfig {
  // Общие настройки тестов
  timeout: number;
  parallel: boolean;
  retries: number;

  // Настройки тестового окружения
  environment: 'development' | 'test' | 'staging' | 'production';
  
  // Настройки моков
  mocks: {
    supabase: {
      enabled: boolean;
      mockData: boolean;
      simulateNetworkDelay: boolean;
      networkDelayRange: [number, number]; // [min, max] в миллисекундах
    };
    http: {
      enabled: boolean;
      mockExternalApis: boolean;
      baseUrl: string;
    };
    database: {
      enabled: boolean;
      useInMemoryDb: boolean;
    };
  };

  // Настройки покрытия кода
  coverage: {
    enabled: boolean;
    threshold: {
      statements: number;
      branches: number;
      functions: number;
      lines: number;
    };
    exclude: string[];
    include: string[];
  };

  // Настройки для различных типов тестов
  testTypes: {
    unit: {
      enabled: boolean;
      timeout: number;
      isolated: boolean;
      cleanup: boolean;
    };
    integration: {
      enabled: boolean;
      timeout: number;
      database: {
        useTestDb: boolean;
        rollback: boolean;
      };
    };
    e2e: {
      enabled: boolean;
      timeout: number;
      headless: boolean;
      viewport: {
        width: number;
        height: number;
      };
    };
  };

  // Логирование
  logging: {
    level: 'debug' | 'info' | 'warn' | 'error';
    showTimestamps: boolean;
    showColors: boolean;
    includeStackTrace: boolean;
  };

  // Настройки производительности
  performance: {
    enabled: boolean;
    slowTestThreshold: number; // миллисекунды
    memoryTracking: boolean;
    gcBeforeTests: boolean;
  };

  // Настройки безопасности
  security: {
    validateInputs: boolean;
    sanitizeOutputs: boolean;
    checkForSensitiveData: boolean;
  };
}

// Текущая конфигурация по умолчанию
export const defaultConfig: TestConfig = {
  timeout: 30000,
  parallel: true,
  retries: 0,

  environment: 'test',

  mocks: {
    supabase: {
      enabled: true,
      mockData: true,
      simulateNetworkDelay: false,
      networkDelayRange: [10, 100],
    },
    http: {
      enabled: true,
      mockExternalApis: true,
      baseUrl: 'https://api.test.example.com',
    },
    database: {
      enabled: true,
      useInMemoryDb: true,
    },
  },

  coverage: {
    enabled: true,
    threshold: {
      statements: 80,
      branches: 70,
      functions: 80,
      lines: 80,
    },
    exclude: [
      'tests/**/*',
      '**/*.d.ts',
      '**/*.test.*',
      '**/*.spec.*',
      '**/mocks/**/*',
      '**/fixtures/**/*',
      '**/node_modules/**/*',
    ],
    include: [
      'supabase/functions/**/*',
      'src/**/*',
    ],
  },

  testTypes: {
    unit: {
      enabled: true,
      timeout: 5000,
      isolated: true,
      cleanup: true,
    },
    integration: {
      enabled: true,
      timeout: 15000,
      database: {
        useTestDb: true,
        rollback: true,
      },
    },
    e2e: {
      enabled: false, // Отключен по умолчанию
      timeout: 30000,
      headless: true,
      viewport: {
        width: 1920,
        height: 1080,
      },
    },
  },

  logging: {
    level: 'info',
    showTimestamps: true,
    showColors: true,
    includeStackTrace: true,
  },

  performance: {
    enabled: true,
    slowTestThreshold: 1000,
    memoryTracking: false,
    gcBeforeTests: false,
  },

  security: {
    validateInputs: true,
    sanitizeOutputs: true,
    checkForSensitiveData: true,
  },
};

// Конфигурация для различных окружений
export const environmentConfigs: Record<string, Partial<TestConfig>> = {
  development: {
    logging: {
      level: 'debug',
      showTimestamps: true,
      showColors: true,
      includeStackTrace: true,
    },
    performance: {
      enabled: true,
      slowTestThreshold: 2000,
      memoryTracking: true,
      gcBeforeTests: false,
    },
    mocks: {
      supabase: {
        enabled: true,
        mockData: true,
        simulateNetworkDelay: false,
        networkDelayRange: [10, 100],
      },
      http: {
        enabled: true,
        mockExternalApis: true,
        baseUrl: 'https://api.dev.example.com',
      },
      database: {
        enabled: true,
        useInMemoryDb: true,
      },
    },
  },

  test: {
    logging: {
      level: 'warn',
      showTimestamps: false,
      showColors: false,
      includeStackTrace: false,
    },
    mocks: {
      supabase: {
        enabled: true,
        mockData: true,
        simulateNetworkDelay: true,
        networkDelayRange: [50, 200],
      },
      http: {
        enabled: true,
        mockExternalApis: true,
        baseUrl: 'https://api.test.example.com',
      },
      database: {
        enabled: true,
        useInMemoryDb: true,
      },
    },
  },

  staging: {
    environment: 'staging',
    mocks: {
      supabase: {
        enabled: true,
        mockData: false,
        simulateNetworkDelay: false,
        networkDelayRange: [10, 100],
      },
      http: {
        enabled: true,
        mockExternalApis: false,
        baseUrl: 'https://api.staging.example.com',
      },
      database: {
        enabled: false,
        useInMemoryDb: false,
      },
    },
  },
};

// Класс для управления конфигурацией
export class TestConfigManager {
  private static config: TestConfig = { ...defaultConfig };

  /**
   * Получение текущей конфигурации
   */
  static getConfig(): TestConfig {
    return { ...this.config };
  }

  /**
   * Установка конфигурации
   */
  static setConfig(config: Partial<TestConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Обновление части конфигурации
   */
  static update(path: string, value: any): void {
    const keys = path.split('.');
    let current: any = this.config;
    
    for (let i = 0; i < keys.length - 1; i++) {
      if (!(keys[i] in current)) {
        current[keys[i]] = {};
      }
      current = current[keys[i]];
    }
    
    current[keys[keys.length - 1]] = value;
  }

  /**
   * Получение значения по пути
   */
  static get(path: string): any {
    const keys = path.split('.');
    let current: any = this.config;
    
    for (const key of keys) {
      if (current === null || current === undefined || !(key in current)) {
        return undefined;
      }
      current = current[key];
    }
    
    return current;
  }

  /**
   * Загрузка конфигурации для окружения
   */
  static loadForEnvironment(environment: string): void {
    const envConfig = environmentConfigs[environment];
    if (envConfig) {
      this.setConfig(envConfig);
    }
  }

  /**
   * Валидация конфигурации
   */
  static validate(): string[] {
    const errors: string[] = [];

    // Проверка timeout
    if (this.config.timeout < 0 || this.config.timeout > 300000) {
      errors.push('timeout должен быть в диапазоне 0-300000');
    }

    // Проверка threshold покрытия
    const { threshold } = this.config.coverage;
    const thresholds = ['statements', 'branches', 'functions', 'lines'] as const;
    
    for (const key of thresholds) {
      if (threshold[key] < 0 || threshold[key] > 100) {
        errors.push(`coverage.threshold.${key} должен быть в диапазоне 0-100`);
      }
    }

    // Проверка сетевых задержек
    const [min, max] = this.config.mocks.supabase.networkDelayRange;
    if (min < 0 || max < min) {
      errors.push('networkDelayRange должен содержать валидные значения [min, max]');
    }

    return errors;
  }

  /**
   * Создание конфигурации для конкретного типа теста
   */
  static getConfigForTestType(type: 'unit' | 'integration' | 'e2e'): Partial<TestConfig> {
    const testTypeConfig = this.config.testTypes[type];
    
    return {
      timeout: testTypeConfig.timeout,
      mocks: {
        supabase: {
          ...this.config.mocks.supabase,
          simulateNetworkDelay: testTypeConfig.timeout > 10000,
        },
        http: this.config.mocks.http,
        database: this.config.mocks.database,
      },
      logging: this.config.logging,
      performance: this.config.performance,
    };
  }

  /**
   * Экспорт конфигурации в JSON
   */
  static export(): string {
    return JSON.stringify(this.config, null, 2);
  }

  /**
   * Импорт конфигурации из JSON
   */
  static import(configJson: string): void {
    try {
      const config = JSON.parse(configJson);
      this.setConfig(config);
    } catch (error) {
      throw new Error(`Ошибка импорта конфигурации: ${error.message}`);
    }
  }
}

// Инициализация конфигурации при загрузке модуля
TestConfigManager.loadForEnvironment(Deno.env.get('TEST_ENV') || 'test');

// Экспорт экземпляра конфигурации
export const testConfig = TestConfigManager.getConfig();

// Экспорт утилит для работы с конфигурацией
export const configUtils = {
  get: TestConfigManager.get.bind(TestConfigManager),
  set: TestConfigManager.update.bind(TestConfigManager),
  validate: TestConfigManager.validate.bind(TestConfigManager),
  getForType: TestConfigManager.getConfigForTestType.bind(TestConfigManager),
};