
"""
Запуск сервера API администрирования кэша

Скрипт для запуска FastAPI сервера с различными конфигурациями
для разработки, тестирования и продакшена.
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    # Импорт конфигурации и приложения
    from config import (Environment, apply_environment_config, config,
                        validate_config)
    from main import app
except ImportError as e:
    logger.error(f"Ошибка импорта модулей: {e}")
    logger.error("Убедитесь, что все зависимости установлены и путь к проекту корректен")
    sys.exit(1)


class ServerManager:
    """Менеджер для управления сервером"""
    
    def __init__(self):
        self.server = None
        self.should_stop = False
    
    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для корректного завершения"""
        def signal_handler(signum, frame):
            logger.info(f"Получен сигнал {signum}. Завершение работы...")
            self.should_stop = True
            if self.server:
                self.server.should_exit = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run_server(self, env: Environment, **kwargs):
        """
        Запуск сервера с заданной конфигурацией
        
        Args:
            env: Окружение для запуска
            **kwargs: Дополнительные параметры для uvicorn
        """
        try:
            # Применяем настройки окружения
            apply_environment_config(env)
            
            # Валидация конфигурации
            validation_errors = validate_config()
            if validation_errors and env == Environment.PRODUCTION:
                logger.error("Ошибки валидации конфигурации для продакшена:")
                for error in validation_errors:
                    logger.error(f"  ❌ {error}")
                sys.exit(1)
            elif validation_errors:
                logger.warning("Предупреждения валидации конфигурации:")
                for error in validation_errors:
                    logger.warning(f"  ⚠️  {error}")
            
            # Настройки uvicorn
            uvicorn_config = {
                "app": app,
                "host": config.host,
                "port": config.port,
                "workers": config.workers if env == Environment.PRODUCTION else 1,
                "reload": config.reload and env == Environment.DEVELOPMENT,
                "log_level": "info",
                "access_log": True,
                "log_config": None,  # Используем наше логирование
                **kwargs
            }
            
            # Дополнительные настройки для продакшена
            if env == Environment.PRODUCTION:
                uvicorn_config.update({
                    "workers": config.workers,
                    "reload": False,
                    "access_log": True,
                    "use_colors": False,
                    "loop": "uvloop",  # Быстрее loop для продакшена
                })
            
            # Логирование запуска
            logger.info(f"Запуск {config.app_name} v{config.app_version}")
            logger.info(f"Окружение: {env.value}")
            logger.info(f"Хост: {config.host}:{config.port}")
            logger.info(f"Отладка: {config.debug}")
            logger.info(f"Автоперезагрузка: {config.reload}")
            logger.info(f"Воркеры: {config.workers}")
            
            # Создание логов директории если нужно
            log_dir = Path("logs")
            if not log_dir.exists():
                log_dir.mkdir(exist_ok=True)
                logger.info(f"Создана директория для логов: {log_dir}")
            
            # Запуск сервера
            self.server = uvicorn.Server(uvicorn.Config(**uvicorn_config))
            await self.server.serve()
            
        except KeyboardInterrupt:
            logger.info("Остановка сервера по запросу пользователя")
        except Exception as e:
            logger.error(f"Критическая ошибка запуска сервера: {e}")
            sys.exit(1)


async def run_health_check(port: int = 8000, host: str = "localhost"):
    """Запуск проверки здоровья сервера"""
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            url = f"http://{host}:{port}/health"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("✅ Сервер работает нормально")
                    logger.info(f"Статус: {data.get('status', 'unknown')}")
                    return True
                else:
                    logger.warning(f"⚠️  Сервер вернул статус: {response.status}")
                    return False
                    
    except Exception as e:
        logger.error(f"❌ Ошибка проверки здоровья: {e}")
        return False


def run_development_server():
    """Запуск сервера для разработки"""
    logger.info("🚀 Запуск сервера для разработки...")
    
    manager = ServerManager()
    manager.setup_signal_handlers()
    
    # Запуск в development окружении
    asyncio.run(manager.run_server(Environment.DEVELOPMENT))


def run_production_server():
    """Запуск сервера для продакшена"""
    logger.info("🏭 Запуск сервера для продакшена...")
    
    # Дополнительные проверки для продакшена
    if config.environment != Environment.PRODUCTION:
        logger.warning("⚠️  Окружение не установлено как production, но запуск как production")
    
    manager = ServerManager()
    manager.setup_signal_handlers()
    
    # Запуск в production окружении
    asyncio.run(manager.run_server(Environment.PRODUCTION))


