
#!/usr/bin/env python3
"""
Parser Integration Module
Объединяет все оптимизированные парсеры в единый интерфейс

Использует:
- OptimizedXMLParser для конфигураций
- BSLASTParser для BSL кода
- Кеширование через Redis
- Инкрементальный парсинг

Версия: 1.0.0
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from scripts.parsers.bsl_ast_parser import BSLASTParser
    from scripts.parsers.optimized_xml_parser import OptimizedXMLParser
    from src.services.configuration_knowledge_base import get_knowledge_base
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    sys.exit(1)

# Optional: Redis для кеширования
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("[WARN] Redis not available, caching disabled")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegratedParser:
    """
    Интегрированный парсер с всеми оптимизациями
    
    Features:
    - Оптимизированный XML парсинг (lxml streaming)
    - AST парсинг BSL кода
    - Инкрементальный парсинг
    - Redis кеширование
    - Параллельная обработка
    """
    
    def __init__(
        self,
        use_ast: bool = True,
        use_redis: bool = True,
        incremental: bool = True,
        redis_url: str = "redis://localhost:6380"
    ):
        """
        Args:
            use_ast: Использовать AST парсинг для BSL
            use_redis: Использовать Redis для кеширования
            incremental: Использовать инкрементальный парсинг
            redis_url: URL Redis сервера
        """
        # XML Parser
        self.xml_parser = OptimizedXMLParser(enable_incremental=incremental)
        
        # BSL AST Parser
        self.use_ast = use_ast
        if use_ast:
            try:
                self.bsl_parser = BSLASTParser(use_language_server=True)
                logger.info("✅ AST парсинг включен")
            except Exception as e:
                logger.warning(f"⚠️ AST парсинг недоступен: {e}")
                logger.warning("Используется fallback regex parser")
                self.use_ast = False
                from scripts.parsers.improve_bsl_parser import \
                    ImprovedBSLParser
                self.bsl_parser = ImprovedBSLParser()
        else:
            from scripts.parsers.improve_bsl_parser import ImprovedBSLParser
            self.bsl_parser = ImprovedBSLParser()
        
        # Redis Cache
        self.use_redis = use_redis and REDIS_AVAILABLE
        self.redis_client = None
        
        if self.use_redis:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("✅ Redis кеш доступен")
            except Exception as e:
                logger.warning(f"⚠️ Redis недоступен: {e}")
                self.use_redis = False
        
        # Stats
        self.stats = {
            'total_configs': 0,
            'total_modules': 0,
            'total_functions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'parse_time': 0.0
        }
        
        # Knowledge Base
        self.kb = get_knowledge_base()
    
    async def parse_all_configurations(
        self,
        config_dir: Path = None,
        parallel: bool = True
    ) -> Dict[str, Any]:
        """
        Парсинг всех конфигураций с максимальной оптимизацией
        
        Args:
            config_dir: Директория с конфигурациями
            parallel: Использовать параллельную обработку
        
        Returns:
            Результаты парсинга всех конфигураций
        """
        if config_dir is None:
            config_dir = Path("./1c_configurations")
        
        logger.info("=" * 70)
        logger.info("INTEGRATED PARSER - OPTIMIZED MODE")
        logger.info("=" * 70)
        logger.info(f"AST Parsing: {'✅ Enabled' if self.use_ast else '❌ Disabled'}")
        logger.info(f"Redis Cache: {'✅ Enabled' if self.use_redis else '❌ Disabled'}")
        logger.info(f"Incremental: {'✅ Enabled' if self.xml_parser.enable_incremental else '❌ Disabled'}")
        logger.info(f"Parallel: {'✅ Enabled' if parallel else '❌ Disabled'}")
        logger.info("=" * 70)
        
        # Находим все конфигурации
        config_files = list(config_dir.rglob("config.xml"))
        logger.info(f"\n📁 Найдено конфигураций: {len(config_files)}")
        
        start_time = datetime.now()
        
        if parallel and len(config_files) > 1:
            # Параллельная обработка
            results = await self._parse_configs_parallel(config_files)
        else:
            # Последовательная обработка
            results = await self._parse_configs_sequential(config_files)
        
        total_time = (datetime.now() - start_time).total_seconds()
        self.stats['parse_time'] = total_time
        
        # Сохраняем хеши для incremental parsing
        if self.xml_parser.enable_incremental:
            self.xml_parser._save_hashes()
        
        # Итоги
        logger.info("\n" + "=" * 70)
        logger.info("ИТОГИ ПАРСИНГА:")
        logger.info("=" * 70)
        logger.info(f"Время: {total_time:.1f} сек ({total_time/60:.1f} мин)")
        logger.info(f"Конфигураций: {self.stats['total_configs']}")
        logger.info(f"Модулей: {self.stats['total_modules']}")
        logger.info(f"Функций: {self.stats['total_functions']}")
        
        if self.use_redis:
            logger.info(f"Cache hits: {self.stats['cache_hits']}")
            logger.info(f"Cache misses: {self.stats['cache_misses']}")
            hit_rate = self.stats['cache_hits'] / max(1, self.stats['cache_hits'] + self.stats['cache_misses']) * 100
            logger.info(f"Cache hit rate: {hit_rate:.1f}%")
        
        logger.info(f"Скорость: {self.stats['total_modules']/total_time:.1f} модулей/сек")
        logger.info("=" * 70)
        
        return {
            'status': 'success',
            'stats': self.stats,
            'results': results
        }
    
    async def _parse_configs_parallel(
        self,
        config_files: List[Path]
    ) -> List[Dict[str, Any]]:
        """Параллельная обработка конфигураций"""
        
        logger.info("🔄 Параллельная обработка...")
        
        # Создаем задачи
        tasks = []
        for config_file in config_files:
            config_name = config_file.parent.name.upper()
            task = self._parse_single_config(config_name, config_file)
            tasks.append(task)
        
        # Выполняем параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Фильтруем ошибки
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Ошибка парсинга {config_files[i].name}: {result}")
            else:
                valid_results.append(result)
        
        return valid_results
    
    async def _parse_configs_sequential(
        self,
        config_files: List[Path]
    ) -> List[Dict[str, Any]]:
        """Последовательная обработка конфигураций"""
        
        logger.info("➡️  Последовательная обработка...")
        
        results = []
        for config_file in config_files:
            config_name = config_file.parent.name.upper()
            result = await self._parse_single_config(config_name, config_file)
            results.append(result)
        
        return results
    
    async def _parse_single_config(
        self,
        config_name: str,
        config_file: Path
    ) -> Dict[str, Any]:
        """Парсинг одной конфигурации"""
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📦 {config_name}")
        logger.info(f"{'='*70}")
        
        modules_saved = 0
        modules_skipped = 0
        
        # Streaming парсинг XML
        for module in self.xml_parser.parse_configuration_streaming(config_name, config_file):
            # Проверяем кеш
            if self.use_redis:
                cached = self._get_from_cache(module['name'])
                if cached:
                    self.stats['cache_hits'] += 1
                    modules_skipped += 1
                    continue
                else:
                    self.stats['cache_misses'] += 1
            
            # Парсим BSL с AST (если включено)
            if self.use_ast and module.get('code'):
                try:
                    ast_result = self.bsl_parser.parse(module['code'])
                    
                    # Обогащаем модуль AST данными
                    module['ast'] = ast_result.get('ast')
                    module['control_flow'] = ast_result.get('control_flow')
                    module['data_flow'] = ast_result.get('data_flow')
                    module['complexity'] = ast_result.get('complexity')
                    module['diagnostics'] = ast_result.get('diagnostics', [])
                    
                    # Обновляем функции с AST
                    module['functions'] = ast_result.get('functions', module.get('functions', []))
                    module['procedures'] = ast_result.get('procedures', module.get('procedures', []))
                    
                except Exception as e:
                    logger.warning(f"AST парсинг не удался для {module['name']}: {e}")
            
            # Сохраняем в базу знаний
            try:
                self.xml_parser.save_module_to_kb(module, config_name)
                
                # Сохраняем в кеш
                if self.use_redis:
                    self._save_to_cache(module['name'], module)
                
                modules_saved += 1
                self.stats['total_modules'] += 1
                self.stats['total_functions'] += module.get('functions_count', 0)
                
            except Exception as e:
                logger.error(f"Ошибка сохранения модуля {module['name']}: {e}")
        
        self.stats['total_configs'] += 1
        
        logger.info(f"✅ {config_name}: {modules_saved} сохранено, {modules_skipped} пропущено")
        
        return {
            'config_name': config_name,
            'modules_saved': modules_saved,
            'modules_skipped': modules_skipped
        }
    
    def _get_from_cache(self, module_name: str) -> Optional[Dict]:
        """Получение из Redis кеша"""
        if not self.use_redis or not self.redis_client:
            return None
        
        try:
            cached = self.redis_client.get(f"module:{module_name}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        
        return None
    
    def _save_to_cache(self, module_name: str, module_data: Dict):
        """Сохранение в Redis кеш"""
        if not self.use_redis or not self.redis_client:
            return
        
        try:
            # Убираем AST из кеша (слишком большой)
            cache_data = module_data.copy()
            cache_data.pop('ast', None)
            cache_data.pop('control_flow', None)
            cache_data.pop('data_flow', None)
            
            # TTL 1 день
            self.redis_client.setex(
                f"module:{module_name}",
                86400,
                json.dumps(cache_data, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"Cache write error: {e}")


async def main():
    """Main entry point"""
    
    # Создаем интегрированный парсер
    parser = IntegratedParser(
        use_ast=True,
        use_redis=True,
        incremental=True
    )
    
    # Парсим все конфигурации
    result = await parser.parse_all_configurations(parallel=True)
    
    if result['status'] == 'success':
        print("\n✅ Парсинг успешно завершен!")
        print(f"📊 Статистика сохранена в результате")
    else:
        print(f"\n❌ Ошибка парсинга: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())




