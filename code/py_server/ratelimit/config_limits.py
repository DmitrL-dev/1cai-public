
"""
Система конфигурируемых лимитов для Rate Limiting
Обеспечивает гибкое управление лимитами запросов с поддержкой:
- Конфигурации через YAML/JSON
- Динамических лимитов по времени
- Многоуровневых лимитов (bronze/silver/gold)
- Правил применения по контексту
- Переопределения для админов
- Hot reload конфигурации
"""

import copy
import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

# Настройка логирования
logger = logging.getLogger(__name__)


class LimitType(Enum):
    """Типы лимитов"""
    IP = "ip"
    USER = "user"
    MCP_TOOL = "mcp_tool"
    SESSION = "session"
    ENDPOINT = "endpoint"


class TierLevel(Enum):
    """Уровни пользователей"""
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    ADMIN = "admin"


@dataclass
class LimitRule:
    """Правило лимита"""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: Optional[int] = None
    burst_allowance: int = 0  # Разрешенные всплески
    penalty_duration: int = 0  # Длительность блокировки в секундах
    weight: float = 1.0  # Вес для вычисления фактического лимита


@dataclass
class TierConfig:
    """Конфигурация уровня пользователя"""
    name: str
    multiplier: float = 1.0
    rules: Dict[str, LimitRule] = field(default_factory=dict)
    priority: int = 0  # Приоритет для разрешения конфликтов


@dataclass
class TimeWindow:
    """Временное окно для динамических лимитов"""
    start_time: str  # HH:MM формат
    end_time: str    # HH:MM формат
    days_of_week: List[int] = field(default_factory=lambda: list(range(7)))  # 0-6, где 0 - понедельник
    multiplier: float = 1.0
    active: bool = True


