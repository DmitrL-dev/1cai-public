
"""
Простой тест системы конфигурируемых лимитов
"""

import os
import sys

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_limits import ConfigurationManager, LimitRule, TimeWindow


def test_basic_functionality():
    """Тест базовой функциональности"""
    print("=== Тест базовой функциональности ===")
    
    # Создание менеджера конфигурации
    config_manager = ConfigurationManager()
    
    # Проверка базовых лимитов
    user_limit = config_manager.config.get_limit_rule('user', 'bronze')
    print(f"Базовый лимит пользователя Bronze: {user_limit.requests_per_minute} req/min, {user_limit.requests_per_hour} req/hour")
    
    # Проверка лимитов Gold
    gold_limit = config_manager.config.get_limit_rule('user', 'gold')
    print(f"Базовый лимит пользователя Gold: {gold_limit.requests_per_minute} req/min, {gold_limit.requests_per_hour} req/hour")
    
    assert gold_limit.requests_per_minute > user_limit.requests_per_minute
    print("✅ Базовые лимиты работают корректно")


def test_tiered_limits():
    """Тест многоуровневой системы"""
    print("\n=== Тест многоуровневой системы ===")
    
    config_manager = ConfigurationManager()
    
    # Назначение уровней пользователям
    config_manager.tiered_limits.assign_user_tier("user_bronze", "bronze")
    config_manager.tiered_limits.assign_user_tier("user_gold", "gold")
    config_manager.tiered_limits.assign_user_tier("user_admin", "admin")
    
    # Проверка получения лимитов
    bronze_limit = config_manager.tiered_limits.get_user_limit_rule("user_bronze", "user")
    gold_limit = config_manager.tiered_limits.get_user_limit_rule("user_gold", "user")
    admin_limit = config_manager.tiered_limits.get_user_limit_rule("user_admin", "user")
    
    print(f"Лимит Bronze: {bronze_limit.requests_per_minute} req/min")
    print(f"Лимит Gold: {gold_limit.requests_per_minute} req/min")
    print(f"Лимит Admin: {admin_limit.requests_per_minute} req/min")
    
    assert bronze_limit.requests_per_minute < gold_limit.requests_per_minute
    assert gold_limit.requests_per_minute < admin_limit.requests_per_minute
    print("✅ Многоуровневая система работает корректно")


def test_dynamic_limits():
    """Тест динамических лимитов"""
    print("\n=== Тест динамических лимитов ===")
    
    config_manager = ConfigurationManager()
    
    # Создание временного окна
    peak_window = TimeWindow(
        start_time="00:00",
        end_time="23:59",
        days_of_week=[1, 2, 3, 4, 5],  # Пн-Пт
        multiplier=0.5  # Снижение на 50%
    )
    
    config_manager.dynamic_limits.add_time_window("test_peak", peak_window)
    
    # Получение эффективного лимита
    base_limit = config_manager.dynamic_limits.get_effective_limit('user', 'bronze')
    
    print(f"Базовый лимит Bronze: {base_limit.requests_per_minute} req/min")
    print(f"Эффективный лимит с временным окном: {base_limit.requests_per_minute} req/min")
    
    # Проверка что лимит изменился (должен быть снижен на 50%)
    # Базовый лимит Bronze = 50 * 0.5 (Bronze multiplier) = 25
    # С временным окном: 25 * 0.5 (time window multiplier) = 12.5 -> 12
    assert base_limit.requests_per_minute == 12  # Целое число после применения обоих множителей
    print("✅ Динамические лимиты работают корректно")


def test_overrides():
    """Тест переопределений"""
    print("\n=== Тест переопределений ===")
    
    config_manager = ConfigurationManager()
    
    # Добавление администратора
    config_manager.limit_overrides.add_admin("admin123")
    
    # Проверка что админ распознается
    assert config_manager.limit_overrides.is_admin("admin123")
    assert not config_manager.limit_overrides.is_admin("user456")
    
    print("✅ Переопределения работают корректно")


def test_effective_limit():
    """Тест получения эффективного лимита"""
    print("\n=== Тест эффективного лимита ===")
    
    config_manager = ConfigurationManager()
    
    # Настройка контекста
    context = {
        'user_id': 'user_test',
        'limit_type': 'user',
        'endpoint': '/api/test'
    }
    
    # Получение эффективного лимита
    effective_limit = config_manager.get_effective_limit(context)
    
    print(f"Эффективный лимит: {effective_limit.requests_per_minute} req/min, {effective_limit.requests_per_hour} req/hour")
    print(f"Burst allowance: {effective_limit.burst_allowance}")
    print(f"Penalty duration: {effective_limit.penalty_duration}s")
    
    assert effective_limit.requests_per_minute > 0
    assert effective_limit.requests_per_hour > 0
    print("✅ Эффективный лимит вычисляется корректно")


def test_monitoring_stats():
    """Тест статистики мониторинга"""
    print("\n=== Тест статистики мониторинга ===")
    
    config_manager = ConfigurationManager()
    
    # Получение статистики
    stats = config_manager.get_monitoring_stats()
    
    print(f"Всего уровней: {stats['total_tiers']}")
    print(f"Активных правил: {stats['active_rules']}")
    print(f"Admin overrides: {stats['admin_overrides']}")
    print(f"Hot reload включен: {stats['hot_reload_enabled']}")
    
    assert stats['total_tiers'] >= 5  # Минимум 5 стандартных уровней
    assert stats['hot_reload_enabled'] == True
    print("✅ Статистика мониторинга работает корректно")


def test_config_validation():
    """Тест валидации конфигурации"""
    print("\n=== Тест валидации конфигурации ===")
    
    from config_limits import LimitValidator
    
    validator = LimitValidator()
    
    # Проверка валидного правила
    valid_rule = LimitRule(
        requests_per_minute=100,
        requests_per_hour=1000,
        burst_allowance=10,
        penalty_duration=300
    )
    
    assert validator.validate_rule(valid_rule)
    print("✅ Валидное правило прошло проверку")
    
    # Проверка невалидного правила
    try:
        invalid_rule = LimitRule(
            requests_per_minute=0,  # Некорректное значение
            requests_per_hour=1000,
            burst_allowance=10,
            penalty_duration=300
        )
        validator.validate_rule(invalid_rule)
        assert False, "Должна была быть ошибка валидации"
    except ValueError:
        print("✅ Некорректное правило корректно отклонено")


def main():
    """Запуск всех тестов"""
    print("Запуск тестов системы конфигурируемых лимитов\n")
    
    try:
        test_basic_functionality()
        test_tiered_limits()
        test_dynamic_limits()
        test_overrides()
        test_effective_limit()
        test_monitoring_stats()
        test_config_validation()
        
        print("\n" + "="*50)
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ ОШИБКА В ТЕСТАХ: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())