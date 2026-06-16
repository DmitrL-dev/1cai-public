
#!/usr/bin/env python3
"""
Тестирование оптимизированных парсеров
Сравнение производительности старого и нового подходов

Запуск:
    python scripts/test_parser_optimization.py
    python scripts/test_parser_optimization.py --benchmark
    python scripts/test_parser_optimization.py --full
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psutil

    from scripts.parsers.parse_1c_config_fixed import Fixed1CConfigParser
    from scripts.parsers.parser_integration import IntegratedParser
    PSUTIL_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] {e}")
    PSUTIL_AVAILABLE = False


class ParserBenchmark:
    """Benchmark comparison между старым и новым парсером"""
    
    def __init__(self):
        self.results = {
            'old_parser': {},
            'new_parser': {},
            'comparison': {}
        }
    
    def measure_memory(self):
        """Измерение текущего использования памяти"""
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # MB
        return 0
    
    async def benchmark_old_parser(self, config_file: Path) -> Dict:
        """Benchmark старого парсера"""
        print("\n" + "=" * 70)
        print("BENCHMARK: Старый парсер (Fixed1CConfigParser)")
        print("=" * 70)
        
        config_name = config_file.parent.name.upper()
        
        # Измеряем память до
        mem_before = self.measure_memory()
        
        # Засекаем время
        start_time = time.time()
        
        try:
            parser = Fixed1CConfigParser()
            result = parser.parse_configuration(config_name, config_file)
            
            parse_time = time.time() - start_time
            mem_after = self.measure_memory()
            mem_used = mem_after - mem_before
            
            stats = {
                'time': parse_time,
                'memory_mb': mem_used,
                'modules': len(result.get('modules', [])),
                'status': result.get('status', 'unknown')
            }
            
            print(f"⏱️  Время: {parse_time:.2f} сек")
            print(f"💾 Память: {mem_used:.1f} MB")
            print(f"📦 Модулей: {stats['modules']}")
            
            self.results['old_parser'] = stats
            return stats
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return {'error': str(e)}
    
    async def benchmark_new_parser(
        self,
        config_file: Path,
        use_ast: bool = True,
        use_redis: bool = False
    ) -> Dict:
        """Benchmark нового оптимизированного парсера"""
        print("\n" + "=" * 70)
        print("BENCHMARK: Новый парсер (IntegratedParser)")
        print("=" * 70)
        print(f"AST: {'✅' if use_ast else '❌'}")
        print(f"Redis: {'✅' if use_redis else '❌'}")
        
        config_name = config_file.parent.name.upper()
        
        # Измеряем память до
        mem_before = self.measure_memory()
        
        # Засекаем время
        start_time = time.time()
        
        try:
            parser = IntegratedParser(
                use_ast=use_ast,
                use_redis=use_redis,
                incremental=False  # Для честного сравнения
            )
            
            # Парсим одну конфигурацию
            modules_count = 0
            for module in parser.xml_parser.parse_configuration_streaming(
                config_name, config_file
            ):
                modules_count += 1
            
            parse_time = time.time() - start_time
            mem_after = self.measure_memory()
            mem_used = mem_after - mem_before
            
            stats = {
                'time': parse_time,
                'memory_mb': mem_used,
                'modules': modules_count,
                'status': 'success'
            }
            
            print(f"⏱️  Время: {parse_time:.2f} сек")
            print(f"💾 Память: {mem_used:.1f} MB")
            print(f"📦 Модулей: {stats['modules']}")
            
            self.results['new_parser'] = stats
            return stats
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def compare_results(self):
        """Сравнение результатов"""
        print("\n" + "=" * 70)
        print("СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
        print("=" * 70)
        
        old = self.results.get('old_parser', {})
        new = self.results.get('new_parser', {})
        
        if not old or not new or 'error' in old or 'error' in new:
            print("❌ Недостаточно данных для сравнения")
            return
        
        # Сравнение времени
        time_old = old.get('time', 0)
        time_new = new.get('time', 0)
        
        if time_new > 0:
            speedup = time_old / time_new
            time_saved = time_old - time_new
            time_saved_pct = (time_saved / time_old) * 100 if time_old > 0 else 0
            
            print(f"\n⏱️  ВРЕМЯ:")
            print(f"  Старый парсер: {time_old:.2f} сек")
            print(f"  Новый парсер:  {time_new:.2f} сек")
            print(f"  Ускорение:     {speedup:.2f}x")
            print(f"  Экономия:      {time_saved:.2f} сек ({time_saved_pct:.1f}%)")
        
        # Сравнение памяти
        mem_old = old.get('memory_mb', 0)
        mem_new = new.get('memory_mb', 0)
        
        if mem_old > 0 and mem_new > 0:
            mem_reduction = mem_old / mem_new
            mem_saved = mem_old - mem_new
            mem_saved_pct = (mem_saved / mem_old) * 100
            
            print(f"\n💾 ПАМЯТЬ:")
            print(f"  Старый парсер: {mem_old:.1f} MB")
            print(f"  Новый парсер:  {mem_new:.1f} MB")
            print(f"  Снижение:      {mem_reduction:.2f}x")
            print(f"  Экономия:      {mem_saved:.1f} MB ({mem_saved_pct:.1f}%)")
        
        # Сравнение результатов
        modules_old = old.get('modules', 0)
        modules_new = new.get('modules', 0)
        
        print(f"\n📦 РЕЗУЛЬТАТЫ:")
        print(f"  Старый парсер: {modules_old} модулей")
        print(f"  Новый парсер:  {modules_new} модулей")
        
        if modules_old == modules_new:
            print(f"  ✅ Результаты идентичны")
        else:
            diff = abs(modules_old - modules_new)
            print(f"  ⚠️  Разница: {diff} модулей")
        
        # Итоговая оценка
        print(f"\n🎯 ИТОГОВАЯ ОЦЕНКА:")
        if speedup > 1:
            print(f"  ✅ Новый парсер БЫСТРЕЕ на {speedup:.1f}x")
        else:
            print(f"  ⚠️  Новый парсер медленнее")
        
        if mem_reduction > 1:
            print(f"  ✅ Новый парсер использует МЕНЬШЕ памяти на {mem_reduction:.1f}x")
        else:
            print(f"  ⚠️  Новый парсер использует больше памяти")
        
        # Сохраняем сравнение
        self.results['comparison'] = {
            'speedup': speedup if time_new > 0 else 0,
            'memory_reduction': mem_reduction if mem_new > 0 else 0,
            'time_saved_sec': time_saved if time_new > 0 else 0,
            'memory_saved_mb': mem_saved if mem_new > 0 else 0
        }
    
    def save_results(self, output_file: Path):
        """Сохранение результатов benchmark"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Результаты сохранены: {output_file}")


