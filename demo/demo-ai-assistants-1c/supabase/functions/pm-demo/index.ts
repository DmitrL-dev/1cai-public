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
            steps.push({ progress: 10, message: 'Анализ вашего запроса...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Подготовка плана проекта...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 60, message: 'Формирование решения...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 90, message: 'Оптимизация и финализация...' });
            await new Promise(r => setTimeout(r, 700));
            
            const queryLower = (userQuery || '').toLowerCase();
            let plan = {};
            let customMessage = '';
            
            // Улучшенная логика анализа с большим количеством паттернов
            if (queryLower.includes('планирование') && queryLower.includes('внедрение') || queryLower.includes('план внедрения')) {
                plan = {
                    phases: [
                        { phase: 1, name: 'Анализ и планирование', duration: '3 недели', tasks: 12 },
                        { phase: 2, name: 'Разработка и настройка', duration: '8 недель', tasks: 45 },
                        { phase: 3, name: 'Тестирование', duration: '2 недели', tasks: 28 },
                        { phase: 4, name: 'Обучение и запуск', duration: '1 неделя', tasks: 15 }
                    ],
                    totalDuration: '14 недель',
                    totalTasks: 100
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создан детальный план внедрения 1С:
• 4 основных этапа внедрения
• Общая длительность: 14 недель
• 100 задач в 4 этапах
• Критический путь и контрольные точки`;
            } else if (queryLower.includes('анализ требований') || queryLower.includes('требования') || queryLower.includes('функциональн')) {
                plan = {
                    categories: [
                        { category: 'Функциональные', count: 45, priority: 'Высокая' },
                        { category: 'Нефункциональные', count: 23, priority: 'Средняя' },
                        { category: 'Технические', count: 18, priority: 'Высокая' },
                        { category: 'Интеграционные', count: 12, priority: 'Средняя' },
                        { category: 'Пользовательские', count: 34, priority: 'Высокая' },
                        { category: 'Безопасность', count: 24, priority: 'Критическая' }
                    ],
                    totalRequirements: 156,
                    complexity: 'Высокая'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Проведен анализ требований проекта:
• 156 требований в 6 категориях
• Приоритизация по критичности
• Оценка сложности реализации
• Рекомендации по приоритизации`;
            } else if (queryLower.includes('миграция') || queryLower.includes('перенос данных') || queryLower.includes('загрузка данных') || queryLower.includes('данных') || queryLower.includes('старой системы')) {
                plan = {
                    sources: [
                        { source: 'Excel файлы', volume: '500 МБ', records: 125000 },
                        { source: 'Старая 1С база', volume: '1.2 ГБ', records: 450000 },
                        { source: 'Внешние системы', volume: '800 МБ', records: 89000 }
                    ],
                    totalVolume: '2.5 ГБ',
                    totalRecords: 664000,
                    phases: 4,
                    duration: '3 недели'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создан план миграции данных:
• 3 источника данных для переноса
• Общий объем: 2.5 ГБ (664,000 записей)
• 4 этапа миграции с валидацией
• Планируемая длительность: 3 недели`;
            } else if (queryLower.includes('интеграция') || queryLower.includes('обмен данными') || queryLower.includes('api') || queryLower.includes('синхронизация')) {
                plan = {
                    integrations: [
                        { system: 'CRM система', type: 'REST API', frequency: 'Real-time', status: 'Планируется' },
                        { system: 'Банковские системы', type: 'Web Services', frequency: 'Ежедневно', status: 'Требуется' },
                        { system: 'E-commerce платформа', type: 'CommerceML', frequency: 'Каждые 30 мин', status: 'Критично' },
                        { system: 'Система логистики', type: 'Direct DB', frequency: 'По событиям', status: 'Важно' }
                    ],
                    totalIntegrations: 4,
                    complexity: 'Высокая'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Спроектированы интеграции с внешними системами:
• 4 интеграционных подключения
• Различные типы: REST API, Web Services, CommerceML
• Смешанная синхронизация: Real-time + batch
• Оценка сложности: Высокая`;
            } else if (queryLower.includes('тестирование') || queryLower.includes('test') || queryLower.includes('qa') || queryLower.includes('проверка')) {
                plan = {
                    testTypes: [
                        { type: 'Модульное тестирование', cases: 234, coverage: '85%', automation: '70%' },
                        { type: 'Интеграционное тестирование', cases: 156, coverage: '60%', automation: '40%' },
                        { type: 'Функциональное тестирование', cases: 445, coverage: '90%', automation: '20%' },
                        { type: 'Нагрузочное тестирование', cases: 89, coverage: '45%', automation: '80%' },
                        { type: 'Пользовательское тестирование', cases: 323, coverage: '95%', automation: '0%' }
                    ],
                    totalCases: 1247,
                    totalAutomation: '50%'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Разработана стратегия тестирования:
• 1,247 тест-кейсов в 5 категориях
• Средний уровень автоматизации: 50%
• Критические области с покрытием 90%+
• План поэтапного внедрения автоматизации`;
            } else if (queryLower.includes('запуск в продуктив') || queryLower.includes('go-live') || queryLower.includes('продуктив') || queryLower.includes('внедрение финальн')) {
                plan = {
                    phases: [
                        { phase: 'Предварительный запуск', duration: '1 день', activities: 8, risk: 'Низкий' },
                        { phase: 'Переход на продуктив', duration: '4 часа', activities: 12, risk: 'Высокий' },
                        { phase: 'Стабилизация', duration: '1 неделя', activities: 15, risk: 'Средний' },
                        { phase: '24/7 поддержка', duration: '1 месяц', activities: 24, risk: 'Низкий' }
                    ],
                    goLiveDate: 'Определяется отдельно',
                    supportLevel: '24/7',
                    rollbackPlan: 'Готов'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создан план запуска в продуктив:
• 4 фазы перехода с детализацией рисков
• Время простоя: 4 часа (план)
• Обеспечена 24/7 поддержка после запуска
• Подготовлен план отката на случай проблем`;
            } else if (queryLower.includes('поддержка') || queryLower.includes('support') || queryLower.includes('сопровождение') || queryLower.includes('помощ')) {
                plan = {
                    levels: [
                        { level: 1, name: 'Первый уровень', response: '2 часа', description: 'Пользовательские вопросы' },
                        { level: 2, name: 'Второй уровень', response: '8 часов', description: 'Техническая поддержка' },
                        { level: 3, name: 'Третий уровень', response: '24 часа', description: 'Разработка исправлений' }
                    ],
                    sla: '95%',
                    availability: '99.5%',
                    monthlyIncidents: 45
                };
                customMessage = `Анализ запроса: "${userQuery}"

Спроектирована модель поддержки:
• 3-уровневая модель эскалации
• SLA: 95% (время ответа соответствует стандартам)
• Доступность системы: 99.5%
• Среднее количество инцидентов: 45/месяц`;
            } else if (queryLower.includes('upgrade') || queryLower.includes('обновление') || queryLower.includes('версия') || queryLower.includes('апгрейд')) {
                plan = {
                    currentVersion: '8.3.18',
                    targetVersion: '8.3.24',
                    migrationType: 'Major Update',
                    components: [
                        { component: 'Платформа 1С', complexity: 'Средняя', downtime: '2 часа' },
                        { component: 'Конфигурация', complexity: 'Высокая', downtime: '4 часа' },
                        { component: 'Данные', complexity: 'Низкая', downtime: '1 час' },
                        { component: 'Интеграции', complexity: 'Средняя', downtime: '3 часа' }
                    ],
                    totalDowntime: '6 часов',
                    rollbackTime: '4 часа'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Подготовлена стратегия обновления:
• Переход с версии 8.3.18 на 8.3.24
• Общее время простоя: 6 часов (план)
• Подготовлен план отката (4 часа)
• Поэтапное обновление с минимизацией рисков`;
            } else {
                plan = {
                    tasks: [
                        { name: 'Анализ требований', assignee: 'Бизнес-аналитик', deadline: '2 недели' },
                        { name: 'Проектирование архитектуры', assignee: 'Архитектор', deadline: '1 неделя' },
                        { name: 'Разработка и настройка', assignee: 'Разработчик 1С', deadline: '6 недель' },
                        { name: 'Интеграция систем', assignee: 'Интегратор', deadline: '2 недели' },
                        { name: 'Тестирование', assignee: 'Тестировщик', deadline: '3 недели' },
                        { name: 'Обучение пользователей', assignee: 'Методист', deadline: '1 неделя' }
                    ],
                    totalTasks: 6,
                    estimatedDuration: '15 недель'
                };
                customMessage = `Анализ запроса: "${userQuery}"

Создан базовый план проекта:
• 6 ключевых задач с ответственными
• Оценка общей длительности: 15 недель
• Последовательное выполнение с контрольными точками
• Учтены зависимости между задачами`;
            }
            
            finalResult = {
                message: customMessage,
                plan: plan,
                userQuery: userQuery
            };
            
            steps.push({ 
                progress: 100, 
                message: 'План проекта успешно создан!',
                result: finalResult
            });
            
        } else if (demoType === 'plan') {
            steps.push({ progress: 10, message: 'Запуск планирования...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Анализ масштабов проекта...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 60, message: 'Создание детального плана...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 80, message: 'Распределение ресурсов...' });
            await new Promise(r => setTimeout(r, 800));
            
            finalResult = {
                phases: [
                    { name: 'Инициализация', duration: '2 недели', tasks: 15 },
                    { name: 'Разработка', duration: '8 недель', tasks: 65 },
                    { name: 'Тестирование', duration: '3 недели', tasks: 25 },
                    { name: 'Внедрение', duration: '2 недели', tasks: 20 }
                ],
                totalDuration: '15 недель',
                budget: '1,800,000 ₽',
                teamSize: 8
            };
            
            steps.push({ 
                progress: 100, 
                message: 'План создан: 4 фазы, 15 недель, команда 8 человек',
                result: finalResult
            });
            
        } else if (demoType === 'risks') {
            steps.push({ progress: 10, message: 'Анализ рисков проекта...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 40, message: 'Выявление потенциальных проблем...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 70, message: 'Оценка вероятности и влияния...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 90, message: 'Разработка планов митигации...' });
            
            finalResult = {
                criticalRisks: [
                    { risk: 'Недостаток квалифицированных специалистов 1С', probability: 'Высокая', impact: 'Высокий', mitigation: 'Привлечение внешних консультантов' },
                    { risk: 'Сложность интеграции с устаревшими системами', probability: 'Средняя', impact: 'Критический', mitigation: 'Поэтапная миграция с тестированием' },
                    { risk: 'Сопротивление изменениям со стороны пользователей', probability: 'Высокая', impact: 'Средний', mitigation: 'Программа обучения и вовлечения' }
                ],
                totalRisks: 12,
                mitigationBudget: '300,000 ₽'
            };
            
            steps.push({ 
                progress: 100, 
                message: 'Выявлено рисков: 3 критических, 9 средних и низких',
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
        console.error('PM demo error:', error);

        return new Response(JSON.stringify({
            error: {
                code: 'PM_DEMO_ERROR',
                message: error.message
            }
        }), {
            status: 500,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
    }
});
