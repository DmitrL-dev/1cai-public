
#!/usr/bin/env python3
"""
Простое тестирование BSL парсера
Без emoji, без проблем с кодировкой
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.parsers.improve_bsl_parser import ImprovedBSLParser


def test_parser_performance():
    """Тест производительности парсера"""
    
    print("=" * 70)
    print("ТЕСТ ПРОИЗВОДИТЕЛЬНОСТИ BSL ПАРСЕРА")
    print("=" * 70)
    
    # Тестовый код (реалистичный)
    test_code = """
#Область ПрограммныйИнтерфейс

Функция ПолучитьСписокКлиентов(ТолькоАктивные = Истина) Экспорт
    
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Клиенты";
    
    Результат = Запрос.Выполнить();
    Возврат Результат;
    
КонецФункции

Функция РассчитатьСкидку(Сумма, Количество) Экспорт
    
    Если Количество > 10 Тогда
        СуммаСкидки = Сумма * 0.15;
    ИначеЕсли Количество > 5 Тогда
        СуммаСкидки = Сумма * 0.10;
    Иначе
        СуммаСкидки = Сумма * 0.05;
    КонецЕсли;
    
    Возврат СуммаСкидки;
    
КонецФункции

Процедура ОбработатьДокумент(Документ) Экспорт
    
    Для Каждого Строка Из Документ.Товары Цикл
        Строка.Сумма = Строка.Количество * Строка.Цена;
    КонецЦикла;
    
    Попытка
        Документ.Записать();
    Исключение
        ВызватьИсключение "Ошибка записи";
    КонецПопытки;
    
КонецПроцедуры

#КонецОбласти
    """
    
    # Дублируем для более реального теста
    test_code = test_code * 20  # 60 функций
    
    print(f"\nТестовый код: {len(test_code)} символов")
    print(f"Строк: {len(test_code.split(chr(10)))}")
    
    # Создаем парсер
    parser = ImprovedBSLParser()
    
    # Прогреваем (первый запуск может быть медленнее)
    parser.parse(test_code)
    
    # Реальный тест (3 прогона)
    times = []
    for i in range(3):
        start = time.time()
        result = parser.parse(test_code)
        elapsed = time.time() - start
        times.append(elapsed)
        
        print(f"\nПрогон {i+1}:")
        print(f"  Время: {elapsed:.4f} сек")
        print(f"  Функций: {len(result['functions'])}")
        print(f"  Процедур: {len(result['procedures'])}")
        print(f"  Областей: {len(result['regions'])}")
        print(f"  API usage: {len(result['api_usage'])}")
    
    # Среднее время
    avg_time = sum(times) / len(times)
    
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 70)
    print(f"Среднее время: {avg_time:.4f} сек")
    print(f"Скорость: {len(result['functions']) / avg_time:.1f} функций/сек")
    
    # Сохраняем baseline
    with open('baseline_performance.txt', 'w') as f:
        f.write(f"Baseline Performance\n")
        f.write(f"===================\n")
        f.write(f"Time: {avg_time:.4f} sec\n")
        f.write(f"Functions: {len(result['functions'])}\n")
        f.write(f"Speed: {len(result['functions']) / avg_time:.1f} funcs/sec\n")
    
    print("\nBaseline сохранен: baseline_performance.txt")
    
    return avg_time, result


if __name__ == "__main__":
    test_parser_performance()




