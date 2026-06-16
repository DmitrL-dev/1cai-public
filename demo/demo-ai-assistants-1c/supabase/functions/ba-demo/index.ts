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
        const requestData = await req.json();
        
        // Валидация входных данных
        if (!requestData || typeof requestData !== 'object') {
            throw new Error('Неверный формат данных запроса');
        }
        
        const { demoType, userQuery } = requestData;
        
        // Валидация обязательных полей
        if (!demoType) {
            throw new Error('Параметр demoType обязателен для указания');
        }
        
        // Валидация поддерживаемых типов демо
        const supportedDemoTypes = ['custom', 'requirements', 'process', 'stories', 'advanced'];
        if (!supportedDemoTypes.includes(demoType)) {
            throw new Error(`Неподдерживаемый тип демо: ${demoType}. Поддерживаемые: ${supportedDemoTypes.join(', ')}`);
        }
        
        // Валидация userQuery для custom типа
        if (demoType === 'custom' && (!userQuery || typeof userQuery !== 'string' || userQuery.trim().length === 0)) {
            throw new Error('Для типа "custom" параметр userQuery обязателен и должен быть непустой строкой');
        }
        
        // Санитизация userQuery
        const sanitizedUserQuery = demoType === 'custom' ? userQuery.trim() : null;

        const steps = [];
        let finalResult = {};

        if (demoType === 'custom') {
            // Пользовательский запрос
            steps.push({ progress: 10, message: 'Анализ вашего запроса...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Извлечение бизнес-требований...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 60, message: 'Структурирование данных...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 90, message: 'Формирование аналитического отчета...' });
            await new Promise(r => setTimeout(r, 700));
            
            const queryLower = (sanitizedUserQuery || '').toLowerCase();
            let analysis = {};
            let customMessage = '';
            
            // Анализ требований
            if (queryLower.includes('требован') || queryLower.includes('requirement')) {
                analysis = {
                    requirements: [
                        { id: 'REQ-001', type: 'Функциональное', priority: 'Высокий', description: 'Учет товаров', source: 'Бизнес-анализ.docx', complexity: 'Средняя' },
                        { id: 'REQ-002', type: 'Функциональное', priority: 'Средний', description: 'Отчетность', source: 'Совещание 15.10', complexity: 'Низкая' },
                        { id: 'REQ-003', type: 'Нефункциональное', priority: 'Высокий', description: 'Производительность', source: 'Тех.требования', complexity: 'Высокая' },
                        { id: 'REQ-004', type: 'Функциональное', priority: 'Высокий', description: 'Интеграция с 1С', source: 'Архитектура.docx', complexity: 'Высокая' },
                        { id: 'REQ-005', type: 'Нефункциональное', priority: 'Средний', description: 'Безопасность данных', source: 'Политика ИБ', complexity: 'Средняя' }
                    ],
                    totalRequirements: 5,
                    functional: 3,
                    nonFunctional: 2,
                    traceability: 'Полная прослеживаемость от бизнес-целей к тестам',
                    riskLevel: 'Средний'
                };
                customMessage = `Анализ требований: "${userQuery}"

Извлечено и структурировано 5 требований:
• 3 функциональных (учет товаров, отчетность, интеграция с 1С)
• 2 нефункциональных (производительность, безопасность)
• Установлена полная трассируемость требований
• Оценен риск реализации: средний уровень
• Все требования готовы к проектированию и разработке`;
            }
            // Анализ процессов и моделирование
            else if (queryLower.includes('процесс') || queryLower.includes('process') || queryLower.includes('bpmn')) {
                analysis = {
                    processes: [
                        { name: 'Приемка товаров', steps: 8, automation: '70%', time: '25 мин', owner: 'Кладовщик', status: 'Оптимизирован' },
                        { name: 'Размещение на складе', steps: 6, automation: '40%', time: '45 мин', owner: 'Кладовщик', status: 'Требует улучшения' },
                        { name: 'Отгрузка клиентам', steps: 7, automation: '60%', time: '35 мин', owner: 'Менеджер', status: 'В процессе' },
                        { name: 'Инвентаризация', steps: 12, automation: '30%', time: '4 часа', owner: 'Бухгалтер', status: 'Критичный' }
                    ],
                    totalProcesses: 4,
                    avgAutomation: '50%',
                    totalTime: '5ч 45мин/день',
                    optimization: {
                        bottleneck: 'Инвентаризация (12 шагов, 30% автоматизации)',
                        recommendation: 'Автоматизировать учет и сканирование штрих-кодов',
                        potential: 'Сокращение времени на 40%'
                    }
                };
                customMessage = `Моделирование бизнес-процессов: "${userQuery}"

Проанализированы 4 ключевых процесса:
• Общее время выполнения: 5ч 45мин/день
• Средняя автоматизация: 50% (низкий показатель)
• Узкое место: инвентаризация (12 шагов, требует критического внимания)
• Рекомендация: приоритетная автоматизация учета и сканирования
• Потенциал оптимизации: сокращение времени на 40%`;
            }
            // User Stories
            else if (queryLower.includes('user story') || queryLower.includes('история') || queryLower.includes('as a') || queryLower.includes('я хочу')) {
                analysis = {
                    userStories: [
                        {
                            id: 'US-001', title: 'Добавление товара',
                            asA: 'Кладовщик', iWant: 'иметь возможность добавлять новые товары',
                            soThat: 'вести полный учет склада',
                            acceptanceCriteria: [
                                'Форма содержит: наименование, артикул, цену, единицу измерения',
                                'Артикул автогенерация при отсутствии',
                                'Валидация обязательных полей',
                                'Отображение в справочнике после сохранения'
                            ],
                            priority: 'Высокий', estimation: '5 SP', status: 'Готово к разработке'
                        },
                        {
                            id: 'US-002', title: 'Учет остатков в реальном времени',
                            asA: 'Менеджер', iWant: 'видеть актуальные остатки товаров',
                            soThat: 'принимать обоснованные решения о закупках',
                            acceptanceCriteria: [
                                'Обновление данных при каждой операции',
                                'Отчет с фильтрами по складу и товарам',
                                'Экспорт в Excel/PDF',
                                'Уведомления при достижении минимума'
                            ],
                            priority: 'Высокий', estimation: '8 SP', status: 'Backlog'
                        }
                    ],
                    totalStories: 18,
                    withAcceptanceCriteria: 18,
                    avgStoryPoints: 5.2,
                    readyForSprint: 8
                };
                customMessage = `Генерация User Stories: "${userQuery}"

Создано 18 историй пользователей:
• 18 User Stories с полными критериями приемки
• Средняя оценка: 5.2 Story Points
• 8 историй готовы к включению в спринт
• Формат: "Как [роль], я хочу [функция], чтобы [цель]"
• Полная трассируемость от требований`;
            }
            // Use Cases
            else if (queryLower.includes('use case') || queryLower.includes('сценарий') || queryLower.includes('actor')) {
                analysis = {
                    useCases: [
                        {
                            id: 'UC-001', title: 'Управление товарами',
                            primaryActor: 'Кладовщик', stakeholders: ['Менеджер', 'Бухгалтер'],
                            mainFlow: '1. Открыть справочник товаров\n2. Добавить/редактировать товар\n3. Сохранить изменения',
                            alternativeFlows: [
                                'Отмена операции при ошибке валидации',
                                'Массовая загрузка через Excel'
                            ],
                            preconditions: 'Авторизация в системе', postconditions: 'Товар добавлен/изменен'
                        },
                        {
                            id: 'UC-002', title: 'Формирование отчетов',
                            primaryActor: 'Менеджер', stakeholders: ['Руководитель'],
                            mainFlow: '1. Выбрать тип отчета\n2. Установить фильтры\n3. Сформировать отчет\n4. Экспортировать результат',
                            alternativeFlows: [
                                'Автоматическая отправка по расписанию',
                                'Подписка на изменения данных'
                            ],
                            preconditions: 'Доступ к данным', postconditions: 'Отчет сформирован'
                        }
                    ],
                    totalUseCases: 12,
                    actors: ['Кладовщик', 'Менеджер', 'Бухгалтер', 'Руководитель', 'Система']
                };
                customMessage = `Моделирование Use Cases: "${userQuery}"

Создано 12 сценариев использования:
• 5 основных акторов с четкими ролями
• Детальное описание основных и альтернативных потоков
• Определены предусловия и постусловия для каждого сценария
• Учтены интересы всех заинтересованных сторон
• Готово для проектирования архитектуры системы`;
            }
            // Диаграммы потоков данных (DFD)
            else if (queryLower.includes('dfd') || queryLower.includes('поток данных') || queryLower.includes('data flow')) {
                analysis = {
                    dfd: {
                        level0: 'Контекстная диаграмма системы складского учета',
                        level1: [
                            { process: 'Управление товарами', dataFlows: 'Справочник товаров, Операции', dataStores: 'База товаров' },
                            { process: 'Учет движения', dataFlows: 'Документы движения', dataStores: 'Регистр остатков' },
                            { process: 'Формирование отчетов', dataFlows: 'Запросы отчетов', dataStores: 'Архив отчетов' }
                        ],
                        level2: [
                            { process: 'Приход товаров', parent: 'Учет движения', dataFlows: 'ТТН, Накладные' },
                            { process: 'Расход товаров', parent: 'Учет движения', dataFlows: 'Заказы, Накладные' }
                        ]
                    },
                    externalEntities: ['Поставщики', 'Покупатели', 'Бухгалтерия'],
                    dataStores: 5,
                    processes: 8
                };
                customMessage = `Диаграммы потоков данных (DFD): "${userQuery}"

Создана иерархия диаграмм:
• Уровень 0: Контекстная диаграмма системы
• Уровень 1: 3 основных процесса, 5 хранилищ данных
• Уровень 2: Детализация процессов движения товаров
• 3 внешние сущности: Поставщики, Покупатели, Бухгалтерия
• Выявлены критичные потоки данных для интеграции с 1С`;
            }
            // Диаграммы деятельности (Activity Diagrams)
            else if (queryLower.includes('activity') || queryLower.includes('деятельность') || queryLower.includes('uml activity')) {
                analysis = {
                    activities: [
                        {
                            name: 'Процесс приемки товара',
                            swimlanes: ['Кладовщик', 'Система 1С'],
                            actions: [
                                'Получить товар и документы',
                                'Проверить соответствие заказу',
                                'Зарегистрировать в 1С',
                                'Разместить на складе',
                                'Обновить остатки'
                            ],
                            decisions: ['Соответствует заказу?', 'Товар есть в базе?'],
                            parallelFlows: ['Проверка качества', 'Документооборот'],
                            timeEstimate: '30 минут'
                        }
                    ],
                    totalActivities: 6,
                    avgExecutionTime: '25 минут',
                    parallelizableTasks: 40
                };
                customMessage = `Диаграммы деятельности (Activity): "${userQuery}"

Смоделированы процессы с учетом параллельности:
• 6 основных процессов с ролевым разделением
• Выявлено 40% задач для параллельного выполнения
• Среднее время выполнения: 25 минут
• Интеграция с дорожками (swimlanes) для 1С
• Оптимизация через параллельные потоки контроля качества`;
            }
            // Диаграммы классов
            else if (queryLower.includes('class') || queryLower.includes('класс') || queryLower.includes('uml class')) {
                analysis = {
                    classes: [
                        {
                            name: 'Товар',
                            attributes: ['id', 'наименование', 'артикул', 'цена', 'едИзмерения'],
                            methods: ['создать()', 'обновить()', 'удалить()', 'получитьОстаток()']
                        },
                        {
                            name: 'ДокументДвижения',
                            attributes: ['id', 'тип', 'дата', 'номер', 'проведен'],
                            methods: ['провести()', 'отменить()', 'получитьСтроки()']
                        },
                        {
                            name: 'Склад',
                            attributes: ['id', 'наименование', 'адрес', 'ответственный'],
                            methods: ['получитьОстатки()', 'переместить()', 'инвентаризировать()']
                        }
                    ],
                    relationships: [
                        { type: 'Ассоциация', from: 'ДокументДвижения', to: 'Товар', cardinality: '1..*' },
                        { type: 'Ассоциация', from: 'Склад', to: 'Товар', cardinality: '1..*' },
                        { type: 'Наследование', from: 'ПриходнаяНакладная', to: 'ДокументДвижения' }
                    ],
                    totalClasses: 15,
                    complexity: 'Средняя'
                };
                customMessage = `Диаграммы классов (UML): "${userQuery}"

Спроектирована объектная модель:
• 15 классов с полной атрибутикой и методами
• 3 основных класса: Товар, ДокументДвижения, Склад
• Определены связи: ассоциации, агрегации, наследование
• Готово для генерации кода 1С и базы данных
• Поддержка принципов ООП и паттернов проектирования`;
            }
            // Анализ заинтересованных лиц
            else if (queryLower.includes('stakeholder') || queryLower.includes('стейкхолдер') || queryLower.includes('заинтересованн')) {
                analysis = {
                    stakeholders: [
                        {
                            name: 'Кладовщик',
                            role: 'Операционный пользователь',
                            interests: ['Удобство работы', 'Скорость операций'],
                            influence: 'Высокий', expectation: 'Автоматизация рутинных операций',
                            communication: 'Еженедельные демо, обучение'
                        },
                        {
                            name: 'Менеджер по закупкам',
                            role: 'Бизнес-пользователь',
                            interests: ['Точность данных', 'Отчетность'],
                            influence: 'Высокий', expectation: 'Аналитика и прогнозирование',
                            communication: 'Ежедневные отчеты, BI-панели'
                        },
                        {
                            name: 'Бухгалтер',
                            role: 'Финансовый пользователь',
                            interests: ['Соответствие стандартам', 'Документооборот'],
                            influence: 'Средний', expectation: 'Интеграция с 1С:Бухгалтерия',
                            communication: 'Месячные отчеты, аудит процессов'
                        }
                    ],
                    powerInterestMatrix: {
                        highPowerHighInterest: ['Кладовщик', 'Менеджер по закупкам'],
                        highPowerLowInterest: ['Директор'],
                        lowPowerHighInterest: ['Бухгалтер'],
                        lowPowerLowInterest: ['Служба поддержки']
                    },
                    communicationPlan: 'Детализированный план коммуникаций по каждой группе'
                };
                customMessage = `Анализ заинтересованных лиц (Stakeholders): "${userQuery}"

Выявлено и проанализировано 12 стейкхолдеров:
• 3 группы с высоким влиянием и интересом (приоритетные)
• Построена матрица влияние/интерес для управления
• Разработан план коммуникаций для каждой роли
• Учтены интересы операционных, бизнес и финансовых пользователей
• Готово для проведения воркшопов и демонстраций`;
            }
            // Оценка и анализ процессов
            else if (queryLower.includes('оценка') || queryLower.includes('метрика') || queryLower.includes('kpi') || queryLower.includes('анализ эффективн')) {
                analysis = {
                    processMetrics: [
                        {
                            process: 'Приемка товаров',
                            time: '25 мин', cost: '500 руб', quality: '95%', automation: '70%',
                            kpi: ['Время выполнения', 'Процент ошибок', 'Стоимость операции']
                        },
                        {
                            process: 'Размещение товаров',
                            time: '45 мин', cost: '800 руб', quality: '88%', automation: '40%',
                            kpi: ['Использование площади', 'Точность размещения']
                        }
                    ],
                    benchmarks: {
                        industryAverage: { time: '30 мин', cost: '600 руб', quality: '90%' },
                        bestPractice: { time: '20 мин', cost: '400 руб', quality: '98%' }
                    },
                    recommendations: [
                        'Автоматизировать сканирование штрих-кодов',
                        'Оптимизировать маршруты размещения',
                        'Внедрить предиктивную аналитику'
                    ],
                    roi: { estimated: '150%', paybackPeriod: '8 месяцев' }
                };
                customMessage = `Оценка процессов и KPI: "${userQuery}"

Проанализированы ключевые метрики процессов:
• Время выполнения: 25-45 мин (при норме 30 мин)
• Качество операций: 88-95% (при норме 90%)
• Автоматизация: 40-70% (цель: 85%)
• ROI проекта: 150%, окупаемость: 8 месяцев
• Рекомендации: автоматизация сканирования и оптимизация маршрутов`;
            }
            // Оптимизация бизнес-процессов
            else if (queryLower.includes('оптимизац') || queryLower.includes('improve') || queryLower.includes('lean') || queryLower.includes('kaizen')) {
                analysis = {
                    currentState: {
                        totalTime: '5ч 45мин/день', manualSteps: 15, errorRate: '12%',
                        bottlenecks: ['Инвентаризация (4 часа)', 'Поиск товаров (45 мин/день)']
                    },
                    optimizedState: {
                        totalTime: '3ч 20мин/день', manualSteps: 6, errorRate: '3%',
                        improvements: 'Автоматизация, RFID, AI-поиск'
                    },
                    optimization: [
                        { area: 'Инвентаризация', current: '4 часа', optimized: '45 мин', method: 'RFID + автоматический учет' },
                        { area: 'Поиск товаров', current: '45 мин/день', optimized: '5 мин/день', method: 'AI-навигация' },
                        { area: 'Документооборот', current: '30 мин/операция', optimized: '5 мин/операция', method: 'Электронный документооборот' }
                    ],
                    timeline: '3 этапа по 2 месяца',
                    expectedGain: '42% сокращение времени, 75% сокращение ошибок'
                };
                customMessage = `Оптимизация бизнес-процессов: "${userQuery}"

Разработана дорожная карта оптимизации:
• Текущее состояние: 5ч 45мин/день, 15 ручных шагов, 12% ошибок
• Целевое состояние: 3ч 20мин/день, 6 ручных шагов, 3% ошибок
• Ключевые улучшения: RFID-инвентаризация, AI-навигация, ЭДО
• 3-этапный план внедрения по 2 месяца
• Ожидаемый эффект: 42% экономии времени, 75% сокращение ошибок`;
            }
            // Автоматизация
            else if (queryLower.includes('автоматизац') || queryLower.includes('automation') || queryLower.includes('бот') || queryLower.includes('робот')) {
                analysis = {
                    automation: {
                        currentLevel: '45%', targetLevel: '85%',
                        candidates: [
                            {
                                process: 'Инвентаризация',
                                automationType: 'RFID + AI',
                                effort: 'Высокий',
                                impact: 'Критичный',
                                roi: '300%'
                            },
                            {
                                process: 'Заказ товаров',
                                automationType: 'Правила + ML',
                                effort: 'Средний',
                                impact: 'Высокий',
                                roi: '200%'
                            }
                        ],
                        technologies: ['RPA', 'AI/ML', 'API интеграция', 'Workflow engine']
                    },
                    roadmap: [
                        { phase: 'Фаза 1', duration: '3 мес', focus: 'Документооборот, уведомления' },
                        { phase: 'Фаза 2', duration: '4 мес', focus: 'RFID, автоматический учет' },
                        { phase: 'Фаза 3', duration: '3 мес', focus: 'AI-аналитика, предикция' }
                    ]
                };
                customMessage = `Стратегия автоматизации: "${userQuery}"

Текущий уровень: 45% → Целевой уровень: 85%
• Приоритетные процессы: инвентаризация (ROI 300%), заказы (ROI 200%)
• Технологии: RPA, AI/ML, API, Workflow engine
• Дорожная карта: 3 фазы по 3-4 месяца
• Ожидаемый эффект: сокращение FTE на 2.5 единицы
• Инвестиции окупятся за 10 месяцев`;
            }
            // Цифровизация
            else if (queryLower.includes('цифровизац') || queryLower.includes('digital') || queryLower.includes('трансформац') || queryLower.includes('индустр 4.0')) {
                analysis = {
                    digitalMaturity: {
                        current: 'Уровень 2 (Базовый)', target: 'Уровень 4 (Оптимизированный)',
                        gap: '2 уровня'
                    },
                    initiatives: [
                        {
                            area: 'IoT и датчики',
                            description: 'Умные датчики влажности, температуры, движения',
                            benefits: 'Контроль условий хранения, безопасность',
                            investment: '2 млн руб', timeline: '6 мес'
                        },
                        {
                            area: 'AI и аналитика',
                            description: 'Предиктивная аналитика спроса, оптимизация запасов',
                            benefits: 'Сокращение излишков на 30%, улучшение сервиса',
                            investment: '1.5 млн руб', timeline: '4 мес'
                        },
                        {
                            area: 'Мобильные приложения',
                            description: 'Мобильный доступ к данным, сканирование, навигация',
                            benefits: 'Мобильность персонала, скорость операций',
                            investment: '800 тыс руб', timeline: '3 мес'
                        }
                    ],
                    transformation: {
                        totalInvestment: '4.3 млн руб',
                        expectedROI: '180%',
                        digitalBenefits: [
                            'Реальное время данных',
                            'Предиктивное обслуживание',
                            'Автоматизированные решения'
                        ]
                    }
                };
                customMessage = `Цифровая трансформация: "${userQuery}"

Текущий уровень зрелости: 2/5 → Целевой: 4/5
• 3 стратегические инициативы с общим бюджетом 4.3 млн руб
• IoT: умные датчики для контроля условий (ROI 250%)
• AI: предиктивная аналитика запасов (сокращение излишков 30%)
• Mobile: мобильный доступ и навигация (ускорение операций 40%)
• Ожидаемый ROI: 180% за 18 месяцев`;
            }
            // Документооборот
            else if (queryLower.includes('документооборот') || queryLower.includes('edms') || queryLower.includes('эдо') || queryLower.includes('electronic document')) {
                analysis = {
                    edms: {
                        currentState: 'Бумажный документооборот',
                        targetState: 'Полностью электронный',
                        coverage: {
                            contracts: '30%', invoices: '60%', acts: '20%', reports: '80%'
                        }
                    },
                    documents: [
                        {
                            type: 'Договоры с поставщиками',
                            format: 'PDF + ЭЦП',
                            workflow: 'Создание → Согласование → Подписание → Архив',
                            automation: '80%',
                            integration: '1С + ЭДО операторы'
                        },
                        {
                            type: 'Накладные ТОРГ-12',
                            format: 'EDI',
                            workflow: 'Получение → Проверка → Проводка в 1С',
                            automation: '95%',
                            integration: '1С:EDI'
                        },
                        {
                            type: 'Акты выполненных работ',
                            format: 'XML + ЭЦП',
                            workflow: 'Создание → Отправка → Подтверждение → Оплата',
                            automation: '70%',
                            integration: '1С + Банк'
                        }
                    ],
                    benefits: {
                        timeSaving: '70% сокращение времени обработки',
                        costReduction: '60% экономия на печати и хранении',
                        errorReduction: '85% сокращение ошибок ввода'
                    },
                    timeline: '4 этапа по 1.5 месяца'
                };
                customMessage = `Система электронного документооборота: "${userQuery}"

Текущее покрытие: 30-80% → Целевое: 95%
• 3 типа документов: договоры, накладные, акты
• Интеграция с 1С и ЭДО-операторами
• Автоматизация процессов: 70-95%
• Ожидаемые эффекты: 70% экономия времени, 85% меньше ошибок
• Поэтапный план внедрения за 6 месяцев`;
            }
            // Workflow
            else if (queryLower.includes('workflow') || queryLower.includes('процессный подход') || queryLower.includes('bpms') || queryLower.includes('маршрутизац')) {
                analysis = {
                    workflow: {
                        engine: 'Camunda/BPMN 2.0',
                        processes: [
                            {
                                name: 'Согласование заказа',
                                steps: 5, participants: ['Менеджер', 'Кладовщик', 'Бухгалтер'],
                                sla: '2 часа',
                                automation: '80%'
                            },
                            {
                                name: 'Утверждение закупки',
                                steps: 4, participants: ['Руководитель', 'Финансы'],
                                sla: '4 часа',
                                automation: '60%'
                            }
                        ]
                    },
                    capabilities: [
                        'Параллельное и последовательное согласование',
                        'Автоматические уведомления и эскалации',
                        'SLA-мониторинг и отчетность',
                        'Интеграция с 1С через API'
                    ],
                    integration: {
                        systems: ['1С:Предприятие', 'ERP', 'CRM', 'DMS'],
                        apis: 'REST/SOAP с аутентификацией'
                    },
                    benefits: [
                        'Прозрачность процессов согласования',
                        'Сокращение времени на 50%',
                        'Соответствие требованиям compliance'
                    ]
                };
                customMessage = `Система управления процессами (Workflow): "${userQuery}"

Внедрение BPMN-движка с интеграцией 1С:
• 2 критичных процесса: согласование заказа (2ч), закупки (4ч)
• Участники: менеджеры, кладовщики, бухгалтерия, руководство
• Автоматизация: 60-80% с автоматическими уведомлениями
• Интеграция: 1С, ERP, CRM через REST API
• Эффекты: 50% сокращение времени, полная прозрачность`;
            }
            // Документы и спецификации
            else if (queryLower.includes('документ') || queryLower.includes('document') || queryLower.includes('спецификац') || queryLower.includes('тз') || queryLower.includes('техническ')) {
                analysis = {
                    documents: [
                        { name: 'Бизнес-требования (BRD)', status: 'создан', pages: 45, version: 'v1.2', owner: 'БА' },
                        { name: 'Техническое задание (ТЗ)', status: 'создан', pages: 67, version: 'v1.0', owner: 'Архитектор' },
                        { name: 'User Stories + Acceptance Criteria', status: 'создан', pages: 23, version: 'v1.1', owner: 'ПМ' },
                        { name: 'API Спецификация (OpenAPI)', status: 'в процессе', pages: 34, version: 'v0.9', owner: 'Разработчик' },
                        { name: 'Архитектурные диаграммы', status: 'создан', pages: 12, version: 'v1.0', owner: 'Архитектор' },
                        { name: 'Тест-кейсы и Test Plan', status: 'в процессе', pages: 28, version: 'v0.8', owner: 'Тестировщик' }
                    ],
                    documentation: {
                        totalPages: 209,
                        completed: '75%',
                        inProgress: '25%',
                        readyForReview: 5
                    },
                    standards: ['ГОСТ 34 серии', 'IEEE 830', 'Agile практики']
                };
                customMessage = `Проектная документация: "${userQuery}"

Создано 6 ключевых документов общим объемом 209 страниц:
• Готовность документации: 75% (5 документов готовы к ревью)
• Бизнес-требования (45 стр., v1.2) - утверждены заказчиком
• ТЗ (67 стр., v1.0) - готово к передаче в разработку
• User Stories (23 стр.) - полный покрытие функций с критериями
• Стандарты: ГОСТ 34, IEEE 830, Agile практики
• API и тест-кейсы в процессе завершения`;
            }
            // Диаграммы общие
            else if (queryLower.includes('диаграмм') || queryLower.includes('bpmn') || queryLower.includes('uml') || queryLower.includes('модель')) {
                analysis = {
                    diagrams: [
                        { type: 'BPMN 2.0', count: 8, description: 'Бизнес-процессы и workflow', quality: 'Production ready' },
                        { type: 'UML Use Case', count: 15, description: 'Сценарии использования', quality: 'Validated' },
                        { type: 'UML Class', count: 12, description: 'Объектная модель данных', quality: 'Implementation ready' },
                        { type: 'DFD (Data Flow)', count: 6, description: 'Потоки данных', quality: 'Consistent' },
                        { type: 'ERD (Entity-Relationship)', count: 4, description: 'Структура БД', quality: 'Normalized' },
                        { type: 'Activity Diagrams', count: 10, description: 'Процессы деятельности', quality: 'Detailed' }
                    ],
                    totalDiagrams: 55,
                    tools: ['Enterprise Architect', 'draw.io', 'PlantUML'],
                    quality: 'Все диаграммы валидированы со стейкхолдерами',
                    traceability: 'Полная трассируемость между всеми видами диаграмм'
                };
                customMessage = `Архитектурные и аналитические диаграммы: "${userQuery}"

Создано 55 диаграмм 6 типов:
• BPMN: 8 диаграмм бизнес-процессов (готовы к внедрению)
• UML Use Case: 15 сценариев (валидированы с пользователями)
• UML Class: 12 диаграмм (готовы к генерации кода)
• DFD: 6 диаграмм потоков данных (консистентны)
• ERD: 4 диаграммы БД (нормализованы)
• Activity: 10 процессов деятельности (детализированы)
• Инструменты: EA, draw.io, PlantUML - полная трассируемость`;
            }
            // Интеграция и совместимость
            else if (queryLower.includes('интеграц') || queryLower.includes('integration') || queryLower.includes('api') || queryLower.includes('обмен данн')) {
                analysis = {
                    integration: {
                        systems: [
                            { name: '1С:Предприятие 8.3', type: 'Core', method: 'Прямая интеграция', status: 'Обязательно' },
                            { name: '1С:Бухгалтерия', type: 'Financial', method: 'Обмен через COM', status: 'Требуется' },
                            { name: 'WMS система', type: 'Warehouse', method: 'REST API', status: 'Рекомендуется' },
                            { name: 'CRM система', type: 'Sales', method: 'SOAP веб-сервисы', status: 'Опционально' }
                        ],
                        protocols: ['REST API', 'SOAP', 'OData', 'COM-подключение', 'File exchange'],
                        dataMapping: {
                            products: 'Полное соответствие справочников номенклатуры',
                            documents: 'Синхронизация документов движения',
                            users: 'Единая авторизация через LDAP'
                        }
                    },
                    compatibility: {
                        versions: ['1С 8.3.15+', 'MS SQL Server 2016+', 'Windows Server 2019+'],
                        browsers: ['Chrome 80+', 'Firefox 75+', 'Edge 80+'],
                        mobile: 'iOS 13+, Android 8+'
                    },
                    apis: [
                        { name: 'Products API', endpoints: 12, method: 'REST/JSON', authentication: 'OAuth 2.0' },
                        { name: 'Documents API', endpoints: 8, method: 'REST/XML', authentication: 'API Key' },
                        { name: 'Reports API', endpoints: 6, method: 'OData', authentication: 'Windows Auth' }
                    ]
                };
                customMessage = `Интеграция с 1С и внешними системами: "${userQuery}"

Проанализированы интеграционные требования:
• 4 системы для интеграции: 1С (обязательно), WMS, CRM (опционально)
• Протоколы: REST API, SOAP, OData, COM-подключение
• 26 REST endpoints с аутентификацией OAuth 2.0 и API Key
• Совместимость: 1С 8.3.15+, SQL Server 2016+, браузеры Chrome/Firefox/Edge
• Полное соответствие справочников и синхронизация документов`;
            }
            // Безопасность и соответствие
            else if (queryLower.includes('безопасность') || queryLower.includes('security') || queryLower.includes('rgpd') || queryLower.includes('соответствие') || queryLower.includes('compliance')) {
                analysis = {
                    security: {
                        authentication: {
                            methods: ['LDAP/Active Directory', 'OAuth 2.0', 'Двухфакторная аутентификация'],
                            passwordPolicy: 'Минимум 8 символов, спецсимволы, смена каждые 90 дней',
                            session: 'Таймаут 30 мин, принудительный logout'
                        },
                        authorization: {
                            model: 'RBAC (Role-Based Access Control)',
                            roles: ['Администратор', 'Менеджер', 'Кладовщик', 'Бухгалтер', 'Гость'],
                            permissions: 'Принцип минимальных привилегий'
                        },
                        audit: {
                            logging: 'Все операции пользователей с timestamp',
                            monitoring: 'Real-time мониторинг подозрительной активности',
                            retention: 'Логи хранятся 7 лет'
                        },
                        encryption: {
                            dataAtRest: 'AES-256 для базы данных',
                            dataInTransit: 'TLS 1.3 для всех соединений',
                            backups: 'Шифрование резервных копий'
                        }
                    },
                    compliance: {
                        standards: ['ГОСТ Р ИСО/МЭК 27001', 'GDPR', '152-ФЗ «О персональных данных»'],
                        auditReadiness: 'Полная документация процессов безопасности',
                        regularAudits: 'Квартальные аудиты безопасности'
                    }
                };
                customMessage = `Обеспечение безопасности и соответствия: "${userQuery}"

Разработана комплексная стратегия безопасности:
• Аутентификация: AD, OAuth 2.0, 2FA с политикой паролей
• Авторизация: RBAC с 5 ролями по принципу минимальных привилегий
• Аудит: полное логирование с retention 7 лет, real-time мониторинг
• Шифрование: AES-256 (данные), TLS 1.3 (передача), зашифрованные бэкапы
• Соответствие: ГОСТ 27001, GDPR, 152-ФЗ с квартальными аудитами`;
            }
            // Производительность и масштабируемость
            else if (queryLower.includes('производительность') || queryLower.includes('performance') || queryLower.includes('масштабируем') || queryLower.includes('scalability') || queryLower.includes('нагрузка')) {
                analysis = {
                    performance: {
                        requirements: {
                            responseTime: '95% запросов < 2 сек, 99% < 5 сек',
                            throughput: '1000 пользователей онлайн, 10000 операций/час',
                            availability: '99.9% uptime (8.76 часов downtime/год)',
                            dataVolume: 'Поддержка до 1 млн товаров, 10 млн документов'
                        },
                        optimization: {
                            database: 'Индексы на частые запросы, партиционирование таблиц',
                            caching: 'Redis для сессий, Memcached для справочников',
                            loadBalancing: 'NGINX для распределения нагрузки',
                            asyncProcessing: 'Очереди для длительных операций'
                        },
                        monitoring: {
                            metrics: ['CPU', 'Memory', 'Disk I/O', 'Database connections'],
                            alerts: 'Автоматические уведомления при превышении порогов',
                            dashboards: 'Real-time мониторинг в Grafana'
                        }
                    },
                    scalability: {
                        horizontal: 'Auto-scaling групп серверов, контейнеризация (Docker)',
                        vertical: 'Возможность увеличения ресурсов до 64 CPU, 256 GB RAM',
                        database: 'Read replicas для отчетов, sharding по периодам',
                        cdn: 'CDN для статических ресурсов и отчетов'
                    },
                    capacity: {
                        current: '500 пользователей, 500K товаров, 1M документов',
                        target: '1000 пользователей, 1M товаров, 10M документов',
                        growth: 'Планирование на 3 года с 20% ростом в год'
                    }
                };
                customMessage = `Производительность и масштабируемость: "${userQuery}"

Целевые показатели производительности:
• Время отклика: 95% запросов < 2 сек, доступность 99.9%
• Нагрузка: 1000 онлайн-пользователей, 10K операций/час
• Объем данных: до 1M товаров, 10M документов с ростом 20%/год
• Оптимизация: индексы БД, Redis/Memcached, NGINX, асинхронные очереди
• Мониторинг: автоматические алерты, Grafana dashboards
• Масштабирование: горизонтальное (Docker, auto-scaling), вертикальное до 64 CPU`;
            }
            // Аналитика и отчетность
            else if (queryLower.includes('аналитика') || queryLower.includes('analytics') || queryLower.includes('bi') || queryLower.includes('отчет') || queryLower.includes('dashboard') || queryLower.includes('kpi')) {
                analysis = {
                    analytics: {
                        dataWarehouse: {
                            source: '1С + внешние системы',
                            etl: 'Автоматическая загрузка каждые 15 минут',
                            storage: 'MS SQL Server с OLAP кубами',
                            history: 'Полная история за 5 лет с агрегатами'
                        },
                        dashboards: [
                            { name: 'Операционный дашборд', users: 'Менеджеры', refresh: 'Real-time', kpis: ['Остатки', 'Движения', 'Продажи'] },
                            { name: 'Финансовый дашборд', users: 'Финансы', refresh: 'День', kpis: ['Прибыль', 'Затраты', 'ROI'] },
                            { name: 'Складской дашборд', users: 'Кладовщики', refresh: 'Час', kpis: ['Загрузка', 'Тurnover', 'Accuracy'] }
                        ],
                        reports: {
                            operational: ['Остатки товаров', 'Движения за период', 'ABC-анализ', 'Скорость оборота'],
                            financial: ['Прибыльность товаров', 'Затраты на склад', 'ROI проектов', 'Бюджет vs факт'],
                            predictive: ['Прогноз спроса', 'Потребность в закупках', 'Оптимальные партии', 'Сезонность']
                        }
                    },
                    biTools: {
                        primary: 'Power BI / Tableau',
                        selfService: 'Пользовательские отчеты без программирования',
                        mobile: 'Мобильные приложения для iOS/Android',
                        alerts: 'Автоматические уведомления при отклонениях KPI'
                    },
                    dataQuality: {
                        completeness: '99.5% заполненность критичных полей',
                        accuracy: 'Автоматическая валидация данных при загрузке',
                        consistency: 'Контроль целостности между системами'
                    }
                };
                customMessage = `Система аналитики и BI: "${userQuery}"

Построена комплексная аналитическая платформа:
• Data Warehouse: автоматический ETL из 1С каждые 15 минут, история 5 лет
• 3 типа дашбордов: операционный (real-time), финансовый (дневной), складской (часовой)
• Отчеты: операционные, финансовые, предиктивные (прогноз спроса, закупки)
• BI-инструменты: Power BI/Tableau, self-service отчеты, мобильные приложения
• Качество данных: 99.5% полнота, автоматическая валидация, контроль целостности`;
            }
            // Тестирование и качество
            else if (queryLower.includes('тестирование') || queryLower.includes('testing') || queryLower.includes('qa') || queryLower.includes('quality') || queryLower.includes('качество')) {
                analysis = {
                    testing: {
                        strategy: 'Пирамида тестирования с автоматизацией',
                        types: [
                            { type: 'Unit Tests', coverage: '90%', tool: 'xUnit для 1С', automation: '100%' },
                            { type: 'Integration Tests', coverage: '80%', tool: 'Selenide + 1С', automation: '80%' },
                            { type: 'UI Tests', coverage: '70%', tool: 'Selenium WebDriver', automation: '60%' },
                            { type: 'API Tests', coverage: '85%', tool: 'Postman/Newman', automation: '90%' },
                            { type: 'Performance Tests', coverage: 'Критичные сценарии', tool: 'JMeter', automation: '100%' }
                        ],
                        environments: ['Dev', 'Test', 'Staging', 'Production'],
                        continuousIntegration: 'Jenkins с автозапуском тестов при коммите'
                    },
                    quality: {
                        codeQuality: 'SonarQube с правилами для 1С и C#',
                        securityScanning: 'Автоматическая проверка уязвимостей',
                        documentation: 'Автогенерация документации из кода (Swagger)',
                        reviews: 'Обязательный code review для всех PR'
                    },
                    metrics: {
                        testCoverage: '85% общий покрытие кода',
                        defectDensity: 'Не более 1 дефекта на 1000 строк кода',
                        meanTimeToRecovery: 'MTTR < 4 часа для критичных дефектов',
                        customerSatisfaction: 'CSAT > 4.5 из 5'
                    },
                    process: {
                        testPlan: 'Детальный план тестирования для каждого релиза',
                        testData: 'Анонимизированные данные prod-качества',
                        bugTracking: 'Jira с интеграцией с Git и CI/CD'
                    }
                };
                customMessage = `Стратегия тестирования и обеспечения качества: "${userQuery}"

Внедрена пирамида тестирования с автоматизацией:
• Покрытие тестами: Unit (90%), Integration (80%), UI (70%), API (85%)
• Инструменты: xUnit (1С), Selenium, Postman, JMeter, SonarQube
• CI/CD: Jenkins с автозапуском тестов при каждом коммите
• Метрики: 85% покрытие, <1 дефекта/1000 строк, MTTR <4 часа
• Процесс: обязательный code review, автогенерация документации
• Качество: анонимизированные данные, отслеживание дефектов в Jira`;
            }
            // По умолчанию - общий анализ
            else {
                analysis = {
                    stakeholders: ['Менеджеры', 'Кладовщики', 'Бухгалтерия', 'IT-отдел'],
                    goals: [
                        'Повышение эффективности склада на 40%',
                        'Сокращение ошибок учета на 75%',
                        'Улучшение отчетности и аналитики',
                        'Интеграция с существующей 1С'
                    ],
                    constraints: ['Бюджет 5 млн руб', 'Сроки 6 месяцев', 'Совместимость с 1С 8.3', 'Обучение персонала'],
                    successCriteria: [
                        'Сокращение времени операций на 40%',
                        'Увеличение точности учета до 99%',
                        'ROI не менее 150% за 12 месяцев'
                    ]
                };
                customMessage = `Бизнес-анализ: "${userQuery}"

Выявлены ключевые аспекты проекта:
• 4 группы стейкхолдеров с различными потребностями и интересами
• 4 бизнес-цели: эффективность (+40%), качество (+75%), аналитика, интеграция
• 4 основных ограничения: бюджет, сроки, совместимость, обучение
• 3 критерия успеха с измеримыми показателями эффективности
• Рекомендуется поэтапный подход с приоритизацией высокоэффективных улучшений`;
            }
            
            finalResult = {
                message: customMessage,
                analysis: analysis,
                userQuery: sanitizedUserQuery || userQuery,
                timestamp: new Date().toISOString(),
                analysisType: 'Расширенный бизнес-анализ для 1С'
            };
            
            steps.push({ 
                progress: 100, 
                message: 'Анализ успешно завершен!',
                result: finalResult
            });
            
        } else if (demoType === 'requirements') {
            steps.push({ progress: 10, message: 'Запуск извлечения требований...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Загрузка и парсинг документов...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 45, message: 'Категоризация требований...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 65, message: 'Извлечение требований с помощью NLP...' });
            await new Promise(r => setTimeout(r, 1100));
            
            steps.push({ progress: 90, message: 'Структурирование и категоризация...' });
            await new Promise(r => setTimeout(r, 700));
            
            const requirements = {
                functional: [
                    {
                        id: 'FR-001',
                        title: 'Учет товаров на складе',
                        description: 'Система должна вести учет товаров с возможностью отслеживания остатков',
                        priority: 'Высокий',
                        source: 'Бизнес-требования.docx, стр. 3'
                    },
                    {
                        id: 'FR-002',
                        title: 'Формирование отчетов',
                        description: 'Возможность создания отчетов по остаткам, движению товаров',
                        priority: 'Средний',
                        source: 'Бизнес-требования.docx, стр. 5'
                    }
                ],
                nonFunctional: [
                    {
                        id: 'NFR-001',
                        title: 'Производительность',
                        description: 'Время отклика системы не должно превышать 2 секунд',
                        priority: 'Высокий',
                        source: 'Технические требования.docx, стр. 2'
                    },
                    {
                        id: 'NFR-002',
                        title: 'Доступность',
                        description: 'Система должна быть доступна 24/7 с uptime 99.5%',
                        priority: 'Высокий',
                        source: 'Технические требования.docx, стр. 4'
                    }
                ]
            };
            
            finalResult = {
                requirements,
                totalExtracted: 45,
                functionalCount: 28,
                nonFunctionalCount: 17,
                confidence: 0.92,
                extractionMethod: 'NLP + машинное обучение',
                qualityScore: 'A',
                readyForDevelopment: true,
                traceabilityMatrix: 'Полная трассируемость от требований к тестам',
                timestamp: new Date().toISOString()
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Извлечено 45 требований: 28 функциональных, 17 нефункциональных',
                result: finalResult
            });
            
        } else if (demoType === 'process') {
            steps.push({ progress: 10, message: 'Запуск моделирования процесса...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Анализ бизнес-процесса...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 50, message: 'Выявление точек принятия решений...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 70, message: 'Создание BPMN диаграммы...' });
            await new Promise(r => setTimeout(r, 1000));
            
            const bpmnDiagram = `
graph TD
    Start([Начало: Поступление товара]) --> Check{Товар<br/>в системе?}
    Check -->|Да| GetInfo[Получить<br/>информацию о товаре]
    Check -->|Нет| CreateNew[Создать новый<br/>товар в справочнике]
    CreateNew --> GetInfo
    GetInfo --> CreateDoc[Создать документ<br/>Приход товара]
    CreateDoc --> FillDetails[Заполнить<br/>детали документа]
    FillDetails --> Validate{Проверка<br/>корректности}
    Validate -->|Ошибки| FixErrors[Исправить ошибки]
    FixErrors --> FillDetails
    Validate -->|OK| Post[Провести документ]
    Post --> UpdateStock[Обновить остатки<br/>на складе]
    UpdateStock --> Notify[Отправить<br/>уведомление]
    Notify --> End([Конец])
`;
            
            finalResult = {
                diagram: bpmnDiagram,
                processName: 'Приход товара на склад',
                steps: 8,
                decisionPoints: 3,
                averageTime: '15 минут',
                participants: ['Кладовщик', 'Система'],
                processMetrics: {
                    efficiency: '85%',
                    bottleneck: 'Проверка корректности данных',
                    automationLevel: '70%',
                    errorRate: '5%'
                },
                improvements: [
                    'Автоматическая валидация данных',
                    'Интеграция с системой качества',
                    'RFID для автоматического учета'
                ],
                bpmnVersion: '2.0',
                isoCompliance: 'ISO 9001:2015',
                timestamp: new Date().toISOString()
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Процесс смоделирован: 8 шагов, 3 точки принятия решений',
                result: finalResult
            });
            
        } else if (demoType === 'advanced') {
            steps.push({ progress: 10, message: 'Запуск расширенного бизнес-анализа...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 25, message: 'Анализ доменной области...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 50, message: 'Построение архитектурной модели...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 75, message: 'Создание технической документации...' });
            await new Promise(r => setTimeout(r, 800));
            
            const advancedAnalysis = {
                domainModel: {
                    entities: ['Товар', 'Склад', 'Документ', 'Пользователь', 'Процесс'],
                    relationships: ['Ассоциация', 'Наследование', 'Агрегация', 'Композиция'],
                    businessRules: [
                        'Остаток товара не может быть отрицательным',
                        'Документ должен быть проведен для изменения остатков',
                        'Доступ к данным определяется ролью пользователя'
                    ]
                },
                architecture: {
                    type: 'Многослойная архитектура',
                    layers: [
                        { name: 'Presentation Layer', technology: '1С Forms, Web-interface', responsibility: 'Пользовательский интерфейс' },
                        { name: 'Business Logic Layer', technology: '1С Modules, C#', responsibility: 'Бизнес-логика' },
                        { name: 'Data Access Layer', technology: '1С Database, SQL', responsibility: 'Доступ к данным' },
                        { name: 'Integration Layer', technology: 'REST API, SOAP', responsibility: 'Интеграция с внешними системами' }
                    ],
                    patterns: ['MVC', 'Repository', 'Service Layer', 'API Gateway']
                },
                integration: {
                    systems: ['1С:Предприятие 8.3', 'ERP система', 'WMS', 'CRM'],
                    protocols: ['OData', 'REST API', 'File exchange', 'Database replication'],
                    dataMapping: 'Полное соответствие справочников и регистров'
                },
                security: {
                    authentication: 'Аутентификация через Active Directory',
                    authorization: 'Ролевая модель доступа (RBAC)',
                    audit: 'Полное логирование всех операций',
                    encryption: 'Шифрование данных в покое и в передаче'
                },
                performance: {
                    requirements: 'Время отклика < 2 сек для 95% запросов',
                    scalability: 'Поддержка до 1000 одновременных пользователей',
                    optimization: 'Индексы БД, кэширование, асинхронная обработка'
                }
            };
            
            finalResult = {
                advancedAnalysis,
                deliverables: [
                    'Архитектурная модель системы',
                    'Техническая спецификация интеграций',
                    'План обеспечения безопасности',
                    'Требования к производительности',
                    'Руководство по развертыванию'
                ],
                confidence: 0.94
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Расширенный анализ завершен: архитектура, интеграции, безопасность',
                result: finalResult
            });

        } else if (demoType === 'stories') {
            steps.push({ progress: 10, message: 'Запуск генерации историй...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 25, message: 'Анализ требований...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 45, message: 'Извлечение ролей пользователей...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 60, message: 'Генерация User Stories...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 85, message: 'Добавление критериев приемки...' });
            await new Promise(r => setTimeout(r, 800));
            
            const userStories = [
                {
                    id: 'US-001',
                    title: 'Добавление товара в систему',
                    asA: 'Кладовщик',
                    iWant: 'иметь возможность добавлять новые товары в систему',
                    soThat: 'вести учет всех товаров на складе',
                    acceptanceCriteria: [
                        'Форма создания товара содержит поля: наименование, артикул, цена, единица измерения',
                        'Артикул генерируется автоматически, если не заполнен',
                        'При сохранении выполняется валидация обязательных полей',
                        'После сохранения товар отображается в справочнике'
                    ],
                    priority: 'Высокий',
                    estimation: '5 SP'
                },
                {
                    id: 'US-002',
                    title: 'Просмотр остатков товаров',
                    asA: 'Менеджер',
                    iWant: 'видеть актуальные остатки товаров на складе',
                    soThat: 'принимать решения о закупках',
                    acceptanceCriteria: [
                        'Отчет показывает наименование, артикул, количество',
                        'Есть фильтр по складу',
                        'Данные обновляются в реальном времени',
                        'Можно экспортировать в Excel'
                    ],
                    priority: 'Средний',
                    estimation: '3 SP'
                }
            ];
            
            finalResult = {
                userStories,
                totalStories: 23,
                withAcceptanceCriteria: 23,
                avgStoryPoints: 4.2,
                totalStoryPoints: 97,
                storyQuality: {
                    wellFormed: '95%',
                    estimable: '100%',
                    testable: '100%',
                    small: '85%'
                },
                prioritization: {
                    mustHave: 12,
                    shouldHave: 8,
                    couldHave: 3
                },
                readyForSprint: 8,
                dependencies: 'Выявлены зависимости между US-001 и US-003',
                riskAssessment: 'Низкий риск - все истории детализированы',
                timestamp: new Date().toISOString()
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Создано 23 User Stories с критериями приемки',
                result: finalResult
            });
        }

        return new Response(JSON.stringify({
            data: {
                steps,
                finalResult,
                metadata: {
                    service: 'BA Demo Analysis Service',
                    version: '2.0.0',
                    timestamp: new Date().toISOString(),
                    processingTime: 'Общее время анализа',
                    supportedLanguages: ['ru', 'en'],
                    capabilities: [
                        'Анализ требований',
                        'Моделирование процессов', 
                        'Генерация User Stories',
                        'Создание архитектурных моделей',
                        'Интеграционный анализ',
                        'Безопасность и соответствие',
                        'Производительность и масштабирование'
                    ]
                }
            }
        }), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });

    } catch (error) {
        console.error('BA demo error:', error);
        
        // Определяем код ошибки в зависимости от типа
        let errorCode = 'BA_DEMO_ERROR';
        let statusCode = 500;
        let errorMessage = 'Внутренняя ошибка сервера';
        
        if (error.message.includes('Неверный формат данных')) {
            errorCode = 'INVALID_REQUEST_FORMAT';
            statusCode = 400;
            errorMessage = error.message;
        } else if (error.message.includes('обязателен') || error.message.includes('Неподдерживаемый тип')) {
            errorCode = 'VALIDATION_ERROR';
            statusCode = 400;
            errorMessage = error.message;
        } else if (error.message.includes('JSON')) {
            errorCode = 'JSON_PARSE_ERROR';
            statusCode = 400;
            errorMessage = 'Ошибка парсинга JSON: неверный формат данных';
        }

        return new Response(JSON.stringify({
            error: {
                code: errorCode,
                message: errorMessage,
                timestamp: new Date().toISOString(),
                requestId: crypto.randomUUID(),
                service: 'BA Demo Analysis Service',
                version: '2.0.0',
                supportedDemoTypes: ['custom', 'requirements', 'process', 'stories', 'advanced'],
                documentation: 'Поддерживается анализ бизнес-процессов, требований, архитектуры и интеграций для систем 1С'
            }
        }), {
            status: statusCode,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
    }
});
