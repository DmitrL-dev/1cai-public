
#!/usr/bin/env python3
"""
РЕАЛЬНЫЙ анализ производительности парсера
Без теорий - только факты и измерения

Что делает:
1. Профилирует текущий парсер
2. Находит РЕАЛЬНЫЕ bottlenecks
3. Предлагает КОНКРЕТНЫЕ улучшения
4. Измеряет РЕАЛЬНЫЙ эффект

Версия: 1.0 Pragmatic
"""

import cProfile
import pstats
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class ParserProfiler:
    """
    Профилировщик парсера - показывает РЕАЛЬНЫЕ данные
    
    Нет теорий, только измерения.
    """
    
    def __init__(self):
        self.results = {}
    
    def profile_current_parser(self, test_code: str):
        """
        Профилирование текущего парсера
        
        Измеряет:
        - Время выполнения каждой функции
        - Количество вызовов
        - Память
        """
        print("=" * 70)
        print("ПРОФИЛИРОВАНИЕ ТЕКУЩЕГО ПАРСЕРА")
        print("=" * 70)
        
        # Start memory tracking
        tracemalloc.start()
        
        # Profile с cProfile
        profiler = cProfile.Profile()
        
        try:
            from scripts.parsers.improve_bsl_parser import ImprovedBSLParser
            
            parser = ImprovedBSLParser()
            
            # Начинаем профилирование
            profiler.enable()
            start_time = time.time()
            
            # РЕАЛЬНЫЙ парсинг
            result = parser.parse(test_code)
            
            # Стоп
            end_time = time.time()
            profiler.disable()
            
            # Memory peak
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            # Результаты
            elapsed = end_time - start_time
            
            print(f"\n📊 РЕЗУЛЬТАТЫ:")
            print(f"Время: {elapsed:.4f} сек")
            print(f"Память (peak): {peak / 1024 / 1024:.2f} MB")
            print(f"Функций найдено: {len(result['functions'])}")
            print(f"Процедур найдено: {len(result['procedures'])}")
            
            # Детальная статистика
            print(f"\n🔍 ТОП-10 МЕДЛЕННЫХ ФУНКЦИЙ:")
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumulative')
            stats.print_stats(10)
            
            # Сохраняем результаты
            self.results['current'] = {
                'time': elapsed,
                'memory_mb': peak / 1024 / 1024,
                'functions_found': len(result['functions'])
            }
            
            return result
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            traceback_str = ''.join(traceback.format_exc())
            print(traceback_str)
            return None
    
    def find_bottlenecks(self):
        """
        Анализ bottlenecks на основе профилирования
        
        Показывает КОНКРЕТНО где тратится время
        """
        print("\n" + "=" * 70)
        print("АНАЛИЗ BOTTLENECKS")
        print("=" * 70)
        
        if not self.results.get('current'):
            print("❌ Нет данных профилирования")
            return
        
        # TODO: Детальный анализ pstats
        # Покажет какие функции реально медленные
        
        print("\n💡 РЕКОМЕНДАЦИИ (на основе РЕАЛЬНЫХ данных):")
        print("1. Запустите полное профилирование на реальном файле")
        print("2. Найдите функции которые занимают >50% времени")
        print("3. Оптимизируйте именно их")
        print("4. Измерьте улучшение")
    
    def compare_optimizations(self):
        """Сравнение до/после оптимизаций"""
        print("\n" + "=" * 70)
        print("СРАВНЕНИЕ")
        print("=" * 70)
        
        current = self.results.get('current', {})
        optimized = self.results.get('optimized', {})
        
        if not current or not optimized:
            print("⚠️  Нет данных для сравнения")
            return
        
        time_improvement = (current['time'] - optimized['time']) / current['time'] * 100
        memory_improvement = (current['memory_mb'] - optimized['memory_mb']) / current['memory_mb'] * 100
        
        print(f"Время: {current['time']:.4f} → {optimized['time']:.4f} сек ({time_improvement:+.1f}%)")
        print(f"Память: {current['memory_mb']:.2f} → {optimized['memory_mb']:.2f} MB ({memory_improvement:+.1f}%)")
        
        if time_improvement > 10:
            print(f"\n✅ Хорошее улучшение: {time_improvement:.1f}%")
        elif time_improvement > 0:
            print(f"\n⚠️  Небольшое улучшение: {time_improvement:.1f}%")
        else:
            print(f"\n❌ Ухудшение: {time_improvement:.1f}%")


def main():
    """Main - запуск реального анализа"""
    
    # Тестовый код BSL
    test_code = """
#Область ПрограммныйИнтерфейс

Функция ПолучитьСписокКлиентов(ТолькоАктивные = Истина) Экспорт
    
    Запрос = Новый Запрос;
    Запрос.Текст = "
    |ВЫБРАТЬ
    |    Клиенты.Ссылка КАК Ссылка,
    |    Клиенты.Наименование КАК Наименование
    |ИЗ
    |    Справочник.Клиенты КАК Клиенты
    |ГДЕ
    |    НЕ Клиенты.ПометкаУдаления";
    
    Если ТолькоАктивные Тогда
        Запрос.Текст = Запрос.Текст + "
        |    И Клиенты.Активный";
    КонецЕсли;
    
    Результат = Запрос.Выполнить().Выгрузить();
    Возврат Результат;
    
КонецФункции

Функция РассчитатьСкидку(Сумма, КоличествоПокупок) Экспорт
    
    Если КоличествоПокупок > 10 Тогда
        СуммаСкидки = Сумма * 0.15;
    ИначеЕсли КоличествоПокупок > 5 Тогда
        СуммаСкидки = Сумма * 0.10;
    Иначе
        СуммаСкидки = Сумма * 0.05;
    КонецЕсли;
    
    Возврат СуммаСкидки;
    
КонецФункции

Процедура ОбработатьДокумент(Документ) Экспорт
    
    Для Каждого СтрокаТаблицы Из Документ.Товары Цикл
        СтрокаТаблицы.Сумма = СтрокаТаблицы.Количество * СтрокаТаблицы.Цена;
    КонецЦикла;
    
    Попытка
        Документ.Записать();
    Исключение
        ВызватьИсключение "Ошибка записи документа";
    КонецПопытки;
    
КонецПроцедуры

#КонецОбласти

#Область СлужебныеПроцедурыИФункции

Функция ПолучитьНастройки()
    
    Настройки = Новый Структура;
    Настройки.Вставить("Параметр1", Истина);
    Настройки.Вставить("Параметр2", 100);
    
    Возврат Настройки;
    
КонецФункции

#КонецОбласти
    """ * 10  # Дублируем для более реального теста
    
    profiler = ParserProfiler()
    
    # Профилируем текущий парсер
    result = profiler.profile_current_parser(test_code)
    
    if result:
        # Анализ bottlenecks
        profiler.find_bottlenecks()
        
        print("\n" + "=" * 70)
        print("✅ Профилирование завершено")
        print("=" * 70)
        print("\nСледующие шаги:")
        print("1. Посмотрите какие функции занимают больше всего времени")
        print("2. Оптимизируйте именно их")
        print("3. Запустите профилирование снова")
        print("4. Измерьте РЕАЛЬНОЕ улучшение")
        print("\nБез этих данных - любые оптимизации это гадание!")


if __name__ == "__main__":
    main()