class LimitConfig:
    """
    Базовая конфигурация лимитов с поддержкой YAML/JSON
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self._config_data: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._last_modified = 0
        self._backup_files = []
        self._max_backups = 5
        
        # Базовая конфигурация согласно техническим требованиям
        self._default_config = {
            'limits': {
                'ip': {
                    'requests_per_minute': 100,
                    'requests_per_hour': 1000,
                    'requests_per_day': 10000,
                    'burst_allowance': 20,
                    'penalty_duration': 300
                },
                'user': {
                    'requests_per_minute': 50,
                    'requests_per_hour': 500,
                    'requests_per_day': 5000,
                    'burst_allowance': 10,
                    'penalty_duration': 600
                },
                'mcp_tool': {
                    'requests_per_minute': 10,
                    'requests_per_hour': 100,
                    'requests_per_day': 1000,
                    'burst_allowance': 5,
                    'penalty_duration': 900
                },
                'session': {
                    'requests_per_minute': 200,
                    'requests_per_hour': 2000,
                    'requests_per_day': 20000,
                    'burst_allowance': 30,
                    'penalty_duration': 300
                },
                'endpoint': {
                    'requests_per_minute': 1000,
                    'requests_per_hour': 10000,
                    'requests_per_day': 100000,
                    'burst_allowance': 50,
                    'penalty_duration': 60
                }
            },
            'tiers': {
                'bronze': {
                    'name': 'Bronze',
                    'multiplier': 0.5,
                    'priority': 1,
                    'rules': {}
                },
                'silver': {
                    'name': 'Silver',
                    'multiplier': 1.0,
                    'priority': 2,
                    'rules': {}
                },
                'gold': {
                    'name': 'Gold',
                    'multiplier': 1.5,
                    'priority': 3,
                    'rules': {}
                },
                'platinum': {
                    'name': 'Platinum',
                    'multiplier': 2.0,
                    'priority': 4,
                    'rules': {}
                },
                'admin': {
                    'name': 'Administrator',
                    'multiplier': 10.0,
                    'priority': 10,
                    'rules': {}
                }
            },
            'time_windows': {},
            'overrides': {},
            'monitoring': {
                'enabled': True,
                'metrics_interval': 60,
                'alert_thresholds': {
                    'violation_rate': 0.05,  # 5%
                    'response_time_ms': 1000,
                    'blocked_requests_per_minute': 100
                }
            }
        }
        
        if config_path:
            self.load_config()
        else:
            self._config_data = copy.deepcopy(self._default_config)
    
    def load_config(self, config_path: Optional[str] = None) -> bool:
        """
        Загрузка конфигурации из файла
        """
        path = config_path or self.config_path
        if not path or not Path(path).exists():
            logger.warning(f"Конфигурационный файл не найден: {path}")
            self._config_data = copy.deepcopy(self._default_config)
            return False
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.endswith(('.yml', '.yaml')):
                    self._config_data = yaml.safe_load(f)
                else:
                    self._config_data = json.load(f)
            
            # Создание резервной копии
            self._create_backup()
            
            # Валидация конфигурации
            validator = LimitValidator()
            validator.validate_config(self._config_data)
            
            self._last_modified = os.path.getmtime(path)
            logger.info(f"Конфигурация загружена из {path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации из {path}: {e}")
            # Загрузка из резервной копии
            return self._restore_from_backup()
    
    def save_config(self, config_path: Optional[str] = None, backup: bool = True) -> bool:
        """
        Сохранение конфигурации в файл
        """
        path = config_path or self.config_path
        if not path:
            logger.error("Не указан путь для сохранения конфигурации")
            return False
        
        try:
            if backup:
                self._create_backup()
            
            # Создание директории если не существует
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                if path.endswith(('.yml', '.yaml')):
                    yaml.dump(self._config_data, f, default_flow_style=False, 
                             allow_unicode=True, indent=2)
                else:
                    json.dump(self._config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Конфигурация сохранена в {path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации в {path}: {e}")
            return False
    
    def get_limit_rule(self, limit_type: str, tier: str = 'bronze') -> LimitRule:
        """
        Получение правила лимита для типа и уровня
        """
        with self._lock:
            limit_config = self._config_data.get('limits', {}).get(limit_type, {})
            tier_config = self._config_data.get('tiers', {}).get(tier, {})
            
            # Базовое правило
            rule = LimitRule(
                requests_per_minute=limit_config.get('requests_per_minute', 100),
                requests_per_hour=limit_config.get('requests_per_hour', 1000),
                requests_per_day=limit_config.get('requests_per_day'),
                burst_allowance=limit_config.get('burst_allowance', 0),
                penalty_duration=limit_config.get('penalty_duration', 0)
            )
            
            # Применение множителя уровня
            multiplier = tier_config.get('multiplier', 1.0)
            rule.requests_per_minute = int(rule.requests_per_minute * multiplier)
            rule.requests_per_hour = int(rule.requests_per_hour * multiplier)
            if rule.requests_per_day:
                rule.requests_per_day = int(rule.requests_per_day * multiplier)
            
            # Специальные правила уровня
            tier_rules = tier_config.get('rules', {})
            if limit_type in tier_rules:
                tier_rule = tier_rules[limit_type]
                for key, value in tier_rule.items():
                    if hasattr(rule, key):
                        setattr(rule, key, int(value * multiplier))
            
            return rule
    
    def update_limit_rule(self, limit_type: str, tier: str, rule_data: Dict[str, Any]):
        """
        Обновление правила лимита
        """
        with self._lock:
            if 'limits' not in self._config_data:
                self._config_data['limits'] = {}
            if limit_type not in self._config_data['limits']:
                self._config_data['limits'][limit_type] = {}
            
            self._config_data['limits'][limit_type].update(rule_data)
            
            logger.info(f"Обновлено правило лимита {limit_type} для уровня {tier}")
    
    def add_tier(self, tier_config: TierConfig):
        """
        Добавление нового уровня
        """
        with self._lock:
            if 'tiers' not in self._config_data:
                self._config_data['tiers'] = {}
            
            self._config_data['tiers'][tier_config.name] = {
                'name': tier_config.name,
                'multiplier': tier_config.multiplier,
                'priority': tier_config.priority,
                'rules': {k: asdict(v) for k, v in tier_config.rules.items()}
            }
            
            logger.info(f"Добавлен новый уровень: {tier_config.name}")
    
    def get_config_data(self) -> Dict[str, Any]:
        """
        Получение данных конфигурации
        """
        with self._lock:
            return copy.deepcopy(self._config_data)
    
    def _create_backup(self):
        """
        Создание резервной копии конфигурации
        """
        if not self.config_path or not Path(self.config_path).exists():
            return
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{self.config_path}.backup_{timestamp}"
            
            # Копирование текущего файла
            import shutil
            shutil.copy2(self.config_path, backup_path)
            
            # Добавление в список резервных копий
            self._backup_files.append(backup_path)
            
            # Ограничение количества резервных копий
            if len(self._backup_files) > self._max_backups:
                old_backup = self._backup_files.pop(0)
                try:
                    os.remove(old_backup)
                except:
                    pass
                    
        except Exception as e:
            logger.warning(f"Не удалось создать резервную копию: {e}")
    
    def _restore_from_backup(self) -> bool:
        """
        Восстановление из резервной копии
        """
        if not self._backup_files:
            logger.error("Нет доступных резервных копий")
            return False
        
        try:
            # Попытка восстановления из последней резервной копии
            last_backup = self._backup_files[-1]
            with open(last_backup, 'r', encoding='utf-8') as f:
                if last_backup.endswith(('.yml', '.yaml')):
                    self._config_data = yaml.safe_load(f)
                else:
                    self._config_data = json.load(f)
            
            logger.info(f"Конфигурация восстановлена из резервной копии: {last_backup}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка восстановления из резервной копии: {e}")
            # Загрузка базовой конфигурации
            self._config_data = copy.deepcopy(self._default_config)
            return False


class DynamicLimits:
    """
    Динамическое изменение лимитов по времени
    """
    
    def __init__(self, config: LimitConfig):
        self.config = config
        self._active_windows: Dict[str, TimeWindow] = {}
        self._current_time = datetime.now()
    
    def add_time_window(self, name: str, window: TimeWindow):
        """
        Добавление временного окна
        """
        self._active_windows[name] = window
        logger.info(f"Добавлено временное окно: {name} ({window.start_time}-{window.end_time})")
    
    def get_effective_limit(self, limit_type: str, tier: str = 'bronze') -> LimitRule:
        """
        Получение эффективного лимита с учетом временных окон
        """
        base_rule = self.config.get_limit_rule(limit_type, tier)
        
        # Проверка активных временных окон
        current_time = datetime.now()
        current_weekday = current_time.weekday()
        current_time_str = current_time.strftime('%H:%M')
        
        effective_multiplier = 1.0
        
        for window in self._active_windows.values():
            if not window.active:
                continue
            
            # Проверка дня недели
            if current_weekday not in window.days_of_week:
                continue
            
            # Проверка времени
            try:
                start_hour, start_min = map(int, window.start_time.split(':'))
                end_hour, end_min = map(int, window.end_time.split(':'))
                
                window_start = current_time.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                window_end = current_time.replace(hour=end_hour, minute=end_min, second=59, microsecond=999999)
                
                # Обработка перехода через полночь
                if window_start > window_end:
                    window_end += timedelta(days=1)
                
                if window_start <= current_time <= window_end:
                    effective_multiplier *= window.multiplier
                    logger.debug(f"Активно временное окно с множителем {window.multiplier}")
                    
            except ValueError:
                logger.warning(f"Некорректное время в окне {window}: {window.start_time}-{window.end_time}")
                continue
        
        # Применение множителя
        if effective_multiplier != 1.0:
            modified_rule = copy.deepcopy(base_rule)
            modified_rule.requests_per_minute = int(modified_rule.requests_per_minute * effective_multiplier)
            modified_rule.requests_per_hour = int(modified_rule.requests_per_hour * effective_multiplier)
            if modified_rule.requests_per_day:
                modified_rule.requests_per_day = int(modified_rule.requests_per_day * effective_multiplier)
            
            return modified_rule
        
        return base_rule
    
    def get_active_windows(self) -> Dict[str, TimeWindow]:
        """
        Получение активных временных окон
        """
        return copy.deepcopy(self._active_windows)


class TieredLimits:
    """
    Многоуровневая система лимитов (bronze/silver/gold)
    """
    
    def __init__(self, config: LimitConfig):
        self.config = config
        self._user_tiers: Dict[str, str] = {}  # user_id -> tier_name
        self._tier_cache: Dict[str, TierConfig] = {}
        self._build_tier_cache()
    
    def _build_tier_cache(self):
        """
        Построение кэша уровней
        """
        tiers_data = self.config.get_config_data().get('tiers', {})
        
        for tier_name, tier_data in tiers_data.items():
            rules = {}
            for rule_name, rule_data in tier_data.get('rules', {}).items():
                rules[rule_name] = LimitRule(**rule_data)
            
            self._tier_cache[tier_name] = TierConfig(
                name=tier_data.get('name', tier_name),
                multiplier=tier_data.get('multiplier', 1.0),
                priority=tier_data.get('priority', 0),
                rules=rules
            )
        
        logger.debug(f"Построен кэш уровней: {list(self._tier_cache.keys())}")
    
    def assign_user_tier(self, user_id: str, tier_name: str):
        """
        Назначение уровня пользователю
        """
        if tier_name not in self._tier_cache:
            raise ValueError(f"Неизвестный уровень: {tier_name}")
        
        self._user_tiers[user_id] = tier_name
        logger.info(f"Пользователю {user_id} назначен уровень {tier_name}")
    
    def get_user_tier(self, user_id: str) -> str:
        """
        Получение уровня пользователя
        """
        return self._user_tiers.get(user_id, 'bronze')
    
    def get_user_limit_rule(self, user_id: str, limit_type: str) -> LimitRule:
        """
        Получение лимита для пользователя с учетом его уровня
        """
        tier_name = self.get_user_tier(user_id)
        return self.config.get_limit_rule(limit_type, tier_name)
    
    def upgrade_user_tier(self, user_id: str, new_tier: str) -> bool:
        """
        Повышение уровня пользователя
        """
        current_tier = self.get_user_tier(user_id)
        
        if current_tier not in self._tier_cache or new_tier not in self._tier_cache:
            return False
        
        current_priority = self._tier_cache[current_tier].priority
        new_priority = self._tier_cache[new_tier].priority
        
        if new_priority > current_priority:
            self._user_tiers[user_id] = new_tier
            logger.info(f"Пользователь {user_id} повышен с {current_tier} до {new_tier}")
            return True
        
        return False
    
    def get_all_tiers(self) -> Dict[str, TierConfig]:
        """
        Получение всех уровней
        """
        return copy.deepcopy(self._tier_cache)
    
    def get_tier_hierarchy(self) -> List[Tuple[str, int]]:
        """
        Получение иерархии уровней (от низшего к высшему)
        """
        tiers = [(name, config.priority) for name, config in self._tier_cache.items()]
        return sorted(tiers, key=lambda x: x[1])


class RateLimitRules:
    """
    Правила применения лимитов по контексту
    """
    
    def __init__(self):
        self._rules: List[Dict[str, Any]] = []
        self._rule_cache: Dict[str, Callable] = {}
    
    def add_rule(self, name: str, condition: str, action: str, priority: int = 0):
        """
        Добавление правила применения лимитов
        
        Args:
            name: Имя правила
            condition: Условие применения (например, "user_id.startswith('admin_')")
            action: Действие (например, "override_limit:admin")
            priority: Приоритет правила (больше = важнее)
        """
        rule = {
            'name': name,
            'condition': condition,
            'action': action,
            'priority': priority,
            'active': True
        }
        
        self._rules.append(rule)
        # Сортировка по приоритету
        self._rules.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"Добавлено правило: {name} (приоритет: {priority})")
    
    def evaluate_rules(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Оценка правил для контекста
        
        Args:
            context: Контекст запроса (user_id, ip, endpoint, etc.)
        
        Returns:
            Действие, которое нужно применить, или None
        """
        for rule in self._rules:
            if not rule.get('active', True):
                continue
            
            try:
                # Безопасная оценка условия
                if self._evaluate_condition(rule['condition'], context):
                    logger.debug(f"Сработало правило: {rule['name']}")
                    return rule['action']
            except Exception as e:
                logger.warning(f"Ошибка оценки правила {rule['name']}: {e}")
        
        return None
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Безопасная оценка условия
        """
        try:
            # Простая безопасная оценка без использования eval
            if condition.startswith('user_id.startswith('):
                prefix = condition.split("'")[1]
                return context.get('user_id', '').startswith(prefix)
            elif condition.startswith('ip.startswith('):
                prefix = condition.split("'")[1]
                return context.get('ip', '').startswith(prefix)
            elif condition == 'user_id in admin_list':
                return context.get('user_id') in context.get('admin_list', [])
            else:
                logger.warning(f"Неизвестное условие: {condition}")
                return False
        except Exception as e:
            logger.warning(f"Ошибка оценки условия '{condition}': {e}")
            return False
    
    def get_active_rules(self) -> List[Dict[str, Any]]:
        """
        Получение активных правил
        """
        return [rule for rule in self._rules if rule.get('active', True)]
    
    def disable_rule(self, rule_name: str):
        """
        Отключение правила
        """
        for rule in self._rules:
            if rule['name'] == rule_name:
                rule['active'] = False
                logger.info(f"Правило {rule_name} отключено")
                break
    
    def enable_rule(self, rule_name: str):
        """
        Включение правила
        """
        for rule in self._rules:
            if rule['name'] == rule_name:
                rule['active'] = True
                logger.info(f"Правило {rule_name} включено")
                break


class LimitOverrides:
    """
    Переопределение лимитов для админов
    """
    
    def __init__(self):
        self._overrides: Dict[str, Dict[str, LimitRule]] = {}  # target -> limit_type -> rule
        self._admin_users: set = set()
    
    def add_admin(self, user_id: str):
        """
        Добавление администратора
        """
        self._admin_users.add(user_id)
        logger.info(f"Добавлен администратор: {user_id}")
    
    def is_admin(self, user_id: str) -> bool:
        """
        Проверка, является ли пользователь администратором
        """
        return user_id in self._admin_users
    
    def set_override(self, target: str, limit_type: str, rule: LimitRule):
        """
        Установка переопределения лимита
        """
        if target not in self._overrides:
            self._overrides[target] = {}
        
        self._overrides[target][limit_type] = copy.deepcopy(rule)
        logger.info(f"Установлено переопределение лимита {limit_type} для {target}")
    
    def get_override(self, target: str, limit_type: str) -> Optional[LimitRule]:
        """
        Получение переопределения лимита
        """
        return copy.deepcopy(self._overrides.get(target, {}).get(limit_type))
    
    def remove_override(self, target: str, limit_type: Optional[str] = None):
        """
        Удаление переопределения лимита
        """
        if limit_type:
            if target in self._overrides and limit_type in self._overrides[target]:
                del self._overrides[target][limit_type]
                logger.info(f"Удалено переопределение лимита {limit_type} для {target}")
        else:
            if target in self._overrides:
                del self._overrides[target]
                logger.info(f"Удалены все переопределения для {target}")
    
    def get_effective_limit(self, user_id: str, limit_type: str, base_rule: LimitRule) -> LimitRule:
        """
        Получение эффективного лимита с учетом переопределений
        """
        # Проверка переопределения для конкретного пользователя
        override = self.get_override(f"user:{user_id}", limit_type)
        if override:
            return override
        
        # Проверка переопределения для IP
        # Это должно быть передано из контекста вызова
        # (пока заглушка)
        
        return base_rule
    
    def get_all_overrides(self) -> Dict[str, Dict[str, LimitRule]]:
        """
        Получение всех переопределений
        """
        return copy.deepcopy(self._overrides)


class LimitValidator:
    """
    Валидация конфигурации лимитов
    """
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Валидация конфигурации лимитов
        """
        try:
            # Проверка структуры limits
            limits = config.get('limits', {})
            for limit_type, limit_config in limits.items():
                if not isinstance(limit_config, dict):
                    raise ValueError(f"Некорректная конфигурация лимита {limit_type}")
                
                # Обязательные поля
                required_fields = ['requests_per_minute', 'requests_per_hour']
                for field in required_fields:
                    if field not in limit_config:
                        raise ValueError(f"Отсутствует обязательное поле {field} в лимите {limit_type}")
                    
                    if not isinstance(limit_config[field], (int, float)) or limit_config[field] <= 0:
                        raise ValueError(f"Некорректное значение {field}={limit_config[field]} в лимите {limit_type}")
            
            # Проверка структуры tiers
            tiers = config.get('tiers', {})
            for tier_name, tier_config in tiers.items():
                if not isinstance(tier_config, dict):
                    raise ValueError(f"Некорректная конфигурация уровня {tier_name}")
                
                if 'multiplier' in tier_config:
                    multiplier = tier_config['multiplier']
                    if not isinstance(multiplier, (int, float)) or multiplier <= 0:
                        raise ValueError(f"Некорректный множитель {multiplier} в уровне {tier_name}")
            
            logger.info("Валидация конфигурации прошла успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка валидации конфигурации: {e}")
            raise
    
    def validate_rule(self, rule: LimitRule) -> bool:
        """
        Валидация отдельного правила лимита
        """
        if rule.requests_per_minute <= 0:
            raise ValueError("requests_per_minute должен быть положительным числом")
        
        if rule.requests_per_hour <= 0:
            raise ValueError("requests_per_hour должен быть положительным числом")
        
        if rule.requests_per_minute > rule.requests_per_hour:
            raise ValueError("requests_per_minute не может быть больше requests_per_hour")
        
        if rule.burst_allowance < 0:
            raise ValueError("burst_allowance не может быть отрицательным")
        
        if rule.penalty_duration < 0:
            raise ValueError("penalty_duration не может быть отрицательным")
        
        return True


