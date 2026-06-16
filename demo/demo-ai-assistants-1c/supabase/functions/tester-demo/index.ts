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
            
            steps.push({ progress: 30, message: 'Подготовка тестовых сценариев...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 60, message: 'Генерация тест-кейсов...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 90, message: 'Финализация результатов...' });
            await new Promise(r => setTimeout(r, 700));
            
            const queryLower = (userQuery || '').toLowerCase();
            let testCases = [];
            let customMessage = '';

            // Анализ пользовательского запроса с учетом специфики 1С
            if (queryLower.includes('unit') || queryLower.includes('модульн') || queryLower.includes('проверка') && queryLower.includes('функц')) {
                // Unit тесты для 1С
                testCases = [
                    { id: 'UT-001', module: 'ОбщиеМодули.РасчетСуммы', function: 'РассчитатьСумму', type: 'positive', status: 'covered' },
                    { id: 'UT-002', module: 'ОбщиеМодули.РасчетСуммы', function: 'РассчитатьСумму', type: 'boundary', status: 'covered' },
                    { id: 'UT-003', module: 'ОбщиеМодули.РасчетСуммы', function: 'РассчитатьСумму', type: 'negative', status: 'pending' },
                    { id: 'UT-004', module: 'Справочники.Товары', function: 'ПередЗаписью', type: 'validation', status: 'not_covered' },
                    { id: 'UT-005', module: 'Документы.ПриходТовара', function: 'ОбработкаПроверкиЗаполнения', type: 'business_logic', status: 'covered' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Созданы Unit тесты для 1С:
• Тестирование общих модулей (функции расчетов) - покрыто 100%
• Проверка бизнес-логики в документах - покрыто 100%
• Валидация данных в справочниках - требует доработки
• Граничные случаи и обработка ошибок - частично покрыто
• Рекомендация: добавить тесты для обработки исключительных ситуаций`;
            } else if (queryLower.includes('интеграц') || queryLower.includes('обмен') || queryLower.includes('синхронизац')) {
                // Интеграционные тесты
                testCases = [
                    { id: 'IT-001', scenario: 'Загрузка данных из внешней системы', endpoint: 'REST API', status: 'passed', duration: '1.2s' },
                    { id: 'IT-002', scenario: 'Синхронизация справочников', system: 'ERP', records: 1500, status: 'passed', duration: '5.8s' },
                    { id: 'IT-003', scenario: 'Обмен документами', system: 'Банк', documents: 50, status: 'failed', error: 'Timeout' },
                    { id: 'IT-004', scenario: 'Интеграция с веб-сервисом', service: 'Доставка', status: 'passed', response: '200 OK' },
                    { id: 'IT-005', scenario: 'Репликация данных', target: 'Мониторинг', status: 'passed', latency: '200ms' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Выполнены интеграционные тесты:
• Загрузка данных из внешних систем - стабильная (1.2с)
• Синхронизация справочников с ERP - работает (1500 записей за 5.8с)
• Обмен документами с банком - проблемы (таймаут)
• Веб-сервисы доставки - функционируют корректно
• Репликация в систему мониторинга - оптимальная производительность (200мс)
• Действие: устранить таймауты в банковском обмене`;
            } else if (queryLower.includes('функционал') || queryLower.includes('бизнес-процесс') || queryLower.includes('сценарий')) {
                // Функциональные тесты
                testCases = [
                    { id: 'FT-001', process: 'Закупка товаров', step: 'Создание заказа поставщику', result: 'success', business_value: 'high' },
                    { id: 'FT-002', process: 'Закупка товаров', step: 'Получение товара', result: 'success', business_value: 'high' },
                    { id: 'FT-003', process: 'Продажи', step: 'Оформление заказа клиента', result: 'success', business_value: 'high' },
                    { id: 'FT-004', process: 'Продажи', step: 'Отгрузка товара', result: 'success', business_value: 'high' },
                    { id: 'FT-005', process: 'Складские операции', step: 'Перемещение между складами', result: 'success', business_value: 'medium' },
                    { id: 'FT-006', process: 'Складские операции', step: 'Списание товара', result: 'failed', business_value: 'high' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Проведено функциональное тестирование бизнес-процессов:
• Процесс "Закупка товаров" - полностью функционален
• Процесс "Продажи" - работает без ошибок
• "Складские операции" - критический сбой в списании товара
• Пользовательские сценарии покрыты на 95%
• Бизнес-ценность: критические процессы протестированы
• Действие: срочно исправить списание товара`;
            } else if (queryLower.includes('регрессия') || queryLower.includes('regression') || queryLower.includes('стабильность')) {
                // Регрессионные тесты
                testCases = [
                    { id: 'RT-001', build: '2.1.15', module: 'Документы', tests: 245, passed: 242, failed: 3, stability: '98.8%' },
                    { id: 'RT-002', build: '2.1.15', module: 'Справочники', tests: 156, passed: 156, failed: 0, stability: '100%' },
                    { id: 'RT-003', build: '2.1.15', module: 'Отчеты', tests: 89, passed: 87, failed: 2, stability: '97.8%' },
                    { id: 'RT-004', build: '2.1.15', module: 'Обработки', tests: 134, passed: 134, failed: 0, stability: '100%' },
                    { id: 'RT-005', build: '2.1.15', module: 'Регистры', tests: 78, passed: 75, failed: 3, stability: '96.2%' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Выполнены регрессионные тесты сборки 2.1.15:
• Общая стабильность: 98.1% (702 теста из 715)
• Документы: 98.8% стабильность (3 критических сбоя)
• Справочники: 100% стабильность ✅
• Отчеты: 97.8% стабильность (2 ошибки форматирования)
• Регистры: 96.2% стабильность (3 проблемы с расчетами)
• Рекомендация: исправить критические ошибки в документах и регистрах`;
            } else if (queryLower.includes('производительн') || queryLower.includes('нагрузк') || queryLower.includes('performance') || queryLower.includes('время отклика')) {
                // Тестирование производительности
                testCases = [
                    { id: 'PT-001', operation: 'Открытие справочника товаров', users: 100, response_time: '0.8s', status: 'PASS', throughput: '125/sec' },
                    { id: 'PT-002', operation: 'Создание документа продажи', users: 50, response_time: '1.2s', status: 'PASS', throughput: '42/sec' },
                    { id: 'PT-003', operation: 'Формирование отчета Остатки', users: 200, response_time: '3.5s', status: 'WARN', throughput: '57/sec' },
                    { id: 'PT-004', operation: 'Проведение документа ПриходТовара', users: 100, response_time: '2.1s', status: 'PASS', throughput: '48/sec' },
                    { id: 'PT-005', operation: 'Расчет себестоимости', users: 20, response_time: '12.3s', status: 'FAIL', throughput: '1.6/sec' },
                    { id: 'PT-006', operation: 'Массовая загрузка данных', users: 10, response_time: '45.2s', status: 'FAIL', throughput: '0.2/sec' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Проведено тестирование производительности:
• Справочники: отличная производительность (0.8с при 100 пользователях)
• Документы продаж: хорошая производительность (1.2с при 50 пользователях)
• Отчеты: приемлемая производительность (3.5с при 200 пользователях)
• Регистры: хорошая производительность (2.1с при 100 пользователях)
• КРИТИЧНО: Расчет себестоимости (12.3с) и массовая загрузка (45.2с)
• Рекомендации: оптимизировать расчеты и загрузку данных`;
            } else if (queryLower.includes('ui') || queryLower.includes('интерфейс') || queryLower.includes('формы') || queryLower.includes('пользовательск')) {
                // Тестирование пользовательского интерфейса
                testCases = [
                    { id: 'UI-001', form: 'Документы.Продажа', element: 'Кнопка "Провести"', action: 'click', result: 'success', browser: 'Chrome' },
                    { id: 'UI-002', form: 'Справочники.Товары', element: 'Поле "Наименование"', action: 'input', result: 'validation_pass', browser: 'Chrome' },
                    { id: 'UI-003', form: 'Отчеты.Продажи', element: 'Таблица результата', action: 'render', result: 'data_displayed', browser: 'Firefox' },
                    { id: 'UI-004', form: 'Обработки.ЗагрузкаДанных', element: 'Прогресс-бар', action: 'progress_update', result: 'smooth', browser: 'IE11' },
                    { id: 'UI-005', form: 'ОбщиеФормы.Настройки', element: 'Checkbox "Автосохранение"', action: 'toggle', result: 'state_changed', browser: 'Edge' },
                    { id: 'UI-006', form: 'Журналы.Документы', element: 'Фильтр по дате', action: 'date_picker', result: 'filter_works', browser: 'Safari' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Проведено тестирование пользовательского интерфейса:
• Кнопки и элементы управления - работают во всех браузерах
• Валидация полей ввода - корректная
• Отображение данных в таблицах - стабильное
• Прогресс-индикаторы - плавное обновление
• Интерактивные элементы (checkbox, фильтры) - функциональны
• Кроссбраузерное тестирование: Chrome, Firefox, IE11, Edge, Safari
• Результат: UI стабилен, готов к продакшену`;
            } else if (queryLower.includes('отчет') || queryLower.includes('report') || queryLower.includes('аналитика')) {
                // Тестирование отчетов
                testCases = [
                    { id: 'RP-001', report: 'ОстаткиТоваров', parameters: 'Склад=Основной', records: 1247, execution_time: '1.8s', accuracy: '100%' },
                    { id: 'RP-002', report: 'ПродажиПоПериодам', parameters: 'Дата=2024-10-01..2024-10-31', records: 3456, execution_time: '2.3s', accuracy: '100%' },
                    { id: 'RP-003', report: 'ВзаиморасчетыСКонтрагентами', parameters: 'Контрагент=Все', records: 892, execution_time: '4.1s', accuracy: '98.7%' },
                    { id: 'RP-004', report: 'ДвиженияТоваров', parameters: 'Товар=Группа "Электроника"', records: 2156, execution_time: '3.2s', accuracy: '100%' },
                    { id: 'RP-005', report: 'Себестоимость', parameters: 'Период=2024-10-01..2024-10-31', records: 567, execution_time: '8.7s', accuracy: '96.4%' },
                    { id: 'RP-006', report: 'ЭффективностьПродаж', parameters: 'Менеджер=Все', records: 234, execution_time: '5.9s', accuracy: '100%' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Протестированы аналитические отчеты 1С:
• "ОстаткиТоваров": высокая точность, быстрая генерация (1.8с)
• "ПродажиПоПериодам": отличная производительность (2.3с)
• "Взаиморасчеты": приемлемое время (4.1с), точность 98.7%
• "ДвиженияТоваров": стабильная работа (3.2с)
• ПРОБЛЕМА: "Себестоимость" медленная (8.7с), точность 96.4%
• "ЭффективностьПродаж": корректные расчеты (5.9с)
• Рекомендация: оптимизировать расчет себестоимости`;
            } else if (queryLower.includes('обмен') || queryLower.includes('синхронизац') || queryLower.includes('выгрузк') || queryLower.includes('загрузк')) {
                // Тестирование обменов данными
                testCases = [
                    { id: 'EX-001', direction: 'Выгрузка', target: 'Сайт', format: 'CommerceML', records: 2450, status: 'success', duration: '12.3s' },
                    { id: 'EX-002', direction: 'Загрузка', source: 'Банк-клиент', format: '1CClientBankExchange', records: 156, status: 'success', duration: '3.2s' },
                    { id: 'EX-003', direction: 'Обмен', system: 'CRM', format: 'REST API', records: 89, status: 'partial', errors: 3 },
                    { id: 'EX-004', direction: 'Выгрузка', target: 'Бухгалтерия', format: 'БухгалтерскиеИзы', records: 678, status: 'success', duration: '8.7s' },
                    { id: 'EX-005', direction: 'Загрузка', source: 'Excel', format: 'ЛистExcel', records: 234, status: 'failed', error: 'Поврежденный файл' },
                    { id: 'EX-006', direction: 'Синхронизация', system: 'WMS', format: 'XML', records: 456, status: 'success', duration: '6.1s' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Протестированы сценарии обмена данными:
• Выгрузка на сайт: успешная (2450 записей за 12.3с)
• Банковские выписки: стабильная загрузка (156 записей за 3.2с)
• Интеграция с CRM: частичная синхронизация (3 ошибки)
• Бухгалтерские выгрузки: корректная работа (678 записей за 8.7с)
• ПРОБЛЕМА: загрузка из Excel (поврежденный файл)
• Синхронизация с WMS: успешная (456 записей за 6.1с)
• Рекомендация: добавить валидацию загружаемых файлов Excel`;
            } else if (queryLower.includes('документ') && queryLower.includes('проведени') || queryLower.includes('проведен')) {
                // Тестирование проведения документов
                testCases = [
                    { id: 'DC-001', document: 'ПриходТовара', action: 'Записать', result: 'success', business_rules: 'Проверен', audit_trail: 'Создан' },
                    { id: 'DC-002', document: 'ПриходТовара', action: 'Провести', result: 'success', business_rules: 'Проверен', audit_trail: 'Обновлен' },
                    { id: 'DC-003', document: 'РасходТовара', action: 'Записать', result: 'success', business_rules: 'Проверен', audit_trail: 'Создан' },
                    { id: 'DC-004', document: 'РасходТовара', action: 'Провести', result: 'failed', business_rules: 'Недостаточно товара', error: 'Negative balance' },
                    { id: 'DC-005', document: 'СчетНаОплату', action: 'Провести', result: 'success', business_rules: 'Проверен', audit_trail: 'Обновлен' },
                    { id: 'DC-006', document: 'ВозвратТовара', action: 'Провести', result: 'success', business_rules: 'Проверен', audit_trail: 'Обновлен' },
                    { id: 'DC-007', document: 'ОприходованиеТовара', action: 'Провести', result: 'success', business_rules: 'Проверен', audit_trail: 'Создан' },
                    { id: 'DC-008', document: 'СписаниеТовара', action: 'Провести', result: 'failed', business_rules: 'Отсутствует основание', error: 'No basis for write-off' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Протестировано проведение документов 1С:
• Приход товара: запись и проведение работают корректно
• Расход товара: запись успешна, проведение блокирует недостачу
• Счета на оплату: проведение с контролем бизнес-правил
• Возвраты товара: корректное проведение
• Оприходование: успешное проведение с созданием движений
• ПРОБЛЕМА: списание товара блокируется (нет основания)
• Бизнес-правила работают корректно
• Аудит-трейл ведется для всех операций
• Рекомендация: доработать интерфейс для указания оснований списания`;
            } else if (queryLower.includes('регистр') || queryLower.includes('накопления') || queryLower.includes('сведений')) {
                // Тестирование регистров
                testCases = [
                    { id: 'RG-001', register: 'ОстаткиТоваров', operation: 'Добавить', period: '2024-11-01', records: 150, accuracy: '100%' },
                    { id: 'RG-002', register: 'ОстаткиТоваров', operation: 'Изменить', period: '2024-11-01', records: 45, accuracy: '100%' },
                    { id: 'RG-003', register: 'ОстаткиТоваров', operation: 'ПолучитьОстаток', query: 'Товар=Ноутбук Dell', result: 15, accuracy: '100%' },
                    { id: 'RG-004', register: 'Взаиморасчеты', operation: 'Добавить', period: '2024-11-01', records: 89, accuracy: '100%' },
                    { id: 'RG-005', register: 'Взаиморасчеты', operation: 'ПолучитьВзаиморасчеты', query: 'Контрагент=ООО Рога и копыта', result: 250000.50, accuracy: '100%' },
                    { id: 'RG-006', register: 'Продажи', operation: 'Добавить', period: '2024-11-01', records: 234, accuracy: '99.6%' },
                    { id: 'RG-007', register: 'ЦеныНоменклатуры', operation: 'Обновить', period: '2024-11-01', records: 67, accuracy: '100%' },
                    { id: 'RG-008', register: 'ЦеныНоменклатуры', operation: 'ПолучитьЦену', query: 'Товар=Клавиатура, ТипЦен=Розничная', result: 8500, accuracy: '100%' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Протестирована работа регистров 1С:
• Регистр "ОстаткиТоваров": добавление, изменение, получение остатков - 100% точность
• Регистр "Взаиморасчеты": корректный учет расчетов с контрагентами
• Регистр "Продажи": высокая точность учета (99.6%)
• Регистр "ЦеныНоменклатуры": стабильное обновление и получение цен
• Контрольные операции: остатки, взаиморасчеты, продажи, цены
• Производительность: быстрые выборки и записи
• Рекомендация: исправить точность в регистре "Продажи"`;
            } else if (queryLower.includes('автотест') || queryLower.includes('автоматиз') || queryLower.includes('automation') || queryLower.includes('скрипт')) {
                // Автоматизация тестирования
                testCases = [
                    { id: 'AT-001', tool: ' Vanessa.ADD', purpose: 'BDD тесты', coverage: '85%', status: 'running' },
                    { id: 'AT-002', tool: ' xUnitFor1C', purpose: 'Unit тесты', coverage: '78%', status: 'running' },
                    { id: 'AT-003', tool: ' Selenium', purpose: 'UI тесты', coverage: '62%', status: 'configured' },
                    { id: 'AT-004', tool: ' Allure', purpose: 'Отчеты', coverage: '90%', status: 'integrated' },
                    { id: 'AT-005', tool: ' Jenkins', purpose: 'CI/CD', coverage: '95%', status: 'configured' },
                    { id: 'AT-006', tool: ' GitLab CI', purpose: 'Автозапуск', coverage: '88%', status: 'configured' },
                    { id: 'AT-007', tool: ' Тест-менеджер', purpose: 'Управление тестами', coverage: '100%', status: 'active' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Настроена автоматизация тестирования 1С:
• Vanessa.ADD (BDD): покрытие 85%, активно используется
• xUnitFor1C (Unit): покрытие 78%, запущено в CI
• Selenium (UI): покрытие 62%, настроен для веб-клиента
• Allure (Отчеты): интеграция 90%, подробная аналитика
• Jenkins (CI/CD): покрытие 95%, автозапуск сборок
• GitLab CI: покрытие 88%, альтернативный pipeline
• Тест-менеджер: покрытие 100%, централизованное управление
• Рекомендация: увеличить покрытие UI-тестов до 80%`;
            } else if (queryLower.includes('покрытие') || queryLower.includes('coverage')) {
                testCases = [
                    { id: 1, name: 'Проверка основного функционала', status: 'covered', priority: 'high' },
                    { id: 2, name: 'Граничные значения', status: 'covered', priority: 'high' },
                    { id: 3, name: 'Обработка ошибок', status: 'partial', priority: 'medium' },
                    { id: 4, name: 'Производительность', status: 'not_covered', priority: 'low' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Анализ тестового покрытия завершен:
• Основной функционал покрыт на 100%
• Граничные значения проверены полностью
• Обработка ошибок покрыта частично (требуется доработка)
• Тесты производительности отсутствуют (рекомендуется добавить)`;
            } else if (queryLower.includes('данны') || queryLower.includes('data') || queryLower.includes('тестов')) {
                testCases = [
                    { scenario: 'Валидные данные', expected: 'Успешная обработка', data_count: 100 },
                    { scenario: 'Граничные значения', expected: 'Корректная обработка', data_count: 50 },
                    { scenario: 'Невалидные данные', expected: 'Обработка ошибки', data_count: 30 }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Сгенерирован комплексный набор тестовых данных:
• 100 записей валидных данных для позитивных тестов
• 50 граничных значений для проверки лимитов
• 30 невалидных записей для негативных тестов
• Общий объем: 180 записей, покрывающих все сценарии`;
            } else if (queryLower.includes('сценар') || queryLower.includes('тест-кейс') || queryLower.includes('case') || queryLower.includes('scenari')) {
                // Тестовые сценарии
                testCases = [
                    { id: 'TS-001', scenario: 'Полный цикл закупки', steps: 12, business_value: 'high', automated: 'yes', priority: 'critical' },
                    { id: 'TS-002', scenario: 'Процесс продажи с предоплатой', steps: 8, business_value: 'high', automated: 'yes', priority: 'critical' },
                    { id: 'TS-003', scenario: 'Возврат товара от клиента', steps: 6, business_value: 'medium', automated: 'no', priority: 'normal' },
                    { id: 'TS-004', scenario: 'Инвентаризация склада', steps: 15, business_value: 'high', automated: 'partial', priority: 'high' },
                    { id: 'TS-005', scenario: 'Настройка скидок и наценок', steps: 5, business_value: 'medium', automated: 'yes', priority: 'normal' },
                    { id: 'TS-006', scenario: 'Формирование бухгалтерских проводок', steps: 9, business_value: 'high', automated: 'yes', priority: 'critical' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Созданы тестовые сценарии для 1С:
• Полный цикл закупки (12 шагов): автоматизирован ✅
• Продажи с предоплатой (8 шагов): автоматизирован ✅
• Возврат товара: ручное тестирование (требует автоматизации)
• Инвентаризация: частично автоматизирована (15 шагов)
• Скидки и наценки: автоматизированы ✅
• Бухгалтерские проводки: автоматизированы ✅
• Критичность: 4 сценария критичны для бизнеса
• Автоматизация: 67% сценариев автоматизировано`;
            } else if (queryLower.includes('валидац') || queryLower.includes('проверк') || queryLower.includes('валид')) {
                // Проверка данных
                testCases = [
                    { id: 'VD-001', field: 'ИНН', rule: 'Корректный формат (10-12 цифр)', test_cases: 15, passed: 15, validation_type: 'regex' },
                    { id: 'VD-002', field: 'Наименование', rule: 'Не пустое, макс 150 символов', test_cases: 20, passed: 18, validation_type: 'length_check' },
                    { id: 'VD-003', field: 'Цена', rule: 'Больше 0, до 1 млн', test_cases: 25, passed: 25, validation_type: 'numeric_range' },
                    { id: 'VD-004', field: 'КодТовара', rule: 'Уникальность в справочнике', test_cases: 100, passed: 99, validation_type: 'uniqueness' },
                    { id: 'VD-005', field: 'Дата', rule: 'Не в будущем, корректный формат', test_cases: 30, passed: 30, validation_type: 'date_validation' },
                    { id: 'VD-006', field: 'Email', rule: 'Корректный email адрес', test_cases: 18, passed: 16, validation_type: 'email_format' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Проведена валидация данных в 1С:
• ИНН контрагентов: 100% корректность (15/15 тестов пройдено)
• Наименования номенклатуры: 90% корректность (18/20, 2 превышают лимит)
• Цены товаров: 100% валидация диапазона (25/25)
• Уникальность кодов: 99% корректность (99/100, найден дубль)
• Даты документов: 100% корректность формата (30/30)
• Email адреса: 89% корректность (16/18, 2 невалидных формата)
• Рекомендация: доработать валидацию наименований и email`;
            } else {
                testCases = [
                    { id: 'TC-001', description: 'Позитивный сценарий', status: 'pass' },
                    { id: 'TC-002', description: 'Негативный сценарий', status: 'pass' },
                    { id: 'TC-003', description: 'Граничные условия', status: 'pending' }
                ];
                customMessage = `Анализ запроса: "${userQuery}"

Созданы базовые тест-кейсы:
• Позитивный сценарий с валидными данными (пройден)
• Негативный сценарий с невалидными данными (пройден)
• Тестирование граничных условий (в ожидании)
• Готовность к расширению под специфические требования`;
            }
            
            finalResult = {
                message: customMessage,
                testCases: testCases,
                totalTests: testCases.length,
                userQuery: userQuery
            };
            
            steps.push({ 
                progress: 100, 
                message: 'Тест-кейсы успешно сгенерированы!',
                result: finalResult
            });
            
        } else if (demoType === 'generate') {
            steps.push({ progress: 10, message: 'Запуск генерации тест-кейсов...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Анализ функциональных требований...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 55, message: 'Генерация позитивных тест-кейсов...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 80, message: 'Генерация негативных тест-кейсов...' });
            await new Promise(r => setTimeout(r, 800));
            
            const testCases = [
                {
                    id: 'TC_001',
                    type: 'positive',
                    category: 'Документы',
                    title: 'Создание приходной накладной с валидными данными',
                    module: 'Документы.ПриходТовара',
                    steps: [
                        'Открыть форму документа "Приход товара"',
                        'Заполнить склад: "Основной склад"',
                        'Добавить строку: Товар="Ноутбук ASUS", Количество=5, Цена=75000',
                        'Заполнить поставщика: "ООО ТехноПоставщик"',
                        'Проверить автоматический расчет суммы: 375000',
                        'Нажать "Провести и закрыть"'
                    ],
                    expected: 'Документ успешно проведен, созданы движения по регистрам',
                    business_value: 'high',
                    automation_status: 'automated'
                },
                {
                    id: 'TC_002',
                    type: 'negative',
                    category: 'Документы',
                    title: 'Попытка проведения документа без указания товара',
                    module: 'Документы.ПриходТовара',
                    steps: [
                        'Создать новый документ "Приход товара"',
                        'Заполнить склад: "Основной склад"',
                        'Оставить табличную часть пустой',
                        'Заполнить поставщика: "ООО ТехноПоставщик"',
                        'Нажать "Провести"'
                    ],
                    expected: 'Система выдает ошибку: "Не заполнены обязательные поля: Товары"',
                    business_value: 'high',
                    automation_status: 'automated'
                },
                {
                    id: 'TC_003',
                    type: 'positive',
                    category: 'Справочники',
                    title: 'Создание номенклатуры с полным набором реквизитов',
                    module: 'Справочники.Номенклатура',
                    steps: [
                        'Открыть справочник "Номенклатура"',
                        'Нажать "Создать"',
                        'Заполнить наименование: "Монитор Samsung 27"',
                        'Заполнить артикул: "SM-27-4K-001"',
                        'Установить единицу измерения: "шт"',
                        'Заполнить ставку НДС: "18%"',
                        'Установить вид номенклатуры: "Товары"',
                        'Сохранить элемент'
                    ],
                    expected: 'Элемент справочника успешно создан с уникальным кодом',
                    business_value: 'medium',
                    automation_status: 'automated'
                },
                {
                    id: 'TC_004',
                    type: 'boundary',
                    category: 'Справочники',
                    title: 'Создание номенклатуры с максимальной длиной наименования',
                    module: 'Справочники.Номенклатура',
                    steps: [
                        'Создать новый элемент номенклатуры',
                        'Ввести наименование длиной 150 символов (максимальная длина)',
                        'Заполнить остальные обязательные реквизиты',
                        'Попытаться сохранить'
                    ],
                    expected: 'Система корректно сохраняет элемент с полным наименованием',
                    business_value: 'medium',
                    automation_status: 'automated'
                },
                {
                    id: 'TC_005',
                    type: 'positive',
                    category: 'Отчеты',
                    title: 'Формирование отчета "Остатки товаров" с параметрами',
                    module: 'Отчеты.ОстаткиТоваров',
                    steps: [
                        'Открыть отчет "Остатки товаров"',
                        'Установить период: с 01.11.2024 по 30.11.2024',
                        'Выбрать склад: "Основной склад"',
                        'Нажать "Сформировать"',
                        'Проверить корректность отображения данных',
                        'Экспортировать в Excel'
                    ],
                    expected: 'Отчет формируется корректно, данные соответствуют ожидаемым',
                    business_value: 'high',
                    automation_status: 'semi_automated'
                },
                {
                    id: 'TC_006',
                    type: 'negative',
                    category: 'Регистры',
                    title: 'Попытка проведения расходного документа при отрицательном остатке',
                    module: 'Документы.РасходТовара',
                    steps: [
                        'Проверить текущий остаток товара "Монитор Samsung 27" = 2 шт',
                        'Создать документ "Расход товара"',
                        'Попытаться отгрузить 5 шт товара "Монитор Samsung 27"',
                        'Провести документ'
                    ],
                    expected: 'Система блокирует проведение с сообщением "Недостаточно товара на складе"',
                    business_value: 'critical',
                    automation_status: 'automated'
                },
                {
                    id: 'TC_007',
                    type: 'integration',
                    category: 'Обмен данными',
                    title: 'Загрузка номенклатуры из Excel файла',
                    module: 'Обработки.ЗагрузкаДанныхИзТабличногоДокумента',
                    steps: [
                        'Открыть обработку загрузки данных',
                        'Выбрать файл: "Номенклатура.xlsx"',
                        'Настроить сопоставление колонок: Наименование, Артикул, Цена',
                        'Выполнить загрузку',
                        'Проверить результат загрузки в справочнике'
                    ],
                    expected: 'Данные успешно загружены, созданы новые элементы справочника',
                    business_value: 'high',
                    automation_status: 'semi_automated'
                },
                {
                    id: 'TC_008',
                    type: 'performance',
                    category: 'Производительность',
                    title: 'Тестирование производительности формирования отчета с большим объемом данных',
                    module: 'Отчеты.ВедомостьПоПартиямТоваров',
                    steps: [
                        'Открыть отчет "Ведомость по партиям товаров"',
                        'Установить период: год (с 01.01.2024 по 31.12.2024)',
                        'Выбрать все склады',
                        'Нажать "Сформировать"',
                        'Замерить время формирования отчета'
                    ],
                    expected: 'Отчет формируется за время не более 10 секунд',
                    business_value: 'medium',
                    automation_status: 'automated'
                },
                {
                    id: 'TC_009',
                    type: 'security',
                    category: 'Безопасность',
                    title: 'Проверка разграничения прав доступа к документам',
                    module: 'УправлениеДоступом',
                    steps: [
                        'Войти в систему под пользователем "Менеджер"',
                        'Попытаться открыть документ "Закрытие месяца" (запрещено)',
                        'Попытаться изменить цены номенклатуры (запрещено)',
                        'Проверить доступность разрешенных операций'
                    ],
                    expected: 'Доступ ограничен согласно настройкам ролей',
                    business_value: 'critical',
                    automation_status: 'automated'
                },
                {
                    id: 'TC_010',
                    type: 'regression',
                    category: 'Регрессионные тесты',
                    title: 'Проверка корректности расчета себестоимости после обновления',
                    module: 'РегистрыНакопления.ПартииТоваров',
                    steps: [
                        'Открыть документ поступления товара',
                        'Провести документ',
                        'Выполнить расчет себестоимости',
                        'Проверить соответствие расчетов ожидаемым значениям'
                    ],
                    expected: 'Расчет себестоимости выполняется корректно',
                    business_value: 'high',
                    automation_status: 'automated'
                }
            ];
            
            finalResult = {
                testCases,
                totalCases: 10,
                categories: {
                    documents: 3,
                    reference: 2,
                    reports: 2,
                    registers: 1,
                    integration: 1,
                    performance: 1,
                    security: 1,
                    regression: 1
                },
                types: {
                    positive: 4,
                    negative: 2,
                    boundary: 1,
                    integration: 1,
                    performance: 1,
                    security: 1,
                    regression: 1
                },
                automation: {
                    automated: 7,
                    semi_automated: 2,
                    manual: 1
                },
                businessPriority: {
                    critical: 3,
                    high: 5,
                    medium: 2
                },
                coverage: {
                    functional: '95%',
                    performance: '80%',
                    security: '90%',
                    integration: '85%'
                }
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Создано 10 комплексных тест-кейсов для 1С: покрытие функционала 95%, автоматизация 90%',
                result: finalResult
            });
            
        } else if (demoType === 'data') {
            steps.push({ progress: 10, message: 'Запуск генерации тестовых данных...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 25, message: 'Анализ структуры данных...' });
            await new Promise(r => setTimeout(r, 800));
            
            steps.push({ progress: 60, message: 'Генерация реалистичных данных...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 85, message: 'Создание граничных случаев...' });
            await new Promise(r => setTimeout(r, 700));
            
            const testData = {
                reference: {
                    products: [
                        { name: 'Ноутбук Dell XPS 15', sku: 'DELL-XPS-15-001', price: 125000, stock: 15, unit: 'шт', nds: 18 },
                        { name: 'Клавиатура механическая', sku: 'KB-MECH-001', price: 8500, stock: 42, unit: 'шт', nds: 18 },
                        { name: 'Мышь беспроводная', sku: 'MOUSE-WL-001', price: 2500, stock: 89, unit: 'шт', nds: 18 },
                        { name: 'Монитор 27" 4K', sku: 'MON-27-4K-001', price: 35000, stock: 25, unit: 'шт', nds: 18 },
                        { name: 'Услуга настройки', sku: 'SERV-SETUP-001', price: 5000, stock: 9999, unit: 'час', nds: 18 }
                    ],
                    contractors: [
                        { name: 'ООО "ТехноПоставщик"', inn: '1234567890', kpp: '123456001', contract: 'Договор поставки №1' },
                        { name: 'ИП Петров А.В.', inn: '9876543210', kpp: '', contract: 'Договор поставки №2' },
                        { name: 'ООО "ЛогистикПро"', inn: '1122334455', kpp: '112233001', contract: 'Договор доставки' }
                    ]
                },
                documents: [
                    {
                        type: 'ПриходТовара',
                        number: 'ПТ-000001',
                        date: '2024-11-01',
                        warehouse: 'Основной склад',
                        supplier: 'ООО "ТехноПоставщик"',
                        totalAmount: 450000
                    },
                    {
                        type: 'РасходТовара',
                        number: 'РТ-000001', 
                        date: '2024-11-01',
                        warehouse: 'Основной склад',
                        customer: 'ООО "КлиентПро"',
                        totalAmount: 125000
                    }
                ],
                registers: {
                    productsRemainder: [
                        { product: 'Ноутбук Dell XPS 15', warehouse: 'Основной склад', remainder: 15 },
                        { product: 'Клавиатура механическая', warehouse: 'Основной склад', remainder: 42 },
                        { product: 'Монитор 27" 4K', warehouse: 'Основной склад', remainder: 25 }
                    ],
                    contractorSettlements: [
                        { contractor: 'ООО "ТехноПоставщик"', debt: -450000, currency: 'RUB' },
                        { contractor: 'ООО "КлиентПро"', debt: 125000, currency: 'RUB' }
                    ]
                },
                edgeCases: [
                    { 
                        name: 'Пустое наименование товара', 
                        sku: 'EMPTY-NAME', 
                        price: 100, 
                        stock: 1, 
                        testType: 'validation_error',
                        expectedError: 'Не заполнено наименование товара'
                    },
                    { 
                        name: 'Товар с очень длинным наименованием', 
                        sku: 'LONG-NAME', 
                        price: 100, 
                        stock: 1, 
                        testType: 'boundary_condition',
                        expectedError: null
                    },
                    { 
                        name: 'Дубликат артикула', 
                        sku: 'DELL-XPS-15-001', 
                        price: 100, 
                        stock: 1, 
                        testType: 'uniqueness_violation',
                        expectedError: 'Артикул не уникален'
                    },
                    { 
                        name: 'Отрицательная цена', 
                        sku: 'UNIQUE-001', 
                        price: -100, 
                        stock: 1, 
                        testType: 'business_rule_violation',
                        expectedError: 'Цена должна быть положительной'
                    },
                    { 
                        name: 'Отрицательный остаток в документе', 
                        sku: 'UNIQUE-002', 
                        price: 100, 
                        stock: -5, 
                        testType: 'accounting_error',
                        expectedError: 'Количество должно быть положительным'
                    },
                    { 
                        name: 'Некорректный ИНН поставщика', 
                        inn: '123', 
                        kpp: '123456001', 
                        testType: 'validation_error',
                        expectedError: 'Некорректный формат ИНН'
                    }
                ],
                integrationData: {
                    exchangeFormats: ['CommerceML', '1CClientBankExchange', 'BOSystemExchange'],
                    webServices: [
                        { name: 'Доставка', endpoint: 'https://delivery-api.example.com', status: 'active' },
                        { name: 'Платежи', endpoint: 'https://payment-api.example.com', status: 'active' }
                    ]
                }
            };
            
            finalResult = {
                testData,
                statistics: {
                    totalRecords: 1000,
                    referenceRecords: 156,
                    documentRecords: 45,
                    registerRecords: 89,
                    edgeCases: 6,
                    integrationRecords: 12
                },
                coverage: {
                    scenarios: 95,
                    businessProcesses: 8,
                    dataTypes: ['normal', 'edge', 'boundary', 'invalid', 'integration'],
                    automation: 87
                },
                categories: {
                    referenceData: {
                        products: 5,
                        contractors: 3,
                        units: 2,
                        taxes: 1
                    },
                    documents: {
                        income: 1,
                        expense: 1,
                        total: 2
                    },
                    registers: {
                        productRemainders: 3,
                        contractorSettlements: 2,
                        total: 5
                    },
                    edgeCases: {
                        validationErrors: 3,
                        businessRuleViolations: 2,
                        boundaryConditions: 1
                    }
                }
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Тестовые данные для 1С готовы: 1000 записей, покрывают 95% сценариев, автоматизация 87%',
                result: finalResult
            });
            
        } else if (demoType === 'coverage') {
            steps.push({ progress: 10, message: 'Запуск анализа покрытия...' });
            await new Promise(r => setTimeout(r, 500));
            
            steps.push({ progress: 30, message: 'Анализ кодовой базы...' });
            await new Promise(r => setTimeout(r, 1000));
            
            steps.push({ progress: 65, message: 'Оценка покрытия тестами...' });
            await new Promise(r => setTimeout(r, 900));
            
            steps.push({ progress: 90, message: 'Выявление непокрытых областей...' });
            await new Promise(r => setTimeout(r, 700));
            
            finalResult = {
                coverage: {
                    modules: {
                        documents: { covered: 92, total: 450, percentage: 92 },
                        reference: { covered: 95, total: 320, percentage: 95 },
                        reports: { covered: 78, total: 180, percentage: 78 },
                        registers: { covered: 88, total: 290, percentage: 88 },
                        businessProcesses: { covered: 85, total: 410, percentage: 85 },
                        integration: { covered: 72, total: 150, percentage: 72 }
                    },
                    overall: {
                        lines: 87,
                        functions: 92,
                        branches: 78,
                        statements: 89,
                        modules: 84
                    }
                },
                uncoveredAreas: [
                    { 
                        module: 'Документы.ПриходТовара', 
                        function: 'ОбработкаПроверкиЗаполнения', 
                        lines: 12,
                        type: 'business_logic',
                        priority: 'high',
                        impact: 'Может привести к некорректным проводкам'
                    },
                    { 
                        module: 'Обработки.ЗагрузкаДанных', 
                        function: 'ПередЗаписью', 
                        lines: 8,
                        type: 'data_validation',
                        priority: 'critical',
                        impact: 'Повреждение данных при загрузке'
                    },
                    { 
                        module: 'Отчеты.Себестоимость', 
                        function: 'Рассчитать', 
                        lines: 15,
                        type: 'calculation',
                        priority: 'high',
                        impact: 'Неточные финансовые показатели'
                    },
                    { 
                        module: 'Регистры.ПартииТоваров', 
                        function: 'Движение', 
                        lines: 6,
                        type: 'accounting',
                        priority: 'medium',
                        impact: 'Неправильный учет партий'
                    },
                    { 
                        module: 'ОбщиеМодули.ОбменДанными', 
                        function: 'Синхронизация', 
                        lines: 10,
                        type: 'integration',
                        priority: 'high',
                        impact: 'Потеря синхронизации с внешними системами'
                    }
                ],
                criticalGaps: 5,
                totalGaps: 23,
                recommendations: [
                    {
                        priority: 'critical',
                        action: 'Добавить валидацию данных при загрузке',
                        estimated_effort: '3 дня',
                        business_impact: 'Высокий'
                    },
                    {
                        priority: 'high',
                        action: 'Покрыть тестами проверку заполнения документов',
                        estimated_effort: '2 дня',
                        business_impact: 'Высокий'
                    },
                    {
                        priority: 'high',
                        action: 'Протестировать расчет себестоимости',
                        estimated_effort: '4 дня',
                        business_impact: 'Критический'
                    },
                    {
                        priority: 'medium',
                        action: 'Добавить тесты для интеграционных процессов',
                        estimated_effort: '5 дней',
                        business_impact: 'Средний'
                    },
                    {
                        priority: 'low',
                        action: 'Повысить покрытие регистров до 95%',
                        estimated_effort: '2 дня',
                        business_impact: 'Низкий'
                    }
                ]
            };
            
            steps.push({ 
                progress: 100, 
                message: '✅ Анализ покрытия завершен: 84% по модулям, выявлено 5 критических пробелов',
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
        console.error('Tester demo error:', error);

        return new Response(JSON.stringify({
            error: {
                code: 'TESTER_DEMO_ERROR',
                message: error.message
            }
        }), {
            status: 500,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
    }
});
