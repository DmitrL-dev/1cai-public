
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простая тестовая версия для проверки базовой функциональности исключений
"""

import json
import os
import sys

# Добавляем текущую папку в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import McpError
from transport import TransportError
from validation import ValidationError


def test_basic_error():
    """Тест базового исключения"""
    print("🧪 Тестирование базового исключения...")
    
    try:
        error = McpError(
            error_code="E001",
            error_type="system",
            user_message="Тестовая системная ошибка"
        )
        
        print(f"✅ Создано исключение: {error}")
        print(f"   Код: {error.error_code}")
        print(f"   Тип: {error.error_type}")
        print(f"   Восстановимое: {error.recoverable}")
        
        # Тест сериализации
        error_dict = error.to_dict()
        print(f"   Сериализация: {json.dumps(error_dict, ensure_ascii=False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validation_error():
    """Тест ошибки валидации"""
    print("\n🧪 Тестирование ошибки валидации...")
    
    try:
        error = ValidationError(
            error_code="E020",
            field_name="email",
            field_value="invalid",
            user_message="Некорректный email"
        )
        
        print(f"✅ Создано исключение: {error}")
        print(f"   Код: {error.error_code}")
        print(f"   Восстановимое: {error.recoverable}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_transport_error():
    """Тест транспортной ошибки"""
    print("\n🧪 Тестирование транспортной ошибки...")
    
    try:
        error = TransportError(
            error_code="E040",
            url="https://example.com",
            method="GET",
            user_message="Сетевая ошибка"
        )
        
        print(f"✅ Создано исключение: {error}")
        print(f"   Код: {error.error_code}")
        print(f"   Восстановимое: {error.recoverable}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 Простые тесты иерархии исключений")
    print("=" * 50)
    
    tests = [
        test_basic_error,
        test_validation_error,
        test_transport_error
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Результаты: {passed}/{total} тестов прошли")
    
    if passed == total:
        print("✅ Все тесты прошли успешно!")
        return True
    else:
        print("❌ Некоторые тесты провалились")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
