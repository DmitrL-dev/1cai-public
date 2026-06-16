
"""
Система маскирования чувствительных данных.

Автоматическое маскирование PII данных, токенов, паролей
и других конфиденциальной информации в логах.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set


class MaskingRule(Enum):
    """Правила маскирования"""
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    PASSWORD = "password"
    TOKEN = "token"
    API_KEY = "api_key"
    IP_ADDRESS = "ip_address"
    BANK_ACCOUNT = "bank_account"
    DRIVER_LICENSE = "driver_license"
    PASSPORT = "passport"


@dataclass
class MaskingConfig:
    """Конфигурация маскирования"""
    enabled: bool = True
    replacement_pattern: str = "***REDACTED***"
    hash_salt: Optional[str] = None
    preserve_length: bool = False
    preserve_pattern: bool = True


class PatternMatcher:
    """Компилятор и матчер регулярных выражений"""
    
    def __init__(self):
        self.patterns: Dict[MaskingRule, Pattern] = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Компиляция регулярных выражений"""
        
        # Email паттерны
        email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        self.patterns[MaskingRule.EMAIL] = email_pattern
        
        # Телефонные номера (российские и международные)
        phone_pattern = re.compile(
            r'\b(?:\+?7|8)?[\s-]?\(?9[0-9]{2}\)?[\s-]?[0-9]{3}[\s-]?[0-9]{2}[\s-]?[0-9]{2}\b',
            re.IGNORECASE
        )
        self.patterns[MaskingRule.PHONE] = phone_pattern
        
        # Номера кредитных карт
        credit_card_pattern = re.compile(
            r'\b(?:\d[ -]*?){13,19}\b',
            re.IGNORECASE
        )
        self.patterns[MaskingRule.CREDIT_CARD] = credit_card_pattern
        
        # SSN (российские и американские)
        ssn_pattern = re.compile(
            r'\b\d{3}-\d{2}-\d{4}\b|\b\d{11}\b',
            re.IGNORECASE
        )
        self.patterns[MaskingRule.SSN] = ssn_pattern
        
        # IP адреса
        ip_pattern = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )
        self.patterns[MaskingRule.IP_ADDRESS] = ip_pattern
        
        # Банковские счета
        bank_account_pattern = re.compile(
            r'\b\d{20,25}\b',
            re.IGNORECASE
        )
        self.patterns[MaskingRule.BANK_ACCOUNT] = bank_account_pattern
    
    def find_matches(self, text: str, rule: MaskingRule) -> List[re.Match]:
        """Поиск всех совпадений для правила"""
        pattern = self.patterns.get(rule)
        if pattern:
            return list(pattern.finditer(text))
        return []
    
    def replace_with_pattern(self, text: str, rule: MaskingRule, 
                           replacement: str, preserve_pattern: bool = True) -> str:
        """Замена текста с сохранением паттерна"""
        pattern = self.patterns.get(rule)
        if not pattern:
            return text
        
        def replace_func(match):
            matched_text = match.group(0)
            
            if preserve_pattern:
                # Сохранение структуры (например, скрытие только части)
                if rule == MaskingRule.EMAIL:
                    username, domain = matched_text.split('@', 1)
                    return f"{username[:2]}***@{domain}"
                elif rule == MaskingRule.PHONE:
                    return re.sub(r'\d', 'X', matched_text)
                elif rule == MaskingRule.CREDIT_CARD:
                    # Маскировка всех кроме последних 4 цифр
                    digits = re.sub(r'\D', '', matched_text)
                    if len(digits) >= 4:
                        masked = 'X' * (len(digits) - 4) + digits[-4:]
                        # Восстановление оригинального форматирования
                        result = masked
                        index = 0
                        formatted_result = ''
                        for char in matched_text:
                            if char.isdigit() and index < len(masked):
                                formatted_result += masked[index]
                                index += 1
                            else:
                                formatted_result += char
                        return formatted_result
                elif rule == MaskingRule.IP_ADDRESS:
                    parts = matched_text.split('.')
                    return f"{parts[0]}.{parts[1]}.***.***"
            
            return replacement
        
        return pattern.sub(replace_func, text)


