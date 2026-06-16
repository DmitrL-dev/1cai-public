/**
 * Mock данные для тестирования Edge Functions
 */

export const mockPerformanceMetrics = {
  generateCode: {
    stepsCount: 5,
    averageStepTime: 500,
    codeGenerationTime: 2000,
    totalTime: 2500,
    memoryPeak: 50 * 1024 * 1024 // 50 MB
  },

  optimizeCode: {
    stepsCount: 4,
    averageStepTime: 600,
    optimizationTime: 1800,
    totalTime: 2200,
    memoryPeak: 45 * 1024 * 1024 // 45 MB
  },

  customProcessing: {
    stepsCount: 6,
    averageStepTime: 400,
    processingTime: 1500,
    totalTime: 1800,
    memoryPeak: 40 * 1024 * 1024 // 40 MB
  }
};

export const mockCodeSamples = {
  catalog1C: `// Модуль справочника товаров
Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)
    УстановитьПривилегированныйРежим(Истина);
    Если Объект.Ссылка.Пустая() Тогда
        Объект.Артикул = ПолучитьНовыйАртикул();
        Объект.ДатаСоздания = ТекущаяДата();
    КонецЕсли;
    УстановитьПривилегированныйРежим(Ложь);
КонецПроцедуры`,

  document1C: `// Модуль документа приходной накладной
Процедура ОбработкаПроведения(Отказ, Режим)
    Движения.ОстаткиТоваров.Записывать = Истина;
    Движения.ОстаткиТоваров.Очистить();
    
    Если Объект.Товары.Количество() = 0 Тогда
        Сообщить("Не заполнена табличная часть");
        Отказ = Истина;
        Возврат;
    КонецЕсли;
КонецПроцедуры`,

  register1C: `// Регистр накопления остатков товаров
Функция ПолучитьОстаткиТоваров(Склад, Товар = Неопределено)
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ | ОстаткиТоваровОстатки.КоличествоОстаток";
    Возврат Запрос.Выполнить().Выгрузить();
КонецФункции`,

  optimizedSQL: `SELECT 
    Товары.Наименование,
    Товары.Артикул,
    ОстаткиТоваров.Количество
FROM Товары
INNER JOIN ОстаткиТоваров WITH(INDEX(IX_ОстаткиТоваров_Склад_Товар))
    ON Товары.Ссылка = ОстаткиТоваров.Товар
WHERE ОстаткиТоваров.Склад = &Склад
    AND ОстаткиТоваров.Количество > 0
ORDER BY Товары.Наименование`,

  apiCode1C: `// HTTP-сервис для интеграции
&НаСервере
Функция ОтправитьЗапросВнешнейСистеме(Метод, Параметры)
    HTTPСоединение = Новый HTTPСоединение("api.external-system.com", 443);
    HTTPЗапрос = Новый HTTPЗапрос("/" + Метод);
    HTTPЗапрос.Заголовки.Вставить("Content-Type", "application/json");
    HTTPОтвет = HTTPСоединение.ВызватьHTTPМетод("POST", HTTPЗапрос);
    Возврат РазобратьОтветJSON(HTTPОтвет.ПолучитьТелоКакСтроку());
КонецФункции`
};

export const mockErrorScenarios = {
  invalidJSON: {
    request: '{ invalid json }',
    expectedError: 'Неверный формат данных запроса'
  },

  missingRequiredField: {
    request: { demoType: 'custom' },
    expectedError: 'Параметр demoType обязателен для указания'
  },

  unsupportedMethod: {
    method: 'PUT',
    expectedError: 'Unsupported method: PUT'
  },

  wrongContentType: {
    headers: { 'Content-Type': 'text/plain' },
    expectedError: 'Content-Type must be application/json'
  },

  networkTimeout: {
    delay: 15000, // 15 seconds
    expectedError: 'Request timeout'
  },

  serverError: {
    trigger: 'simulate_internal_error',
    expectedError: 'Внутренняя ошибка сервера'
  }
};

export const mockRateLimitData = {
  allowedRequests: 100,
  timeWindow: 3600, // 1 hour
  burstLimit: 10,
  resetTime: 3600
};

export const mockUserQueries = {
  catalog: [
    'создать справочник товаров',
    'создать справочник номенклатуры',
    'справочник клиентов с кодами',
    'catalog товаров с иерархией'
  ],

  document: [
    'создать документ продажи',
    'документ приходной накладной',
    'document заказа покупателя',
    'документ с движениями по регистрам'
  ],

  register: [
    'создать регистр накопления остатков',
    'регистр сведений цен',
    'register операций',
    'регистр бухгалтерии с субконто'
  ],

  report: [
    'создать отчет продаж',
    'отчет по остаткам товаров',
    'report финансовых показателей',
    'отчет с диаграммами'
  ],

  processing: [
    'создать обработку загрузки данных',
    'обработка массового изменения цен',
    'processing импорта из Excel',
    'обработка синхронизации'
  ],

  optimization: [
    'оптимизировать SQL запрос',
    'ускорить выполнение отчета',
    'оптимизация производительности',
    'improve database queries'
  ],

  api: [
    'создать API для интеграции',
    'веб-сервис для внешних систем',
    'REST API методы',
    'интеграция с CRM системой'
  ]
};

export const mockStepProgressions = {
  customProcessing: [
    { progress: 10, message: 'Анализ вашего запроса...' },
    { progress: 30, message: 'Подготовка кода...' },
    { progress: 60, message: 'Генерация решения...' },
    { progress: 90, message: 'Оптимизация и форматирование...' },
    { progress: 100, message: 'Код успешно сгенерирован!' }
  ],

  generateCode: [
    { progress: 10, message: 'Запуск генерации кода...' },
    { progress: 25, message: 'Анализ требований к справочнику товаров...' },
    { progress: 50, message: 'Генерация структуры модуля...' },
    { progress: 75, message: 'Создание обработчиков событий...' },
    { progress: 90, message: 'Добавление валидации и проверок...' },
    { progress: 100, message: '✅ Код сгенерирован' }
  ],

  optimizeCode: [
    { progress: 10, message: 'Запуск оптимизации...' },
    { progress: 30, message: 'Анализ SQL запроса...' },
    { progress: 60, message: 'Выявление узких мест' },
    { progress: 85, message: 'Применение оптимизаций...' },
    { progress: 100, message: '✅ Производительность улучшена' }
  ],

  apiIntegration: [
    { progress: 10, message: 'Запуск создания API интеграции...' },
    { progress: 25, message: 'Анализ спецификации API...' },
    { progress: 50, message: 'Генерация методов интеграции...' },
    { progress: 75, message: 'Добавление обработки ошибок...' },
    { progress: 100, message: '✅ API интеграция готова' }
  ]
};

export const mockSecurityTests = {
  sqlInjection: {
    userQuery: "'; DROP TABLE users; --",
    expectedBehavior: 'safe_handling'
  },

  xssAttempt: {
    userQuery: '<script>alert("xss")</script>',
    expectedBehavior: 'sanitized'
  },

  pathTraversal: {
    userQuery: '../../../etc/passwd',
    expectedBehavior: 'blocked'
  },

  oversizedRequest: {
    userQuery: 'x'.repeat(10000),
    expectedBehavior: 'rejected'
  },

  specialCharacters: {
    userQuery: 'тест "кавычки" \\backslash /slash |pipe',
    expectedBehavior: 'handled_correctly'
  }
};
