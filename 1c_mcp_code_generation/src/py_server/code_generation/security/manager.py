
#!/usr/bin/env python3
"""
Security Manager для 1C AI MCP Code Generation

Менеджер безопасности для анализа и проверки безопасности генерируемого кода.

Версия: 1.0
Дата: 30.10.2025
"""

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class SecurityThreat:
    """Описание угрозы безопасности"""
    threat_id: str
    threat_type: str  # injection, escalation, disclosure, etc.
    severity: str  # critical, high, medium, low
    description: str
    affected_lines: List[int]
    remediation: str
    cwe_id: Optional[str] = None  # Common Weakness Enumeration

@dataclass
class SecurityAnalysisResult:
    """Результат анализа безопасности"""
    risk_level: str
    threats_found: List[SecurityThreat]
    security_score: int
    compliance_status: Dict[str, bool]
    recommendations: List[str]
    scan_timestamp: datetime

class SecurityManager:
    """Менеджер безопасности для генерации кода"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация менеджера безопасности
        
        Args:
            config: Конфигурация безопасности
        """
        self.config = config
        
        # Настройки безопасности
        self.max_code_size = config.get('max_code_size', 50000)
        self.risk_thresholds = config.get('risk_thresholds', {
            'low': 0.3,
            'medium': 0.6,
            'high': 0.8,
            'critical': 0.95
        })
        self.blocked_patterns = config.get('blocked_patterns', [])
        self.whitelist_patterns = config.get('whitelist_patterns', [])
        
        # Правила безопасности
        self.threat_rules = self._initialize_threat_rules()
        self.compliance_standards = self._initialize_compliance_standards()
        
        # Статистика
        self.scan_stats = {
            'total_scans': 0,
            'threats_detected': 0,
            'blocks_executed': 0,
            'false_positives': 0
        }
        
        logger.info("SecurityManager инициализирован")
    
    async def analyze_security(self, code: str, request_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Основной анализ безопасности кода
        
        Args:
            code: Код для анализа
            request_context: Контекст запроса
            
        Returns:
            Результат анализа безопасности
        """
        start_time = datetime.now()
        self.scan_stats['total_scans'] += 1
        
        # Проверка размера кода
        if len(code) > self.max_code_size:
            return {
                'risk_level': 'critical',
                'description': f'Код превышает максимальный размер: {len(code)} > {self.max_code_size}',
                'threats': [],
                'security_score': 0,
                'blocked': True
            }
        
        try:
            # Выполнение различных типов проверок
            threats = []
            
            # SQL-инъекции
            sql_threats = await self._detect_sql_injections(code)
            threats.extend(sql_threats)
            
            # XSS уязвимости
            xss_threats = await self._detect_xss_vulnerabilities(code)
            threats.extend(xss_threats)
            
            # Код-инъекции
            code_threats = await self._detect_code_injections(code)
            threats.extend(code_threats)
            
            # Эскалация привилегий
            privilege_threats = await self._detect_privilege_escalation(code)
            threats.extend(privilege_threats)
            
            # Утечки информации
            disclosure_threats = await self._detect_information_disclosure(code)
            threats.extend(disclosure_threats)
            
            # Проверка заблокированных паттернов
            blocked_threats = await self._detect_blocked_patterns(code)
            threats.extend(blocked_threats)
            
            # Анализ чувствительных данных
            sensitive_threats = await self._detect_sensitive_data(code)
            threats.extend(sensitive_threats)
            
            # Вычисление общего уровня риска
            risk_level = self._calculate_overall_risk_level(threats)
            security_score = self._calculate_security_score(threats)
            
            # Проверка соответствия стандартам
            compliance_status = await self._check_compliance_standards(threats, code)
            
            # Генерация рекомендаций
            recommendations = self._generate_security_recommendations(threats, risk_level)
            
            # Обновление статистики
            if threats:
                self.scan_stats['threats_detected'] += len(threats)
            
            result = {
                'risk_level': risk_level,
                'threats': [asdict(threat) for threat in threats],
                'security_score': security_score,
                'compliance_status': compliance_status,
                'recommendations': recommendations,
                'scan_timestamp': start_time.isoformat(),
                'scan_duration': (datetime.now() - start_time).total_seconds(),
                'blocked': risk_level == 'critical'
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка анализа безопасности: {e}")
            return {
                'risk_level': 'high',
                'description': f'Ошибка анализа безопасности: {str(e)}',
                'threats': [],
                'security_score': 0,
                'error': str(e)
            }
    
    async def _detect_sql_injections(self, code: str) -> List[SecurityThreat]:
        """Обнаружение SQL-инъекций"""
        
        threats = []
        
        # Паттерны SQL-инъекций
        sql_injection_patterns = [
            {
                'pattern': r'Выполнить\s*\(\s*["\'].*\+.*["\']',
                'threat_type': 'sql_injection',
                'severity': 'critical',
                'description': 'Выполнение SQL с конкатенацией строк',
                'remediation': 'Используйте параметризованные запросы',
                'cwe_id': 'CWE-89'
            },
            {
                'pattern': r'Запрос\s*\.\s*Текст\s*=.*\+',
                'threat_type': 'sql_injection',
                'severity': 'high',
                'description': 'Конкатенация в тексте SQL запроса',
                'remediation': 'Используйте параметризованные запросы',
                'cwe_id': 'CWE-89'
            },
            {
                'pattern': r'СтрЗаменить\s*\(\s*["\'].*["\']\s*,\s*.*\+.*\)',
                'threat_type': 'sql_injection',
                'severity': 'medium',
                'description': 'СтрЗаменить с конкатенацией может быть небезопасным',
                'remediation': 'Проверьте входные данные перед заменой',
                'cwe_id': 'CWE-20'
            },
            {
                'pattern': r'Содержит\s*\(\s*.*\+.*\)',
                'threat_type': 'sql_injection',
                'severity': 'medium',
                'description': 'Конкатенация в функции Содержит',
                'remediation': 'Используйте параметризованные запросы',
                'cwe_id': 'CWE-89'
            }
        ]
        
        lines = code.split('\n')
        
        for pattern_info in sql_injection_patterns:
            pattern = pattern_info['pattern']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    threat = SecurityThreat(
                        threat_id=f"sql_injection_{len(threats)}",
                        threat_type=pattern_info['threat_type'],
                        severity=pattern_info['severity'],
                        description=pattern_info['description'],
                        affected_lines=[line_num],
                        remediation=pattern_info['remediation'],
                        cwe_id=pattern_info.get('cwe_id')
                    )
                    threats.append(threat)
        
        return threats
    
    async def _detect_xss_vulnerabilities(self, code: str) -> List[SecurityThreat]:
        """Обнаружение XSS уязвимостей"""
        
        threats = []
        
        # Паттерны XSS уязвимостей
        xss_patterns = [
            {
                'pattern': r'ЭлементыФормы\.[^.]+\.Значение\s*=.*\+',
                'severity': 'high',
                'description': 'Присваивание значения с конкатенацией в элементы формы',
                'remediation': 'Проверьте и экранируйте входные данные',
                'cwe_id': 'CWE-79'
            },
            {
                'pattern': r'ТекстHTML\s*=.*\+',
                'severity': 'high',
                'description': 'Установка HTML с конкатенацией',
                'remediation': 'Используйте безопасные методы установки HTML',
                'cwe_id': 'CWE-79'
            },
            {
                'pattern': r'НавигационнаяСсылка\s*=.*\+',
                'severity': 'medium',
                'description': 'Установка навигационной ссылки с конкатенацией',
                'remediation': 'Валидируйте и экранируйте URL',
                'cwe_id': 'CWE-20'
            },
            {
                'pattern': r'Страница\s*\.\s*Заголовок\s*=.*\+',
                'severity': 'medium',
                'description': 'Установка заголовка страницы с конкатенацией',
                'remediation': 'Экранируйте пользовательский ввод',
                'cwe_id': 'CWE-79'
            }
        ]
        
        lines = code.split('\n')
        
        for pattern_info in xss_patterns:
            pattern = pattern_info['pattern']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    threat = SecurityThreat(
                        threat_id=f"xss_{len(threats)}",
                        threat_type='xss',
                        severity=pattern_info['severity'],
                        description=pattern_info['description'],
                        affected_lines=[line_num],
                        remediation=pattern_info['remediation'],
                        cwe_id=pattern_info.get('cwe_id')
                    )
                    threats.append(threat)
        
        return threats
    
    async def _detect_code_injections(self, code: str) -> List[SecurityThreat]:
        """Обнаружение инъекций кода"""
        
        threats = []
        
        # Паттерны инъекций кода
        code_injection_patterns = [
            {
                'pattern': r'Выполнить\s*\(',
                'severity': 'critical',
                'description': 'Выполнение произвольного кода',
                'remediation': 'Избегайте использования Выполнить()',
                'cwe_id': 'CWE-94'
            },
            {
                'pattern': r'ЗагрузитьИзФайла\s*\(',
                'severity': 'high',
                'description': 'Загрузка произвольного файла',
                'remediation': 'Проверяйте путь к файлу и тип файла',
                'cwe_id': 'CWE-73'
            },
            {
                'pattern': r'ПолучитьФайл\s*\(',
                'severity': 'high',
                'description': 'Получение файла из внешнего источника',
                'remediation': 'Проверяйте источник файла',
                'cwe_id': 'CWE-22'
            },
            {
                'pattern': r'ПодключитьВнешнююОбработку\s*\(',
                'severity': 'critical',
                'description': 'Подключение внешней обработки',
                'remediation': 'Используйте только проверенные обработки',
                'cwe_id': 'CWE-94'
            }
        ]
        
        lines = code.split('\n')
        
        for pattern_info in code_injection_patterns:
            pattern = pattern_info['pattern']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    threat = SecurityThreat(
                        threat_id=f"code_injection_{len(threats)}",
                        threat_type='code_injection',
                        severity=pattern_info['severity'],
                        description=pattern_info['description'],
                        affected_lines=[line_num],
                        remediation=pattern_info['remediation'],
                        cwe_id=pattern_info.get('cwe_id')
                    )
                    threats.append(threat)
        
        return threats
    
    async def _detect_privilege_escalation(self, code: str) -> List[SecurityThreat]:
        """Обнаружение попыток эскалации привилегий"""
        
        threats = []
        
        # Паттерны эскалации привилегий
        privilege_patterns = [
            {
                'pattern': r'Роли\s*\.\s*ПолныеПрава',
                'severity': 'high',
                'description': 'Использование роли с полными правами',
                'remediation': 'Используйте минимально необходимые права',
                'cwe_id': 'CWE-732'
            },
            {
                'pattern': r'Роли\s*\.\s*АдминистраторСистемы',
                'severity': 'medium',
                'description': 'Использование роли администратора',
                'remediation': 'Ограничьте использование админских прав',
                'cwe_id': 'CWE-732'
            },
            {
                'pattern': r'УстановитьПривилегированныйРежим\s*\(',
                'severity': 'high',
                'description': 'Установка привилегированного режима',
                'remediation': 'Используйте привилегированный режим только при необходимости',
                'cwe_id': 'CWE-269'
            }
        ]
        
        lines = code.split('\n')
        
        for pattern_info in privilege_patterns:
            pattern = pattern_info['pattern']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    threat = SecurityThreat(
                        threat_id=f"privilege_escalation_{len(threats)}",
                        threat_type='privilege_escalation',
                        severity=pattern_info['severity'],
                        description=pattern_info['description'],
                        affected_lines=[line_num],
                        remediation=pattern_info['remediation'],
                        cwe_id=pattern_info.get('cwe_id')
                    )
                    threats.append(threat)
        
        return threats
    
    async def _detect_information_disclosure(self, code: str) -> List[SecurityThreat]:
        """Обнаружение утечек информации"""
        
        threats = []
        
        # Паттерны утечек информации
        disclosure_patterns = [
            {
                'pattern': r'Сообщить\s*\(\s*.*[Пп]ароль.*\)',
                'severity': 'high',
                'description': 'Вывод пароля в сообщении',
                'remediation': 'Не выводите пароли и другие секретные данные',
                'cwe_id': 'CWE-532'
            },
            {
                'pattern': r'Сообщить\s*\(\s*.*[Кк]люч.*\)',
                'severity': 'high',
                'description': 'Вывод ключа в сообщении',
                'remediation': 'Не выводите криптографические ключи',
                'cwe_id': 'CWE-532'
            },
            {
                'pattern': r'ЗаписьЛога.*пароль',
                'severity': 'medium',
                'description': 'Запись пароля в лог',
                'remediation': 'Не записывайте пароли в логи',
                'cwe_id': 'CWE-532'
            },
            {
                'pattern': r'ЗаписьЛога.*ключ',
                'severity': 'medium',
                'description': 'Запись ключа в лог',
                'remediation': 'Не записывайте ключи в логи',
                'cwe_id': 'CWE-532'
            },
            {
                'pattern': r'Сообщить\s*\(\s*.*token.*\)',
                'severity': 'medium',
                'description': 'Вывод токена в сообщении',
                'remediation': 'Не выводите токены и маркеры доступа',
                'cwe_id': 'CWE-532'
            }
        ]
        
        lines = code.split('\n')
        
        for pattern_info in disclosure_patterns:
            pattern = pattern_info['pattern']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    threat = SecurityThreat(
                        threat_id=f"information_disclosure_{len(threats)}",
                        threat_type='information_disclosure',
                        severity=pattern_info['severity'],
                        description=pattern_info['description'],
                        affected_lines=[line_num],
                        remediation=pattern_info['remediation'],
                        cwe_id=pattern_info.get('cwe_id')
                    )
                    threats.append(threat)
        
        return threats
    
    async def _detect_blocked_patterns(self, code: str) -> List[SecurityThreat]:
        """Обнаружение заблокированных паттернов"""
        
        threats = []
        
        if not self.blocked_patterns:
            return threats
        
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in self.blocked_patterns:
                if pattern in line:
                    threat = SecurityThreat(
                        threat_id=f"blocked_pattern_{len(threats)}",
                        threat_type='blocked_pattern',
                        severity='critical',
                        description=f'Обнаружен заблокированный паттерн: {pattern}',
                        affected_lines=[line_num],
                        remediation='Удалите заблокированный код',
                        cwe_id='CWE-184'  # Incomplete Blacklist
                    )
                    threats.append(threat)
                    self.scan_stats['blocks_executed'] += 1
        
        return threats
    
    async def _detect_sensitive_data(self, code: str) -> List[SecurityThreat]:
        """Обнаружение чувствительных данных в коде"""
        
        threats = []
        
        # Паттерны чувствительных данных
        sensitive_patterns = [
            {
                'pattern': r'["\']?[Пп]ароль["\']?\s*=\s*["\'][^"\']*["\']',
                'severity': 'high',
                'description': 'Хранение пароля в коде',
                'remediation': 'Используйте безопасное хранение паролей'
            },
            {
                'pattern': r'["\']?[Кк]люч["\']?\s*=\s*["\'][^"\']*["\']',
                'severity': 'high',
                'description': 'Хранение ключа в коде',
                'remediation': 'Используйте безопасное хранение ключей'
            },
            {
                'pattern': r'["\']?[Тт]окен["\']?\s*=\s*["\'][^"\']*["\']',
                'severity': 'medium',
                'description': 'Хранение токена в коде',
                'remediation': 'Используйте безопасное хранение токенов'
            },
            {
                'pattern': r'connection_string\s*=',
                'severity': 'medium',
                'description': 'Хранение строки подключения в коде',
                'remediation': 'Используйте безопасное хранение строк подключения'
            }
        ]
        
        lines = code.split('\n')
        
        for pattern_info in sensitive_patterns:
            pattern = pattern_info['pattern']
            
            for line_num, line in enumerate(lines, 1):
                if re.search(pattern, line, re.IGNORECASE):
                    threat = SecurityThreat(
                        threat_id=f"sensitive_data_{len(threats)}",
                        threat_type='sensitive_data_exposure',
                        severity=pattern_info['severity'],
                        description=pattern_info['description'],
                        affected_lines=[line_num],
                        remediation=pattern_info['remediation']
                    )
                    threats.append(threat)
        
        return threats
    
    def _calculate_overall_risk_level(self, threats: List[SecurityThreat]) -> str:
        """Вычисление общего уровня риска"""
        
        if not threats:
            return 'low'
        
        severity_scores = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }
        
        # Подсчет угроз по уровням серьезности
        threat_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        for threat in threats:
            threat_counts[threat.severity] += 1
        
        # Вычисление взвешенного риска
        total_threats = len(threats)
        weighted_risk = (
            threat_counts['critical'] * 4 +
            threat_counts['high'] * 3 +
            threat_counts['medium'] * 2 +
            threat_counts['low'] * 1
        ) / max(1, total_threats)
        
        # Определение уровня риска
        if threat_counts['critical'] > 0:
            return 'critical'
        elif weighted_risk >= self.risk_thresholds['high']:
            return 'high'
        elif weighted_risk >= self.risk_thresholds['medium']:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_security_score(self, threats: List[SecurityThreat]) -> int:
        """Вычисление балла безопасности"""
        
        if not threats:
            return 100
        
        penalty_per_severity = {
            'critical': 30,
            'high': 20,
            'medium': 10,
            'low': 5
        }
        
        total_penalty = sum(
            penalty_per_severity[threat.severity] for threat in threats
        )
        
        return max(0, 100 - total_penalty)
    
    async def _check_compliance_standards(self, threats: List[SecurityThreat], code: str) -> Dict[str, bool]:
        """Проверка соответствия стандартам безопасности"""
        
        compliance_status = {
            'owasp_top_10': self._check_owasp_compliance(threats),
            'nist_framework': self._check_nist_compliance(threats, code),
            'iso_27001': self._check_iso_compliance(threats),
            'pci_dss': self._check_pci_compliance(threats)
        }
        
        return compliance_status
    
    def _check_owasp_compliance(self, threats: List[SecurityThreat]) -> bool:
        """Проверка соответствия OWASP Top 10"""
        
        # Проверка наличия уязвимостей из OWASP Top 10
        owasp_threat_types = {
            'sql_injection': 'A03:2021 – Injection',
            'xss': 'A03:2021 – Injection',
            'code_injection': 'A03:2021 – Injection',
            'information_disclosure': 'A01:2021 – Broken Access Control'
        }
        
        for threat in threats:
            if threat.threat_type in owasp_threat_types:
                return False
        
        return True
    
    def _check_nist_compliance(self, threats: List[SecurityThreat], code: str) -> bool:
        """Проверка соответствия NIST Framework"""
        
        # Проверка основных требований NIST
        critical_threats = [t for t in threats if t.severity in ['critical', 'high']]
        
        if critical_threats:
            return False
        
        # Проверка наличия базовых мер безопасности
        has_authentication = 'Роли' in code or 'Аутентификация' in code
        has_authorization = 'Права' in code or 'Разрешения' in code
        
        return has_authentication and has_authorization
    
    def _check_iso_compliance(self, threats: List[SecurityThreat]) -> bool:
        """Проверка соответствия ISO 27001"""
        
        # Проверка критических уязвимостей
        if any(t.severity == 'critical' for t in threats):
            return False
        
        # Проверка наличия мер защиты информации
        critical_threats = [t for t in threats if t.severity in ['high', 'critical']]
        
        return len(critical_threats) == 0
    
    def _check_pci_compliance(self, threats: List[SecurityThreat]) -> bool:
        """Проверка соответствия PCI DSS"""
        
        # Проверка уязвимостей связанных с платежными данными
        payment_threats = []
        
        for threat in threats:
            if any(keyword in threat.description.lower() for keyword in 
                   ['payment', 'card', 'credit', 'payment_data']):
                payment_threats.append(threat)
        
        # PCI DSS не допускает уязвимостей высокого уровня
        high_severity_threats = [t for t in payment_threats if t.severity in ['high', 'critical']]
        
        return len(high_severity_threats) == 0
    
    def _generate_security_recommendations(self, threats: List[SecurityThreat], risk_level: str) -> List[str]:
        """Генерация рекомендаций по безопасности"""
        
        recommendations = []
        
        # Общие рекомендации на основе уровня риска
        if risk_level == 'critical':
            recommendations.extend([
                'Немедленно устраните критические уязвимости',
                'Проведите полный аудит безопасности',
                'Рассмотрите возможность привлечения внешних экспертов'
            ])
        elif risk_level == 'high':
            recommendations.extend([
                'Устраните высокорисковые уязвимости в ближайшее время',
                'Внедрите дополнительные меры защиты'
            ])
        
        # Рекомендации по типам угроз
        threat_types = set(threat.threat_type for threat in threats)
        
        if 'sql_injection' in threat_types:
            recommendations.append('Используйте параметризованные запросы для предотвращения SQL-инъекций')
        
        if 'xss' in threat_types:
            recommendations.append('Валидируйте и экранируйте пользовательский ввод')
        
        if 'code_injection' in threat_types:
            recommendations.append('Избегайте использования функций выполнения произвольного кода')
        
        if 'information_disclosure' in threat_types:
            recommendations.append('Не выводите конфиденциальную информацию в логи и сообщения')
        
        # Общие рекомендации
        recommendations.extend([
            'Регулярно проводите код-ревью с фокусом на безопасность',
            'Внедрите автоматические проверки безопасности в CI/CD',
            'Обучите команду основам безопасной разработки',
            'Используйте принцип минимально необходимых прав доступа'
        ])
        
        return recommendations
    
    def _initialize_threat_rules(self) -> Dict[str, Any]:
        """Инициализация правил угроз"""
        
        return {
            'sql_injection': {
                'enabled': True,
                'patterns': [
                    'Выполнить.*\+',
                    'Запрос.*Текст.*\+',
                    'СтрЗаменить.*\+'
                ]
            },
            'xss': {
                'enabled': True,
                'patterns': [
                    'ЭлементыФормы.*Значение.*\+',
                    'ТекстHTML.*\+',
                    'НавигационнаяСсылка.*\+'
                ]
            },
            'code_injection': {
                'enabled': True,
                'patterns': [
                    'Выполнить\(',
                    'ЗагрузитьИзФайла\(',
                    'ПодключитьВнешнююОбработку\('
                ]
            }
        }
    
    def _initialize_compliance_standards(self) -> Dict[str, Any]:
        """Инициализация стандартов соответствия"""
        
        return {
            'owasp_top_10': {
                'enabled': True,
                'mandatory_checks': ['injection', 'broken_auth', 'sensitive_data']
            },
            'nist_framework': {
                'enabled': True,
                'risk_tolerance': 'low'
            },
            'iso_27001': {
                'enabled': True,
                'risk_management': True
            },
            'pci_dss': {
                'enabled': False,  # Включается только для платежных систем
                'cardholder_data': True
            }
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса менеджера безопасности"""
        return {
            'initialized': True,
            'scan_stats': self.scan_stats.copy(),
            'risk_thresholds': self.risk_thresholds,
            'blocked_patterns_count': len(self.blocked_patterns),
            'threat_rules': list(self.threat_rules.keys()),
            'compliance_standards': list(self.compliance_standards.keys()),
            'version': '1.0'
        }
    
    def add_blocked_pattern(self, pattern: str):
        """Добавление нового заблокированного паттерна"""
        if pattern not in self.blocked_patterns:
            self.blocked_patterns.append(pattern)
            logger.info(f"Добавлен заблокированный паттерн: {pattern}")
    
    def remove_blocked_pattern(self, pattern: str):
        """Удаление заблокированного паттерна"""
        if pattern in self.blocked_patterns:
            self.blocked_patterns.remove(pattern)
            logger.info(f"Удален заблокированный паттерн: {pattern}")
    
    def get_blocked_patterns(self) -> List[str]:
        """Получение списка заблокированных паттернов"""
        return self.blocked_patterns.copy()
    
    def update_risk_thresholds(self, thresholds: Dict[str, float]):
        """Обновление порогов риска"""
        self.risk_thresholds.update(thresholds)
        logger.info(f"Обновлены пороги риска: {thresholds}")
    
    def reset_statistics(self):
        """Сброс статистики"""
        self.scan_stats = {
            'total_scans': 0,
            'threats_detected': 0,
            'blocks_executed': 0,
            'false_positives': 0
        }
        logger.info("Статистика безопасности сброшена")