class DataSanitizer:
    """Основной класс для санитизации данных"""
    
    def __init__(self):
        self.matcher = PatternMatcher()
        self.configs = self._load_default_configs()
        self.sensitive_keys = self._load_sensitive_keys()
        self.logger = logging.getLogger(__name__)
    
    def _load_default_configs(self) -> Dict[MaskingRule, MaskingConfig]:
        """Загрузка конфигураций по умолчанию"""
        return {
            MaskingRule.EMAIL: MaskingConfig(
                enabled=True,
                replacement_pattern="***EMAIL***",
                preserve_length=False,
                preserve_pattern=True
            ),
            MaskingRule.PHONE: MaskingConfig(
                enabled=True,
                replacement_pattern="***PHONE***",
                preserve_length=False,
                preserve_pattern=True
            ),
            MaskingRule.CREDIT_CARD: MaskingConfig(
                enabled=True,
                replacement_pattern="***CARD***",
                preserve_length=False,
                preserve_pattern=True
            ),
            MaskingRule.SSN: MaskingConfig(
                enabled=True,
                replacement_pattern="***SSN***",
                preserve_length=False,
                preserve_pattern=False
            ),
            MaskingRule.IP_ADDRESS: MaskingConfig(
                enabled=True,
                replacement_pattern="***IP***",
                preserve_length=False,
                preserve_pattern=True
            ),
            MaskingRule.BANK_ACCOUNT: MaskingConfig(
                enabled=True,
                replacement_pattern="***ACCOUNT***",
                preserve_length=False,
                preserve_pattern=False
            ),
            MaskingRule.PASSWORD: MaskingConfig(
                enabled=True,
                replacement_pattern="***PASSWORD***",
                preserve_length=False,
                preserve_pattern=False
            ),
            MaskingRule.TOKEN: MaskingConfig(
                enabled=True,
                replacement_pattern="***TOKEN***",
                preserve_length=False,
                preserve_pattern=False
            ),
            MaskingRule.API_KEY: MaskingConfig(
                enabled=True,
                replacement_pattern="***API_KEY***",
                preserve_length=False,
                preserve_pattern=False
            ),
        }
    
    def _load_sensitive_keys(self) -> Set[str]:
        """Загрузка чувствительных ключей"""
        return {
            'password', 'pwd', 'passwd',
            'token', 'access_token', 'refresh_token', 'auth_token',
            'api_key', 'api_key_id', 'secret', 'secret_key',
            'credit_card', 'cc_number', 'card_number',
            'ssn', 'social_security',
            'phone', 'phone_number', 'mobile',
            'email', 'e_mail', 'mail_address',
            'bank_account', 'account_number',
            'driver_license', 'passport', 'id_card',
            'private_key', 'key', 'encryption_key',
            'session_id', 'session_token',
            'user_id', 'username', 'user_name',
            'client_id', 'client_secret'
        }
    
    def sanitize_dict(self, data: Dict[str, Any], 
                     custom_rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Санитизация словаря данных"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        
        for key, value in data.items():
            sanitized_key = self.sanitize_key(key, custom_rules.get('key_mappings') if custom_rules else None)
            
            if isinstance(value, dict):
                sanitized[sanitized_key] = self.sanitize_dict(value, custom_rules)
            elif isinstance(value, list):
                sanitized[sanitized_key] = self.sanitize_list(value, custom_rules)
            else:
                sanitized[sanitized_key] = self.sanitize_value(value, key, custom_rules)
        
        return sanitized
    
    def sanitize_list(self, data: List[Any], 
                     custom_rules: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Санитизация списка данных"""
        if not isinstance(data, list):
            return data
        
        sanitized = []
        for item in data:
            if isinstance(item, dict):
                sanitized.append(self.sanitize_dict(item, custom_rules))
            elif isinstance(item, list):
                sanitized.append(self.sanitize_list(item, custom_rules))
            else:
                sanitized.append(self.sanitize_value(item, custom_rules=custom_rules))
        
        return sanitized
    
    def sanitize_value(self, value: Any, key: Optional[str] = None,
                      custom_rules: Optional[Dict[str, Any]] = None) -> Any:
        """Санитизация отдельного значения"""
        if value is None:
            return value
        
        # Проверка на чувствительные ключи
        if key and self.is_sensitive_key(key, custom_rules):
            return self._get_replacement_value(key, custom_rules)
        
        # Если это строка, применяем все правила маскирования
        if isinstance(value, str):
            sanitized = value
            
            # Применяем все активные правила маскирования
            for rule, config in self.configs.items():
                if config.enabled:
                    sanitized = self.matcher.replace_with_pattern(
                        sanitized, rule, config.replacement_pattern, config.preserve_pattern
                    )
            
            return sanitized
        
        return value
    
    def sanitize_key(self, key: str, key_mappings: Optional[Dict[str, str]] = None) -> str:
        """Санитизация ключа (если есть маппинг)"""
        if key_mappings and key in key_mappings:
            return key_mappings[key]
        
        # Понижение регистра для проверки чувствительности
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in self.sensitive_keys):
            # Возвращаем нормализованный ключ
            for sensitive in self.sensitive_keys:
                if sensitive in key_lower:
                    return sensitive
        
        return key
    
    def is_sensitive_key(self, key: str, custom_rules: Optional[Dict[str, Any]] = None) -> bool:
        """Проверка, является ли ключ чувствительным"""
        key_lower = key.lower()
        
        # Проверка стандартных чувствительных ключей
        if any(sensitive in key_lower for sensitive in self.sensitive_keys):
            return True
        
        # Проверка кастомных правил
        if custom_rules and 'sensitive_keys' in custom_rules:
            sensitive_keys = custom_rules['sensitive_keys']
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                return True
        
        return False
    
    def _get_replacement_value(self, key: str, custom_rules: Optional[Dict[str, Any]] = None) -> str:
        """Получение значения замены для чувствительного ключа"""
        if custom_rules and 'replacement_mapping' in custom_rules:
            key_lower = key.lower()
            for sensitive, replacement in custom_rules['replacement_mapping'].items():
                if sensitive in key_lower:
                    return replacement
        
        # Значения по умолчанию для разных типов данных
        key_lower = key.lower()
        if any(word in key_lower for word in ['password', 'pwd', 'passwd']):
            return "***PASSWORD***"
        elif any(word in key_lower for word in ['token', 'auth']):
            return "***TOKEN***"
        elif any(word in key_lower for word in ['api_key', 'key']):
            return "***API_KEY***"
        elif any(word in key_lower for word in ['credit_card', 'card']):
            return "***CARD***"
        elif any(word in key_lower for word in ['phone', 'mobile']):
            return "***PHONE***"
        elif any(word in key_lower for word in ['email', 'mail']):
            return "***EMAIL***"
        else:
            return "***REDACTED***"
    
    def hash_sensitive_value(self, value: str, salt: Optional[str] = None) -> str:
        """Хеширование чувствительного значения"""
        if salt:
            return hashlib.sha256((value + salt).encode()).hexdigest()
        return hashlib.sha256(value.encode()).hexdigest()
    
    def create_user_hash(self, user_id: str, salt: Optional[str] = None) -> str:
        """Создание хеша пользователя"""
        return self.hash_sensitive_value(user_id, salt)


# Глобальный экземпляр санитайзера
default_sanitizer = DataSanitizer()


# Функции-утилиты
def sanitize_sensitive_data(data: Any, custom_rules: Optional[Dict[str, Any]] = None) -> Any:
    """Быстрая функция для санитизации данных"""
    return default_sanitizer.sanitize_dict(data, custom_rules) if isinstance(data, dict) else data


def sanitize_for_logging(data: Dict[str, Any], 
                        custom_rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Санитизация данных специально для логирования"""
    # Добавляем специальные правила для логирования
    log_rules = custom_rules or {}
    log_rules.update({
        'sensitive_keys': [
            'auth', 'session', 'cookie', 'jwt',
            'billing', 'payment', 'transaction',
            'medical', 'health', 'insurance'
        ]
    })
    
    return default_sanitizer.sanitize_dict(data, log_rules)


def sanitize_request_data(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Санитизация данных HTTP запроса"""
    # Специальные правила для HTTP запросов
    http_rules = {
        'sensitive_keys': [
            'authorization', 'cookie', 'x-api-key',
            'content-type', 'content-length'
        ],
        'replacement_mapping': {
            'authorization': 'Authorization: ***',
            'cookie': 'Cookie: ***'
        }
    }
    
    return default_sanitizer.sanitize_dict(request_data, http_rules)


def sanitize_response_data(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """Санитизация данных HTTP ответа"""
    # Специальные правила для HTTP ответов
    response_rules = {
        'sensitive_keys': [
            'set-cookie', 'session-id', 'auth-token',
            'access-token', 'refresh-token'
        ],
        'replacement_mapping': {
            'set-cookie': 'Set-Cookie: ***',
            'session-id': '***SESSION***',
            'auth-token': '***AUTH_TOKEN***'
        }
    }
    
    return default_sanitizer.sanitize_dict(response_data, response_rules)


def sanitize_user_data(user_data: Dict[str, Any], 
                      salt: Optional[str] = None) -> Dict[str, Any]:
    """Санитизация пользовательских данных"""
    if not isinstance(user_data, dict):
        return user_data
    
    sanitized = user_data.copy()
    
    # Хеширование user_id
    if 'user_id' in sanitized:
        sanitized['user_id'] = default_sanitizer.create_user_hash(
            str(sanitized['user_id']), salt
        )
    
    # Маскирование email
    if 'email' in sanitized:
        sanitized['email'] = default_sanitizer.matcher.replace_with_pattern(
            sanitized['email'], MaskingRule.EMAIL, "***EMAIL***", True
        )
    
    # Маскирование телефона
    if 'phone' in sanitized:
        sanitized['phone'] = default_sanitizer.matcher.replace_with_pattern(
            sanitized['phone'], MaskingRule.PHONE, "***PHONE***", True
        )
    
    # Маскирование других чувствительных полей
    for key, value in sanitized.items():
        if isinstance(value, str):
            sanitized[key] = default_sanitizer.sanitize_value(value, key)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_user_data(value, salt)
    
    return sanitized


def create_masking_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """Создание отчета о маскировании"""
    report = {
        'total_keys': 0,
        'masked_keys': 0,
        'masked_values': 0,
        'masked_patterns': {}
    }
    
    def analyze_dict(d, path=""):
        nonlocal report
        
        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key
            report['total_keys'] += 1
            
            if default_sanitizer.is_sensitive_key(key):
                report['masked_keys'] += 1
                mask_type = key.lower().split('_')[-1]
                report['masked_patterns'][mask_type] = report['masked_patterns'].get(mask_type, 0) + 1
            
            if isinstance(value, str):
                # Проверка на паттерны
                for rule in MaskingRule:
                    if default_sanitizer.matcher.find_matches(value, rule):
                        report['masked_values'] += 1
                        rule_name = rule.value
                        report['masked_patterns'][rule_name] = report['masked_patterns'].get(rule_name, 0) + 1
            
            elif isinstance(value, dict):
                analyze_dict(value, current_path)
    
    analyze_dict(data)
    return report