def run_test_server():
    """Запуск сервера для тестирования"""
    logger.info("🧪 Запуск сервера для тестирования...")
    
    manager = ServerManager()
    manager.setup_signal_handlers()
    
    # Запуск в test окружении
    asyncio.run(manager.run_server(
        Environment.TESTING,
        port=8001,  # Другой порт для тестов
        workers=1
    ))


def check_dependencies():
    """Проверка зависимостей"""
    logger.info("🔍 Проверка зависимостей...")
    
    required_modules = [
        "fastapi",
        "uvicorn", 
        "psutil",
        "pydantic"
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"  ✅ {module}")
        except ImportError:
            logger.error(f"  ❌ {module} - не установлен")
            missing_modules.append(module)
    
    if missing_modules:
        logger.error(f"Отсутствующие модули: {', '.join(missing_modules)}")
        logger.error("Установите их командой: pip install -r requirements.txt")
        return False
    
    logger.info("✅ Все зависимости установлены")
    return True


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Запуск API администрирования кэша для 1С сервера",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Запуск для разработки
  python run.py dev

  # Запуск для продакшена
  python run.py prod

  # Запуск для тестирования
  python run.py test

  # Проверка здоровья сервера
  python run.py health --port 8000

  # Проверка зависимостей
  python run.py check

  # Информация о конфигурации
  python run.py info
        """
    )
    
    parser.add_argument(
        "command",
        choices=["dev", "prod", "test", "health", "check", "info"],
        help="Команда для выполнения"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Порт для проверки здоровья (по умолчанию 8000)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost", 
        help="Хост для проверки здоровья (по умолчанию localhost)"
    )
    
    parser.add_argument(
        "--config-file",
        type=str,
        help="Путь к файлу конфигурации (.env файл)"
    )
    
    args = parser.parse_args()
    
    # Загрузка конфигурационного файла если указан
    if args.config_file:
        from pathlib import Path
        config_file = Path(args.config_file)
        if config_file.exists():
            import os
            os.environ["ENV_FILE"] = str(config_file)
            logger.info(f"Загружена конфигурация из: {config_file}")
        else:
            logger.error(f"Файл конфигурации не найден: {config_file}")
            sys.exit(1)
    
    # Выполнение команды
    try:
        if args.command == "dev":
            run_development_server()
        elif args.command == "prod":
            run_production_server()
        elif args.command == "test":
            run_test_server()
        elif args.command == "health":
            if asyncio.run(run_health_check(args.port, args.host)):
                sys.exit(0)
            else:
                sys.exit(1)
        elif args.command == "check":
            if check_dependencies():
                sys.exit(0)
            else:
                sys.exit(1)
        elif args.command == "info":
            # Информация о конфигурации
            pass

            from config import config
            
            logger.info("=== Информация о конфигурации ===")
            logger.info(f"Текущее окружение: {config.environment}")
            logger.info(f"Приложение: {config.app_name} v{config.app_version}")
            logger.info(f"Режим отладки: {config.debug}")
            logger.info(f"Хост: {config.host}:{config.port}")
            
            print("\n=== Настройки кэша ===")
            print(f"  Тип: {config.cache.type}")
            print(f"  Максимальная память: {config.cache.max_memory_mb} МБ")
            print(f"  TTL по умолчанию: {config.cache.default_ttl} сек")
            
            print("\n=== Настройки безопасности ===")
            print(f"  CORS источники: {len(config.security.cors_origins)}")
            print(f"  JWT алгоритм: {config.security.jwt_algorithm}")
            print(f"  Лимит запросов: {config.security.rate_limit_per_minute}/мин")
            
            print("\n=== Настройки метрик ===")
            print(f"  Включены: {config.metrics.enable_metrics}")
            print(f"  Хранение: {config.metrics.metrics_retention_hours} часов")
            
            # Проверка валидности
            from config import validate_config
            errors = validate_config()
            if errors:
                print(f"\n❌ Найдено {len(errors)} ошибок валидации:")
                for error in errors:
                    print(f"  • {error}")
            else:
                print("\n✅ Конфигурация валидна")
                
    except KeyboardInterrupt:
        logger.info("Остановка по запросу пользователя")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Ошибка выполнения команды: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
