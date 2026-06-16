"""
Скрипт проверки рефакторинга API
Запустите этот скрипт, чтобы убедиться, что все отрефакторенные модули импортируются корректно и обратная совместимость сохранена.
"""
import sys
import logging
import os

# Добавляем корень проекта в sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def verify_module(name, legacy_path, new_path):
    logger.info(f"Проверка модуля: {name}...")
    try:
        # 1. Проверка импорта нового модуля
        logger.info(f"  Импорт нового модуля: {new_path}")
        __import__(new_path)

        # 2. Проверка импорта легаси прокси
        logger.info(f"  Импорт легаси прокси: {legacy_path}")
        legacy = __import__(legacy_path, fromlist=["*"])

        # 3. Проверка экспортов
        if name == "Code Analyzers":
            if hasattr(legacy, "analyze_python_code"):
                logger.info("  ✅ Функции экспортированы корректно")
            else:
                logger.error("  ❌ Функции НЕ экспортированы из легаси прокси")
                return False
        elif hasattr(legacy, "router"):
            logger.info("  ✅ Router экспортирован корректно")
        else:
            logger.error("  ❌ Router НЕ экспортирован из легаси прокси")
            return False

        logger.info(f"✅ Модуль {name} успешно проверен")
        return True
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта в {name}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка в {name}: {e}")
        return False


def main():
    logger.info("Запуск проверки рефакторинга...")

    modules_to_verify = [
        ("BA Sessions", "src.api.ba_sessions", "src.modules.ba_sessions"),
        ("Copilot API", "src.api.copilot_api_perfect", "src.modules.copilot"),
        ("Code Analyzers", "src.api.code_analyzers", "src.modules.code_analyzers"),
        ("Code Approval", "src.api.code_approval", "src.modules.code_approval"),
        ("Assistants", "src.api.assistants", "src.modules.assistants"),
        ("Metrics", "src.api.metrics", "src.modules.metrics"),
    ]

    success_count = 0
    for name, legacy, new in modules_to_verify:
        if verify_module(name, legacy, new):
            success_count += 1

    logger.info("-" * 30)
    if success_count == len(modules_to_verify):
        logger.info(f"✅ ВСЕ {success_count} МОДУЛЕЙ УСПЕШНО ПРОВЕРЕНЫ")
        sys.exit(0)
    else:
        logger.error(f"❌ ПРОВАЛ: Только {success_count}/{len(modules_to_verify)} модулей проверено")
        sys.exit(1)


if __name__ == "__main__":
    main()
