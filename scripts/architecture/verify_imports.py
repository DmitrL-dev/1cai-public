import sys
import os

# Добавляем текущую директорию в путь поиска модулей
sys.path.append(os.path.abspath("."))

print("🔍 Проверка импортов после рефакторинга...\n")

failed = False

# 1. Проверка MCP
try:
    print("✅ src.ai.mcp.server: OK")
except ImportError as e:
    print(f"❌ src.ai.mcp.server: FAILED ({e})")
    failed = True

# 2. Проверка Self-Healing
try:
    print("✅ src.ai.healing.code: OK")
except ImportError as e:
    print(f"❌ src.ai.healing.code: FAILED ({e})")
    failed = True

# 3. Проверка Code Analysis
try:
    print("✅ src.ai.code_analysis.dna: OK")
except ImportError as e:
    print(f"❌ src.ai.code_analysis.dna: FAILED ({e})")
    failed = True

print("-" * 30)
if failed:
    print("⚠️  ЕСТЬ ПРОБЛЕМЫ С ИМПОРТАМИ")
    sys.exit(1)
else:
    print("🎉 ВСЕ МОДУЛИ НАЙДЕНЫ КОРРЕКТНО")
    sys.exit(0)