async def quick_test():
    """Быстрый тест базовой функциональности"""
    print("=" * 70)
    print("QUICK TEST: Базовая функциональность")
    print("=" * 70)
    
    # Тест 1: OptimizedXMLParser
    print("\n[TEST 1] OptimizedXMLParser")
    try:
        from scripts.parsers.optimized_xml_parser import OptimizedXMLParser
        parser = OptimizedXMLParser()
        print("  ✅ OptimizedXMLParser импортирован")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
    
    # Тест 2: BSLASTParser
    print("\n[TEST 2] BSLASTParser")
    try:
        from scripts.parsers.bsl_ast_parser import BSLASTParser
        parser = BSLASTParser(use_language_server=False)  # Fallback
        print("  ✅ BSLASTParser импортирован")
        
        # Тестовый код
        test_code = "Функция Тест()\n  Возврат 1;\nКонецФункции"
        result = parser.parse(test_code)
        print(f"  ✅ Парсинг работает: {len(result['functions'])} функций")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
    
    # Тест 3: IntegratedParser
    print("\n[TEST 3] IntegratedParser")
    try:
        from scripts.parsers.parser_integration import IntegratedParser
        parser = IntegratedParser(use_ast=False, use_redis=False)
        print("  ✅ IntegratedParser импортирован")
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
    
    # Тест 4: BSL Language Server доступность
    print("\n[TEST 4] BSL Language Server")
    try:
        import requests
        response = requests.get("http://localhost:8080/actuator/health", timeout=2)
        if response.status_code == 200:
            print("  ✅ BSL Language Server доступен")
        else:
            print(f"  ⚠️  BSL LS вернул статус {response.status_code}")
    except Exception as e:
        print(f"  ❌ BSL Language Server недоступен: {e}")
        print("  💡 Запустите: docker-compose -f docker-compose.parser.yml up -d")
    
    # Тест 5: Redis доступность
    print("\n[TEST 5] Redis Cache")
    try:
        import redis
        client = redis.from_url("redis://localhost:6380", socket_connect_timeout=2)
        client.ping()
        print("  ✅ Redis доступен")
    except Exception as e:
        print(f"  ❌ Redis недоступен: {e}")
        print("  💡 Запустите: docker-compose -f docker-compose.parser.yml up -d")


async def full_benchmark():
    """Полный benchmark на реальных данных"""
    print("=" * 70)
    print("FULL BENCHMARK: Реальные данные")
    print("=" * 70)
    
    # Находим конфигурацию для теста
    config_dir = Path("./1c_configurations")
    config_files = list(config_dir.rglob("config.xml"))
    
    if not config_files:
        print("❌ Конфигурации не найдены в ./1c_configurations")
        return
    
    # Берем первую конфигурацию
    config_file = config_files[0]
    print(f"\n📁 Тестовая конфигурация: {config_file.parent.name}")
    print(f"📊 Размер файла: {config_file.stat().st_size / 1024 / 1024:.1f} MB")
    
    benchmark = ParserBenchmark()
    
    # Benchmark старого парсера
    await benchmark.benchmark_old_parser(config_file)
    
    # Небольшая пауза для очистки памяти
    await asyncio.sleep(2)
    
    # Benchmark нового парсера
    await benchmark.benchmark_new_parser(config_file, use_ast=False, use_redis=False)
    
    # Сравнение
    benchmark.compare_results()
    
    # Сохранение результатов
    output_file = Path("./benchmark_results.json")
    benchmark.save_results(output_file)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test Parser Optimization")
    parser.add_argument('--quick', action='store_true', help='Quick functionality test')
    parser.add_argument('--benchmark', action='store_true', help='Full benchmark')
    parser.add_argument('--full', action='store_true', help='All tests')
    
    args = parser.parse_args()
    
    if args.full or (not args.quick and not args.benchmark):
        # По умолчанию - все тесты
        await quick_test()
        print("\n")
        await full_benchmark()
    elif args.quick:
        await quick_test()
    elif args.benchmark:
        await full_benchmark()


if __name__ == "__main__":
    asyncio.run(main())