class ConfigurationManager:
    """
    Менеджер конфигурации с поддержкой hot reload
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = LimitConfig(config_path)
        self.dynamic_limits = DynamicLimits(self.config)
        self.tiered_limits = TieredLimits(self.config)
        self.limit_rules = RateLimitRules()
        self.limit_overrides = LimitOverrides()
        
        self._lock = threading.RLock()
        self._hot_reload_enabled = True
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Инициализация стандартных правил
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """
        Настройка стандартных правил применения лимитов
        """
        # Правила для админов
        self.limit_rules.add_rule(
            name="admin_override",
            condition="user_id in admin_list",
            action="apply_admin_limits",
            priority=100
        )
        
        # Правила для MCP tools
        self.limit_rules.add_rule(
            name="mcp_heavy_operations",
            condition="endpoint.startswith('/mcp/')",
            action="apply_mcp_heavy_limits",
            priority=50
        )
        
        # Правила для API endpoints
        self.limit_rules.add_rule(
            name="api_priority",
            condition="endpoint.startswith('/api/')",
            action="apply_api_limits",
            priority=25
        )
    
    def start_hot_reload(self, check_interval: int = 30):
        """
        Запуск горячей перезагрузки конфигурации
        """
        if not self._hot_reload_enabled or not self.config.config_path:
            return
        
        if self._watch_thread and self._watch_thread.is_alive():
            logger.warning("Hot reload уже запущен")
            return
        
        self._stop_event.clear()
        self._watch_thread = threading.Thread(
            target=self._watch_config,
            args=(check_interval,),
            daemon=True
        )
        self._watch_thread.start()
        
        logger.info(f"Запущен hot reload конфигурации (интервал: {check_interval}с)")
    
    def stop_hot_reload(self):
        """
        Остановка горячей перезагрузки конфигурации
        """
        if self._watch_thread:
            self._stop_event.set()
            self._watch_thread.join(timeout=5)
            logger.info("Hot reload конфигурации остановлен")
    
    def _watch_config(self, check_interval: int):
        """
        Мониторинг изменений конфигурации
        """
        last_modified = self.config._last_modified
        
        while not self._stop_event.is_set():
            try:
                if self.config.config_path and Path(self.config.config_path).exists():
                    current_modified = os.path.getmtime(self.config.config_path)
                    
                    if current_modified > last_modified:
                        logger.info("Обнаружено изменение конфигурации, перезагрузка...")
                        
                        if self.config.load_config():
                            # Пересборка кэшей
                            self.tiered_limits._build_tier_cache()
                            
                            logger.info("Конфигурация успешно перезагружена")
                            last_modified = current_modified
                        
            except Exception as e:
                logger.error(f"Ошибка при проверке конфигурации: {e}")
            
            if self._stop_event.wait(check_interval):
                break
    
    def get_effective_limit(self, context: Dict[str, Any]) -> LimitRule:
        """
        Получение эффективного лимита с учетом всех факторов
        """
        with self._lock:
            limit_type = context.get('limit_type', 'user')
            user_id = context.get('user_id', '')
            
            # Получение базового лимита с учетом уровня
            user_tier = self.tiered_limits.get_user_tier(user_id)
            base_rule = self.dynamic_limits.get_effective_limit(limit_type, user_tier)
            
            # Применение правил
            action = self.limit_rules.evaluate_rules(context)
            if action == "apply_admin_limits" and self.limit_overrides.is_admin(user_id):
                # Применение админских лимитов
                admin_rule = LimitRule(
                    requests_per_minute=10000,
                    requests_per_hour=100000,
                    burst_allowance=1000,
                    penalty_duration=0
                )
                return admin_rule
            
            # Применение переопределений
            effective_rule = self.limit_overrides.get_effective_limit(user_id, limit_type, base_rule)
            
            return effective_rule
    
    def export_config(self, path: str, format: str = 'json') -> bool:
        """
        Экспорт конфигурации
        """
        try:
            config_data = self.config.get_config_data()
            
            with open(path, 'w', encoding='utf-8') as f:
                if format.lower() in ['yaml', 'yml']:
                    yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, indent=2)
                else:
                    json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Конфигурация экспортирована в {path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка экспорта конфигурации: {e}")
            return False
    
    def import_config(self, path: str) -> bool:
        """
        Импорт конфигурации
        """
        try:
            validator = LimitValidator()
            
            # Загрузка и валидация
            with open(path, 'r', encoding='utf-8') as f:
                if path.endswith(('.yml', '.yaml')):
                    config_data = yaml.safe_load(f)
                else:
                    config_data = json.load(f)
            
            validator.validate_config(config_data)
            
            # Сохранение конфигурации
            self.config._config_data = config_data
            self.config.save_config()
            
            # Пересборка кэшей
            self.tiered_limits._build_tier_cache()
            
            logger.info(f"Конфигурация импортирована из {path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка импорта конфигурации: {e}")
            return False
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """
        Получение статистики для мониторинга
        """
        return {
            'total_tiers': len(self.tiered_limits.get_all_tiers()),
            'active_rules': len(self.limit_rules.get_active_rules()),
            'admin_overrides': len(self.limit_overrides.get_all_overrides()),
            'hot_reload_enabled': self._hot_reload_enabled,
            'config_path': self.config.config_path,
            'tier_hierarchy': self.tiered_limits.get_tier_hierarchy()
        }


# Пример использования
if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Создание менеджера конфигурации
    config_manager = ConfigurationManager()
    
    # Добавление администратора
    config_manager.limit_overrides.add_admin("admin_123")
    
    # Назначение уровня пользователю
    config_manager.tiered_limits.assign_user_tier("user_456", "gold")
    
    # Получение эффективного лимита
    context = {
        'user_id': 'user_456',
        'limit_type': 'user',
        'endpoint': '/api/data'
    }
    
    effective_limit = config_manager.get_effective_limit(context)
    print(f"Эффективный лимит: {effective_limit}")
    
    # Статистика мониторинга
    stats = config_manager.get_monitoring_stats()
    print(f"Статистика: {stats}")
