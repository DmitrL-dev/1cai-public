Deno.serve(async (req) => {
    const corsHeaders = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
        'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
        'Access-Control-Max-Age': '86400',
        'Access-Control-Allow-Credentials': 'false'
    };

    if (req.method === 'OPTIONS') {
        return new Response(null, { status: 200, headers: corsHeaders });
    }

    try {
        const { demoType, userQuery } = await req.json();

        const steps = [];
        let finalResult = {};

        if (demoType === 'custom') {
            // Пользовательский запрос
            steps.push({ progress: 10, message: 'Обработка вашего запроса...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Анализ требований и контекста...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 60, message: 'Формирование архитектурного решения...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 90, message: 'Подготовка финального ответа...' });
            await new Promise(r => setTimeout(r, 700));
            
            // Генерируем ответ на основе пользовательского запроса
            const queryLower = (userQuery || '').toLowerCase();
            
            let customMessage = '';
            let customDiagram = '';
            let customComponents = {};
            
            // Функция для проверки наличия терминов с учетом синонимов
            const containsTerm = (text, terms) => {
                return terms.some(term => text.includes(term));
            };

            // Словари синонимов для интеллектуального анализа
            const synonymGroups = {
                erp: ['erp', 'система управления ресурсами предприятия', 'erp-система', 'корпоративная система', 'управление предприятием', 'enterprise resource planning'],
                crm: ['crm', 'система управления взаимоотношениями с клиентами', 'crm-система', 'клиентский сервис', 'управление клиентами', 'отношения с клиентами', 'продажи', 'customer relationship'],
                wms: ['wms', 'система управления складом', 'warehouse management', 'управление складскими операциями', 'складская система', 'операции на складе', 'перемещение товаров'],
                integration: ['интеграц', 'api', 'rest', 'soap', 'обмен данными', 'синхронизация', 'обмен', 'интегрировать', 'подключение', 'связь между системами'],
                accounting: ['бухгалтер', 'учет', 'бухучет', 'бухгалтерский учет', 'финансовый учет', 'проводки', 'дебет', 'кредит', 'баланс', 'бухгалтерия'],
                documentFlow: ['документооборот', 'документ', 'согласование', 'утверждение', 'workflow', 'процесс документооборота', 'электронные документы'],
                payroll: ['заработная плата', 'зарплата', 'расчет зарплаты', 'кадровый учет', 'штатное расписание', 'табель', 'отпуск', 'больничный', 'оклад'],
                inventory: ['складской учет', 'учет товаров', 'остатки', 'движение товаров', 'товародвижение', 'инвентаризация', 'номенклатура'],
                trade: ['торговля', 'торговля', 'продажа товаров', 'розница', 'оптовая торговля', 'касса', 'розничная торговля', 'опт'],
                production: ['производство', 'производственный', 'цех', 'технологический процесс', 'производственная линия', 'выпуск продукции', 'производственный учет'],
                finance: ['финансы', 'финансовый', 'бюджетирование', 'финансовое планирование', 'денежные средства', 'финансовый анализ', 'казначейство'],
                database: ['база', 'database', 'бд', 'данны', 'хранение данных', 'структура данных'],
                microservices: ['микросервис', 'microservice', 'сервис', 'декомпозиция'],
                security: ['безопасн', 'security', 'защит', 'аутентификация', 'авторизация', 'шифрование'],
                monitoring: ['монитор', 'мониторинг', 'observability', 'логирование', 'метрики']
            };

            // Расширенная интеллектуальная логика анализа
            // 1. ERP системы
            if (containsTerm(queryLower, synonymGroups.erp)) {
                customDiagram = `graph TB
    ERP[ERP Система]
    ERP --> Finance[Финансовый модуль]
    ERP --> Sales[Модуль продаж]
    ERP --> Purchase[Модуль закупок]
    ERP --> HR[Кадровый модуль]
    ERP --> Production[Производство]
    ERP --> Inventory[Складской учет]
    Finance --> Reports[Отчетность]
    Sales --> Customers[Клиенты]
    Purchase --> Suppliers[Поставщики]
    HR --> Payroll[Расчет зарплаты]`;
                customComponents = {
                    modules: 6,
                    integrations: 8,
                    complexity: 'Very High',
                    estimatedTime: '12-16 недель',
                    technologies: ['1C:Предприятие', 'PostgreSQL', 'MS SQL Server']
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создана архитектура ERP системы:
• 6 основных модулей: Финансы, Продажи, Закупки, HR, Производство, Склад
• Интеграция с внешними системами через API
• Высокая сложность архитектуры
• Оценка сроков: 12-16 недель
• Рекомендуемые технологии: 1C:Предприятие, PostgreSQL`;

            // 2. CRM системы
            } else if (containsTerm(queryLower, synonymGroups.crm)) {
                customDiagram = `graph TB
    CRM[CRM Система]
    CRM --> Contacts[Контактные лица]
    CRM --> Leads[Лиды и возможности]
    CRM --> Sales[Воронка продаж]
    CRM --> Marketing[Маркетинговые кампании]
    CRM --> Analytics[Аналитика и отчеты]
    CRM --> Integration[Интеграция с 1С]
    Sales --> Pipeline[Трубопровод сделок]
    Marketing --> Campaigns[Email-кампании]
    Analytics --> Reports[Отчеты по продажам]`;
                customComponents = {
                    modules: 5,
                    features: ['Управление лидами', 'Воронка продаж', 'Интеграция с 1С'],
                    complexity: 'Medium',
                    estimatedTime: '6-8 недель'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Разработана архитектура CRM системы:
• Управление контактными лицами и лидами
• Воронка продаж с автоматизацией
• Маркетинговые кампании и email-маркетинг
• Интеграция с 1С для синхронизации данных
• Аналитика и отчеты по продажам`;

            // 3. Складские системы WMS
            } else if (containsTerm(queryLower, synonymGroups.wms) || containsTerm(queryLower, synonymGroups.inventory)) {
                customDiagram = `graph TB
    WMS[WMS Система]
    WMS --> Receiving[Приемка товаров]
    WMS --> Storage[Хранение]
    WMS --> Picking[Комплектация заказов]
    WMS --> Shipping[Отгрузка]
    WMS --> Inventory[Учет остатков]
    WMS --> Barcode[Сканирование ШК]
    WMS --> Integration[Интеграция с 1С]
    Receiving --> Quality[Контроль качества]
    Storage --> Zones[Складские зоны]
    Picking --> Orders[Заказы клиентов]
    Barcode --> Items[Товарные позиции]`;
                customComponents = {
                    modules: 6,
                    integrations: ['1С', 'TMS', 'WMS', 'EDI'],
                    complexity: 'High',
                    estimatedTime: '10-12 недель',
                    features: ['Штрих-коды', 'Мобильные терминалы', 'Автоматизация']
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создана архитектура WMS системы:
• Полный цикл складских операций: приемка, хранение, комплектация, отгрузка
• Интеграция с 1С для синхронизации данных
• Штрих-кодирование и мобильные терминалы
• Контроль качества при приемке
• Управление складскими зонами`;

            // 4. Интеграция с 1С
            } else if (containsTerm(queryLower, synonymGroups.integration) && queryLower.includes('1с')) {
                customDiagram = `sequenceDiagram
    participant External as Внешняя система
    participant Gateway as API Gateway
    participant OneC as 1С:Предприятие
    participant DB as База данных
    External->>Gateway: REST запрос
    Gateway->>OneC: OData/Web сервис
    OneC->>DB: SQL запрос
    DB-->>OneC: Данные
    OneC-->>Gateway: Результат
    Gateway-->>External: JSON ответ`;
                customComponents = {
                    integrationType: 'OData/REST',
                    protocols: ['OData', 'REST API', 'COM'],
                    complexity: 'Medium',
                    estimatedTime: '4-6 недель',
                    entities: ['Номенклатура', 'Контрагенты', 'Документы']
                };
                customMessage = `Анализ запроса: "${userQuery}"

Разработана архитектура интеграции с 1С:
• Протокол OData для веб-сервисов
• REST API для внешних систем
• Синхронизация основных сущностей
• Обработка ошибок и логирование
• Поддержка различных версий 1С`;

            // 5. Бухгалтерский учет
            } else if (containsTerm(queryLower, synonymGroups.accounting)) {
                customDiagram = `graph TB
    Accounting[Бухгалтерская система]
    Accounting --> Documents[Бухгалтерские документы]
    Accounting --> Accounts[План счетов]
    Accounting --> Operations[Хозяйственные операции]
    Accounting --> Reports[Бухгалтерские отчеты]
    Accounting --> Tax[Налоговый учет]
    Documents --> Invoices[Счета-фактуры]
    Documents --> Payments[Платежные поручения]
    Operations --> Debit[Дебет]
    Operations --> Credit[Кредит]
    Reports --> Balance[Баланс]
    Reports --> PnL[Отчет о прибылях и убытках]`;
                customComponents = {
                    modules: 5,
                    reports: ['Баланс', 'ОПУ', 'ДДС'],
                    complexity: 'High',
                    estimatedTime: '8-10 недель',
                    compliance: ['РСБУ', 'МСФО']
                };
                customMessage = `Анализ запроса: "${userQuery}"

Спроектирована система бухгалтерского учета:
• Ведение хозяйственных операций по двойной записи
• Формирование обязательных отчетов
• Налоговый учет в соответствии с требованиями
• Интеграция с банк-клиентом
• Архивирование документов`;

            // 6. Документооборот
            } else if (containsTerm(queryLower, synonymGroups.documentFlow)) {
                customDiagram = `graph TB
    DocFlow[Система документооборота]
    DocFlow --> Creation[Создание документа]
    DocFlow --> Approval[Согласование]
    DocFlow --> Execution[Исполнение]
    DocFlow --> Archive[Архивирование]
    DocFlow --> Templates[Шаблоны]
    Approval --> Routing[Маршрутизация]
    Approval --> Signatures[Электронные подписи]
    Execution --> Tasks[Задачи]
    Execution --> Monitoring[Контроль исполнения]
    Archive --> Search[Поиск по архиву]`;
                customComponents = {
                    features: ['Маршрутизация документов', 'ЭЦП', 'Поиск', 'Интеграция с 1С'],
                    complexity: 'Medium',
                    estimatedTime: '6-8 недель',
                    workflows: 3
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создана система документооборота:
• Электронный документооборот с маршрутизацией
• Согласование и утверждение документов
• Электронные цифровые подписи
• Поиск по архиву документов
• Интеграция с 1С и внешними системами`;

            // 7. Учет заработной платы
            } else if (containsTerm(queryLower, synonymGroups.payroll)) {
                customDiagram = `graph TB
    Payroll[Система расчета зарплаты]
    Payroll --> Employees[Штатное расписание]
    Payroll --> TimeTracking[Табель учета времени]
    Payroll --> Salary[Расчет зарплаты]
    Payroll --> Taxes[Налоговый учет]
    Payroll --> Reports[Отчеты в фонды]
    TimeTracking --> WorkHours[Отработанное время]
    TimeTracking --> Leave[Отпуска и больничные]
    Salary --> Base[Оклад/тариф]
    Salary --> Bonuses[Премии]
    Taxes --> PFR[ПФР]
    Taxes --> FSS[ФСС]
    Reports --> 2NDFL[Справки 2-НДФЛ]`;
                customComponents = {
                    modules: 5,
                    reports: ['РСВ', 'СЗВ-М', '2-НДФЛ'],
                    complexity: 'Medium',
                    estimatedTime: '6-8 недель',
                    compliance: ['ТК РФ', 'НК РФ']
                };
                customMessage = `Анализ запроса: "${userQuery}"

Разработана система учета заработной платы:
• Штатное расписание и тарифные сетки
• Табель учета рабочего времени
• Автоматический расчет зарплаты и налогов
• Формирование отчетности в контролирующие органы
• Соответствие требованиям ТК РФ и НК РФ`;

            // 8. Торговля
            } else if (containsTerm(queryLower, synonymGroups.trade)) {
                customDiagram = `graph TB
    Trade[Торговая система]
    Trade --> Orders[Заказы клиентов]
    Trade --> Pricing[Ценообразование]
    Trade --> Inventory[Товарный запас]
    Trade --> SalesChannels[Каналы продаж]
    Trade --> Customers[Клиенты]
    Trade --> Analytics[Аналитика продаж]
    Orders --> WebShop[Интернет-магазин]
    Orders --> Retail[Розница]
    Orders --> Wholesale[Опт]
    Pricing --> Discounts[Скидки и акции]
    Analytics --> Reports[Отчеты по продажам]
    Analytics --> Forecast[Прогнозирование спроса]`;
                customComponents = {
                    channels: 3,
                    features: ['Интеграция с кассой', 'Онлайн-платежи', 'Аналитика'],
                    complexity: 'Medium',
                    estimatedTime: '8-10 недель'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создана торговая система:
• Многоканальные продажи: опт, розница, интернет
• Управление ценообразованием и скидками
• Интеграция с кассовым оборудованием
• Аналитика продаж и прогнозирование спроса
• Управление товарными запасами`;

            // 9. Производство
            } else if (containsTerm(queryLower, synonymGroups.production)) {
                customDiagram = `graph TB
    Production[Система управления производством]
    Production --> Planning[Планирование производства]
    Production --> Manufacturing[Процесс производства]
    Production --> Quality[Контроль качества]
    Production --> Materials[Управление материалами]
    Production --> Equipment[Учет оборудования]
    Planning --> MRP[MRP планирование]
    Manufacturing --> Workshop[Участки/цеха]
    Manufacturing --> Operations[Технологические операции]
    Quality --> QC[Входной контроль]
    Quality --> Testing[Контроль готовой продукции]
    Materials --> BOM[Спецификации]
    Equipment --> Maintenance[Планирование ТОиР]`;
                customComponents = {
                    modules: 5,
                    features: ['MRP планирование', 'MES интеграция', 'ТОиР'],
                    complexity: 'Very High',
                    estimatedTime: '12-14 недель',
                    planning: 'MRP/ERP'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Спроектирована система управления производством:
• MRP планирование потребности в материалах
• Технологические карты и нормы времени
• Контроль качества на всех этапах
• Планирование ТОиР оборудования
• Интеграция с системами класса MES`;

            // 10. Финансы и бюджетирование
            } else if (containsTerm(queryLower, synonymGroups.finance)) {
                customDiagram = `graph TB
    Finance[Финансовая система]
    Finance --> Budgeting[Бюджетирование]
    Finance --> CashFlow[Денежные потоки]
    Finance --> Treasury[Казначейство]
    Finance --> Reporting[Финансовая отчетность]
    Finance --> Planning[Финансовое планирование]
    Budgeting --> Operating[Операционный бюджет]
    Budgeting --> Capital[Капитальный бюджет]
    CashFlow --> Inflows[Поступления]
    CashFlow --> Outflows[Выплаты]
    Treasury --> Payments[Платежи]
    Treasury --> Receivables[Дебиторка]
    Reporting --> Management[Управленческая отчетность]`;
                customComponents = {
                    modules: 4,
                    reports: ['ДДС', 'ОПУ', 'Баланс', 'Бюджет движения средств'],
                    complexity: 'High',
                    estimatedTime: '10-12 недель',
                    planning: '12+ месяцев'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Разработана финансовая система:
• Бюджетное управление (операционный и капитальный бюджеты)
• Управление денежными потоками и казначейством
• Многовалютный учет и курсовые разницы
• Управленческая и консолидированная отчетность
• Финансовое планирование на горизонте 12+ месяцев`;

            // 11. Интеграция и API
            } else if (containsTerm(queryLower, synonymGroups.integration)) {
                customDiagram = `sequenceDiagram
    participant Client
    participant Gateway
    participant Service
    participant External
    participant Queue
    Client->>Gateway: API Request
    Gateway->>Service: Process
    Service->>External: Call External API
    External-->>Service: Response
    Service->>Queue: Async Task
    Queue->>Service: Process Result
    Service-->>Gateway: Result
    Gateway-->>Client: API Response`;
                customComponents = {
                    endpoints: 8,
                    methods: ['POST', 'GET', 'PUT', 'DELETE'],
                    authentication: 'OAuth 2.0 + JWT',
                    async: true
                };
                customMessage = `Анализ запроса: "${userQuery}"

Разработана архитектура API интеграции:
• Паттерн: API Gateway + Event-Driven Architecture
• 8+ endpoints с REST API
• Асинхронная обработка задач через очереди
• Аутентификация: OAuth 2.0 + JWT
• Мониторинг и логирование интеграций`;

            // 12. База данных
            } else if (containsTerm(queryLower, synonymGroups.database)) {
                customDiagram = `graph TB
    App[Приложение] --> Master[(Master DB)]
    Master --> Replica1[(Replica 1)]
    Master --> Replica2[(Replica 2)]
    Master --> Backup[(Backup)]
    App --> Cache[Redis Cache]
    Master --> Analytics[(Analytics DB)]
    Master --> Archive[(Archive DB)]
    Replica1 --> ReadLoad[Read Load]
    Replica2 --> ReadLoad
    Cache --> Session[Session Store]`;
                customComponents = {
                    databases: 5,
                    replication: 'Master-Slave + Multi-Region',
                    caching: 'Redis + Application Level',
                    backup: 'Continuous + Daily Snapshots'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Спроектирована архитектура базы данных:
• Master-Slave репликация с геораспределением
• 2+ реплики для масштабирования чтения
• Многоуровневое кэширование: Redis + приложение
• Analytics и Archive базы для отчетности
• Непрерывное резервное копирование`;

            // 13. Микросервисы
            } else if (containsTerm(queryLower, synonymGroups.microservices)) {
                customDiagram = `graph TB
    Gateway[API Gateway] --> AuthService[Auth Service]
    Gateway --> UserService[User Service]
    Gateway --> OrderService[Order Service]
    Gateway --> PaymentService[Payment Service]
    Gateway --> NotificationService[Notification Service]
    OrderService --> MessageQueue[Message Queue]
    PaymentService --> MessageQueue
    NotificationService --> MessageQueue
    MessageQueue --> EventStore[Event Store]`;
                customComponents = {
                    services: 5,
                    pattern: 'Microservices + Event Sourcing',
                    communication: 'REST + Event-Driven',
                    scalability: 'Horizontal per Service'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Разработана микросервисная архитектура:
• 5+ независимых сервисов с четкими границами
• Event Sourcing для сохранения состояния системы
• Асинхронная коммуникация через Event Store
• API Gateway для единой точки входа
• Горизонтальное масштабирование каждого сервиса`;

            // 14. Безопасность
            } else if (containsTerm(queryLower, synonymGroups.security)) {
                customDiagram = `graph TB
    Internet[Интернет] --> WAF[WAF]
    WAF --> LoadBalancer[Load Balancer]
    LoadBalancer --> App[Application]
    App --> Auth[Auth Service]
    App --> RBAC[Role-Based Access]
    App --> Encryption[Encryption Layer]
    Auth --> JWT[JWT Tokens]
    RBAC --> Permissions[Permissions Matrix]
    Encryption --> TLS[TLS/SSL]`;
                customComponents = {
                    layers: 6,
                    security: ['WAF', 'OAuth 2.0', 'RBAC', 'TLS', 'Encryption'],
                    compliance: ['ISO 27001', 'GDPR']
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создана многоуровневая система безопасности:
• Web Application Firewall (WAF) от веб-атак
• OAuth 2.0 + JWT для аутентификации
• Role-Based Access Control (RBAC) для авторизации
• End-to-end шифрование данных
• Соответствие стандартам ISO 27001 и GDPR`;

            // 15. Мониторинг и observability
            } else if (containsTerm(queryLower, synonymGroups.monitoring)) {
                customDiagram = `graph TB
    App[Application] --> Metrics[Prometheus]
    App --> Logs[ELK Stack]
    App --> Traces[Jaeger]
    App --> Health[Health Checks]
    Metrics --> AlertManager[AlertManager]
    Metrics --> Grafana[Grafana Dashboard]
    Logs --> Kibana[Kibana]
    Traces --> JaegerUI[Jaeger UI]
    AlertManager --> Slack[Slack]
    AlertManager --> Email[Email Notifications]`;
                customComponents = {
                    monitoring: 'Full Stack',
                    tools: ['Prometheus', 'Grafana', 'ELK', 'Jaeger'],
                    alerting: 'Real-time + SLA-based'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Спроектирована система мониторинга и observability:
• Full Stack мониторинг: метрики, логи, трассировка
• Prometheus для сбора метрик и Grafana для визуализации
• ELK Stack для централизованного логирования
• Jaeger для distributed tracing и анализа производительности
• Real-time оповещения в Slack и Email`;

            } else {
                // Универсальный ответ для любого другого запроса
                customDiagram = `graph TB
    UI[Пользовательский интерфейс]
    BL[Бизнес-логика]
    DAL[Слой доступа к данным]
    API[API Layer]
    DB[(База данных)]
    CACHE[(Кэш)]
    UI --> BL
    BL --> DAL
    DAL --> API
    API --> DB
    API --> CACHE`;
                customComponents = {
                    layers: 5,
                    pattern: 'Layered Architecture + Caching',
                    technologies: ['React', '1C', 'PostgreSQL', 'Redis']
                };
                customMessage = `Анализ запроса: "${userQuery}"

Предложена расширенная многослойная архитектура:
• 5 слоев: UI, бизнес-логика, DAL, API, БД + Кэш
• Паттерн: Layered Architecture с кэшированием
• Обеспечивает высокую производительность и масштабируемость
• Четкое разделение ответственности между слоями
• Рекомендуемые технологии: React, 1С, PostgreSQL, Redis`;
            }
            
            finalResult = {
                message: customMessage,
                diagram: customDiagram,
                components: customComponents,
                userQuery: userQuery
            };
            
            steps.push({ 
                progress: 100, 
                message: 'Готово! Архитектурное решение сформировано',
                result: finalResult
            });
            
        } else if (demoType === 'design') {
            // Архитектурное проектирование
            steps.push({ progress: 10, message: 'Запуск анализа требований...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Анализ требований к складской системе завершен' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 50, message: 'Определение основных компонентов: Справочники, Документы, Регистры' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 70, message: 'Проектирование структуры данных...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 90, message: 'Создание архитектурной схемы' });
            
            // Генерируем реальную Mermaid диаграмму
            const mermaidDiagram = `
erDiagram
    WAREHOUSE ||--o{ PRODUCT : contains
    WAREHOUSE {
        uuid id PK
        string name
        string address
        decimal capacity
    }
    PRODUCT ||--o{ STOCK : has
    PRODUCT {
        uuid id PK
        string name
        string sku
        decimal price
    }
    STOCK {
        uuid id PK
        uuid warehouse_id FK
        uuid product_id FK
        int quantity
        date last_updated
    }
    DOCUMENT ||--o{ MOVEMENT : records
    DOCUMENT {
        uuid id PK
        string doc_number
        date doc_date
        string type
    }
    MOVEMENT {
        uuid id PK
        uuid document_id FK
        uuid product_id FK
        int quantity
        string operation
    }
`;
            
            finalResult = {
                diagram: mermaidDiagram,
                components: {
                    catalogs: 5,
                    documents: 3,
                    registers: 4
                },
                complexity: 'Medium',
                estimatedTime: '4-6 недель'
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Архитектура спроектирована: 5 справочников, 3 документа, 4 регистра',
                result: finalResult
            });
            
        } else if (demoType === 'diagram') {
            steps.push({ progress: 10, message: 'Запуск генерации диаграммы...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 25, message: 'Анализ структуры системы...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 50, message: 'Генерация Mermaid диаграммы...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 75, message: 'Визуализация связей между компонентами...' });
            await new Promise(r => setTimeout(r, 800));
            
            const flowDiagram = `
graph TB
    User[Пользователь] --> UI[Web UI]
    UI --> Gateway[API Gateway]
    Gateway --> Auth[Сервис аутентификации]
    Gateway --> Warehouse[Сервис складских операций]
    Gateway --> Reports[Сервис отчетов]
    Warehouse --> DB[(База данных)]
    Reports --> DB
    Warehouse --> Queue[Очередь сообщений]
    Queue --> Notifications[Сервис уведомлений]
    Notifications --> Email[Email]
    Notifications --> SMS[SMS]
`;
            
            finalResult = {
                diagram: flowDiagram,
                type: 'flow',
                components: 8
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Диаграмма создана: ER-модель + схема взаимодействия',
                result: finalResult
            });
            
        } else if (demoType === 'analysis') {
            steps.push({ progress: 10, message: 'Запуск анализа рисков...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Сканирование архитектуры на предмет рисков...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 60, message: 'Анализ производительности...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 80, message: 'Оценка масштабируемости...' });
            await new Promise(r => setTimeout(r, 700));
            
            finalResult = {
                risks: {
                    critical: [
                        'Отсутствие индексов на таблице STOCK',
                        'Нет репликации базы данных',
                        'Единая точка отказа в API Gateway'
                    ],
                    high: [
                        'Недостаточная валидация входных данных',
                        'Отсутствие rate limiting',
                        'Нет мониторинга производительности',
                        'Устаревшие зависимости',
                        'Слабые политики паролей'
                    ],
                    medium: [
                        'Неоптимальные SQL запросы',
                        'Отсутствие кеширования',
                        'Недостаточное логирование'
                    ]
                },
                totalRisks: 11,
                criticalCount: 3,
                highCount: 5,
                mediumCount: 3
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Выявлено рисков: 3 критических, 5 высоких, 3 средних',
                result: finalResult
            });
        }

        return new Response(JSON.stringify({
            data: {
                steps,
                finalResult
            }
        }), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });

    } catch (error) {
        console.error('Architect demo error:', error);

        return new Response(JSON.stringify({
            error: {
                code: 'ARCHITECT_DEMO_ERROR',
                message: error.message
            }
        }), {
            status: 500,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
    }
});
