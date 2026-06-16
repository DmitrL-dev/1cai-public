
"""
Примеры использования AI Code Review Agent
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from src.ai.agents.code_review.ai_reviewer import AICodeReviewer


async def example_1_basic_review():
    """Пример 1: Базовый review файла"""
    
    print("="*70)
    print("EXAMPLE 1: Basic Code Review")
    print("="*70)
    
    reviewer = AICodeReviewer()
    
    # Код с проблемами
    code_with_issues = '''
Функция ПолучитьДанныеКлиента(ИмяКлиента)
    
    // SQL Injection vulnerability!
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Контрагенты ГДЕ Наименование = \\"" + ИмяКлиента + "\\"";
    
    Результат = Запрос.Выполнить();  // No error handling!
    
    Возврат Результат;
    
КонецФункции
'''
    
    result = await reviewer.review_code(code_with_issues, "test.bsl")
    
    print("\n" + result['summary'])
    print(f"\nTotal issues found: {result['total_issues']}")
    print(f"Overall status: {result['overall_status']}")
    
    print("\n--- Security Issues ---")
    for issue in result['issues']['security']:
        print(f"  [{issue['severity']}] {issue['message']} (line {issue['line']})")
    
    print("="*70)


async def example_2_good_code():
    """Пример 2: Хороший код без проблем"""
    
    print("\n" + "="*70)
    print("EXAMPLE 2: Good Code (No Issues)")
    print("="*70)
    
    reviewer = AICodeReviewer()
    
    # Правильный код
    good_code = '''
// Получает данные клиента по ID
//
// Параметры:
//   КлиентID - УникальныйИдентификатор - ID клиента
//
// Возвращаемое значение:
//   Структура - Данные клиента или Неопределено
//
Функция ПолучитьДанныеКлиента(КлиентID) Экспорт
    
    Попытка
        Запрос = Новый Запрос;
        Запрос.Текст = "
        |ВЫБРАТЬ
        |    Контрагенты.Наименование,
        |    Контрагенты.ИНН,
        |    Контрагенты.Адрес
        |ИЗ
        |    Справочник.Контрагенты КАК Контрагенты
        |ГДЕ
        |    Контрагенты.Ссылка = &КлиентID";
        
        Запрос.УстановитьПараметр("КлиентID", КлиентID);
        
        Результат = Запрос.Выполнить();
        
        Если Результат.Пустой() Тогда
            Возврат Неопределено;
        КонецЕсли;
        
        Выборка = Результат.Выбрать();
        Выборка.Следующий();
        
        ДанныеКлиента = Новый Структура;
        ДанныеКлиента.Вставить("Наименование", Выборка.Наименование);
        ДанныеКлиента.Вставить("ИНН", Выборка.ИНН);
        ДанныеКлиента.Вставить("Адрес", Выборка.Адрес);
        
        Возврат ДанныеКлиента;
        
    Исключение
        ЗаписьЖурналаРегистрации(
            "Ошибка получения данных клиента",
            УровеньЖурналаРегистрации.Ошибка,
            ,
            ,
            ПодробноеПредставлениеОшибки(ИнформацияОбОшибке())
        );
        
        Возврат Неопределено;
    КонецПопытки;
    
КонецФункции
'''
    
    result = await reviewer.review_code(good_code, "good_example.bsl")
    
    print("\n" + result['summary'])
    print(f"\nTotal issues found: {result['total_issues']}")
    print(f"Overall status: {result['overall_status']}")
    
    if result['total_issues'] == 0:
        print("\n✨ Perfect code! No issues found!")
    
    print("="*70)


async def example_3_pr_review():
    """Пример 3: Review всего Pull Request"""
    
    print("\n" + "="*70)
    print("EXAMPLE 3: Pull Request Review")
    print("="*70)
    
    reviewer = AICodeReviewer()
    
    # Симуляция PR с несколькими файлами
    files_changed = [
        {
            'filename': 'src/ПродажиСервер.bsl',
            'content': '''
Функция РассчитатьСуммуЗаказа(Заказ)
    Сумма = 0;
    
    // N+1 problem!
    Для Каждого Строка Из Заказ.Товары Цикл
        Запрос = Новый Запрос;
        Запрос.Текст = "ВЫБРАТЬ Цена ГДЕ Товар = &Товар";
        Запрос.УстановитьПараметр("Товар", Строка.Товар);
        Цена = Запрос.Выполнить().Выгрузить()[0].Цена;
        
        Сумма = Сумма + Цена * Строка.Количество;
    КонецЦикла;
    
    Возврат Сумма;
КонецФункции
'''
        },
        {
            'filename': 'src/HTTPСервис.bsl',
            'content': '''
Функция ОбработкаЗапроса(Запрос)
    
    ПараметрИмя = Запрос.ПолучитьПараметрЗапроса("имя");
    
    // XSS vulnerability!
    Ответ = Новый HTTPСервисОтвет(200);
    Ответ.УстановитьТелоИзСтроки("<html><body>Привет, " + ПараметрИмя + "!</body></html>");
    
    Возврат Ответ;
    
КонецФункции
'''
        }
    ]
    
    result = await reviewer.review_pull_request(files_changed)
    
    print("\n" + result['summary'])
    print("\n--- Metrics ---")
    print(f"Files reviewed: {result['metrics']['files_reviewed']}")
    print(f"Total issues: {result['metrics']['total_issues']}")
    print(f"  Critical: {result['metrics']['critical']}")
    print(f"  High: {result['metrics']['high']}")
    print(f"  Medium: {result['metrics']['medium']}")
    print(f"  Low: {result['metrics']['low']}")
    
    print("\n--- Issues by File ---")
    for file_review in result['file_reviews']:
        print(f"\n{file_review['filename']}:")
        print(f"  Total issues: {file_review['total_issues']}")
    
    print("="*70)


async def main():
    """Запуск всех примеров"""
    
    print("="*70)
    print("   AI Code Review Agent - Examples")
    print("="*70)
    
    await example_1_basic_review()
    await example_2_good_code()
    await example_3_pr_review()
    
    print("\n" + "="*70)
    print("[SUCCESS] All examples completed!")
    print("="*70)
    print("\nAI Code Review features demonstrated:")
    print("  [OK] Security scanning - SQL injection, XSS, credentials")
    print("  [OK] Performance analysis - N+1 queries, slow loops")
    print("  [OK] Best practices - naming, error handling")
    print("  [OK] Pull Request review - multi-file analysis")
    print("\nReady for production use!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())


