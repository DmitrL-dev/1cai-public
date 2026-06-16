
#!/usr/bin/env python3
"""
Code Validator для 1C AI MCP Code Generation

Валидатор кода 1С для проверки синтаксиса, качества, безопасности и стандартов.

Версия: 1.0
Дата: 30.10.2025
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Результат валидации"""
    valid: bool
    score: int
    errors: List[str]
    warnings: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any]

@dataclass
class SyntaxValidationResult:
    """Результат синтаксической валидации"""
    line_number: int
    column: int
    error_type: str
    message: str
    severity: str  # error, warning, info

@dataclass
class StandardComplianceResult:
    """Результат проверки соответствия стандартам"""
    rule_id: str
    rule_name: str
    compliance_level: float  # 0.0 - 1.0
    violations: List[str]
    recommendations: List[str]

@dataclass
class SecurityAnalysisResult:
    """Результат анализа безопасности"""
    risk_level: str  # low, medium, high, critical
    vulnerabilities: List[Dict[str, Any]]
    security_score: int

class CodeValidator:
    """Валидатор кода 1С"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация валидатора
        
        Args:
            config: Конфигурация валидатора
        """
        self.config = config
        
        # Настройки
        self.enabled_checks = config.get('enabled_checks', ['syntax', 'standards', 'security', 'performance'])
        self.strict_mode = config.get('strict_mode', False)
        self.auto_fix = config.get('auto_fix', False)
        self.timeout = config.get('timeout', 10)
        
        # Статистика
        self.validation_stats = {
            'total_validations': 0,
            'validation_errors': 0,
            'validation_warnings': 0,
            'average_score': 0.0
        }
        
        # Правила валидации
        self.syntax_rules = self._initialize_syntax_rules()
        self.standard_rules = self._initialize_standard_rules()
        self.security_rules = self._initialize_security_rules()
        self.performance_rules = self._initialize_performance_rules()
        
        logger.info("CodeValidator инициализирован")
    
    async def validate_code(self, code: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Основная функция валидации кода
        
        Args:
            code: Код для валидации
            context: Контекст валидации
            
        Returns:
            Результат валидации
        """
        start_time = datetime.now()
        self.validation_stats['total_validations'] += 1
        
        # Результат по умолчанию
        result = {
            'valid': True,
            'score': 100,
            'errors': [],
            'warnings': [],
            'recommendations': [],
            'metadata': {
                'validation_time': 0,
                'checks_performed': [],
                'code_hash': hashlib.md5(code.encode('utf-8')).hexdigest(),
                'code_size': len(code),
                'lines_count': len(code.split('\n'))
            }
        }
        
        try:
            # Выполнение проверок
            check_results = {}
            
            if 'syntax' in self.enabled_checks:
                syntax_result = await self._validate_syntax(code)
                check_results['syntax'] = syntax_result
                self._update_result_with_syntax(result, syntax_result)
            
            if 'standards' in self.enabled_checks:
                standards_result = await self._validate_standards(code, context)
                check_results['standards'] = standards_result
                self._update_result_with_standards(result, standards_result)
            
            if 'security' in self.enabled_checks:
                security_result = await self._validate_security(code)
                check_results['security'] = security_result
                self._update_result_with_security(result, security_result)
            
            if 'performance' in self.enabled_checks:
                performance_result = await self._validate_performance(code, context)
                check_results['performance'] = performance_result
                self._update_result_with_performance(result, performance_result)
            
            # Обновление метаданных
            execution_time = (datetime.now() - start_time).total_seconds()
            result['metadata']['validation_time'] = execution_time
            result['metadata']['checks_performed'] = list(check_results.keys())
            
            # Вычисление итогового балла
            result['score'] = self._calculate_total_score(result)
            
            # Определение статуса валидности
            result['valid'] = len(result['errors']) == 0
            
            # Автоматическое исправление (если включено)
            if self.auto_fix and not result['valid']:
                result['fixed_code'] = await self._auto_fix_code(code, result['errors'])
            
            # Обновление статистики
            self._update_validation_stats(result)
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"Ошибка валидации: {str(e)}")
            result['score'] = 0
            self.validation_stats['validation_errors'] += 1
            logger.error(f"Ошибка валидации кода: {e}")
        
        return result
    
    async def _validate_syntax(self, code: str) -> List[SyntaxValidationResult]:
        """Синтаксическая валидация"""
        
        errors = []
        
        try:
            # Проверка баланса скобок
            bracket_errors = self._check_bracket_balance(code)
            errors.extend(bracket_errors)
            
            # Проверка корректности процедур и функций
            procedure_errors = self._check_procedures_functions(code)
            errors.extend(procedure_errors)
            
            # Проверка синтаксиса областей
            region_errors = self._check_regions(code)
            errors.extend(region_errors)
            
            # Проверка корректности строк
            string_errors = self._check_string_syntax(code)
            errors.extend(string_errors)
            
            # Проверка комментариев
            comment_errors = self._check_comment_syntax(code)
            errors.extend(comment_errors)
            
        except Exception as e:
            logger.error(f"Ошибка синтаксической валидации: {e}")
            errors.append(SyntaxValidationResult(
                line_number=0, column=0, error_type="validation_error",
                message=f"Критическая ошибка валидации: {str(e)}", severity="error"
            ))
        
        return errors
    
    async def _validate_standards(self, code: str, context: Dict[str, Any]) -> List[StandardComplianceResult]:
        """Проверка соответствия стандартам"""
        
        results = []
        
        # Проверка именования
        naming_result = self._check_naming_standards(code)
        results.append(naming_result)
        
        # Проверка структуры кода
        structure_result = self._check_code_structure(code)
        results.append(structure_result)
        
        # Проверка документирования
        documentation_result = self._check_documentation_standards(code)
        results.append(documentation_result)
        
        # Проверка архитектурных принципов
        architecture_result = self._check_architecture_standards(code)
        results.append(architecture_result)
        
        return results
    
    async def _validate_security(self, code: str) -> SecurityAnalysisResult:
        """Проверка безопасности"""
        
        vulnerabilities = []
        risk_factors = []
        
        # Проверка SQL-инъекций
        sql_vulnerabilities = self._check_sql_injections(code)
        vulnerabilities.extend(sql_vulnerabilities)
        
        # Проверка XSS уязвимостей
        xss_vulnerabilities = self._check_xss_vulnerabilities(code)
        vulnerabilities.extend(xss_vulnerabilities)
        
        # Проверка опасных функций
        dangerous_functions = self._check_dangerous_functions(code)
        vulnerabilities.extend(dangerous_functions)
        
        # Проверка утечек информации
        information_leaks = self._check_information_leaks(code)
        vulnerabilities.extend(information_leaks)
        
        # Вычисление уровня риска
        risk_level = self._calculate_security_risk_level(vulnerabilities)
        security_score = self._calculate_security_score(vulnerabilities)
        
        return SecurityAnalysisResult(
            risk_level=risk_level,
            vulnerabilities=vulnerabilities,
            security_score=security_score
        )
    
    async def _validate_performance(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Проверка производительности"""
        
        issues = []
        metrics = {}
        
        # Анализ цикломатической сложности
        complexity = self._calculate_cyclomatic_complexity(code)
        metrics['cyclomatic_complexity'] = complexity
        
        if complexity > 20:
            issues.append(f"Высокая цикломатическая сложность: {complexity}")
        
        # Анализ глубины вложенности
        nesting_depth = self._calculate_nesting_depth(code)
        metrics['nesting_depth'] = nesting_depth
        
        if nesting_depth > 5:
            issues.append(f"Большая глубина вложенности: {nesting_depth}")
        
        # Проверка на потенциальные проблемы производительности
        performance_issues = self._check_performance_issues(code)
        issues.extend(performance_issues)
        
        # Анализ размера функций
        function_sizes = self._analyze_function_sizes(code)
        metrics['function_sizes'] = function_sizes
        
        large_functions = [f for f in function_sizes if f > 50]
        if large_functions:
            issues.append(f"Найдено {len(large_functions)} больших функций")
        
        return {
            'issues': issues,
            'metrics': metrics,
            'performance_score': self._calculate_performance_score(issues, metrics)
        }
    
    def _check_bracket_balance(self, code: str) -> List[SyntaxValidationResult]:
        """Проверка баланса скобок"""
        
        errors = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            bracket_stack = []
            
            for col, char in enumerate(line):
                if char in '([{':
                    bracket_stack.append((char, col))
                elif char in ')]}':
                    if not bracket_stack:
                        errors.append(SyntaxValidationResult(
                            line_number=line_num,
                            column=col,
                            error_type="unmatched_bracket",
                            message=f"Незакрытая закрывающая скобка: {char}",
                            severity="error"
                        ))
                    else:
                        opening_bracket, opening_col = bracket_stack.pop()
                        if not self._brackets_match(opening_bracket, char):
                            errors.append(SyntaxValidationResult(
                                line_number=line_num,
                                column=col,
                                error_type="mismatched_brackets",
                                message=f"Несоответствующие скобки: {opening_bracket} и {char}",
                                severity="error"
                            ))
        
        # Проверка незакрытых скобок
        for bracket, col in bracket_stack:
            errors.append(SyntaxValidationResult(
                line_number=len(lines),
                column=col,
                error_type="unclosed_bracket",
                message=f"Незакрытая скобка: {bracket}",
                severity="error"
            ))
        
        return errors
    
    def _check_procedures_functions(self, code: str) -> List[SyntaxValidationResult]:
        """Проверка процедур и функций"""
        
        errors = []
        lines = code.split('\n')
        
        procedure_stack = []
        
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Поиск начал процедур/функций
            if line_stripped.startswith('Процедура ') or line_stripped.startswith('Функция '):
                procedure_stack.append((line_num, line_stripped.split()[1]))
            
            # Поиск окончаний
            elif line_stripped == 'КонецПроцедуры' or line_stripped == 'КонецФункции':
                if not procedure_stack:
                    errors.append(SyntaxValidationResult(
                        line_number=line_num,
                        column=0,
                        error_type="unexpected_end",
                        message="Конец процедуры без начала",
                        severity="error"
                    ))
                else:
                    procedure_stack.pop()
        
        # Проверка незакрытых процедур
        for line_num, proc_name in procedure_stack:
            errors.append(SyntaxValidationResult(
                line_number=line_num,
                column=0,
                error_type="unclosed_procedure",
                message=f"Незакрытая процедура: {proc_name}",
                severity="error"
            ))
        
        return errors
    
    def _check_regions(self, code: str) -> List[SyntaxValidationResult]:
        """Проверка областей"""
        
        errors = []
        lines = code.split('\n')
        
        region_stack = []
        
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            if line_stripped.startswith('#Область '):
                region_name = line_stripped[9:].strip()
                region_stack.append((line_num, region_name))
            
            elif line_stripped == '#КонецОбласти':
                if not region_stack:
                    errors.append(SyntaxValidationResult(
                        line_number=line_num,
                        column=0,
                        error_type="unexpected_region_end",
                        message="Конец области без начала",
                        severity="error"
                    ))
                else:
                    region_stack.pop()
        
        # Проверка незакрытых областей
        for line_num, region_name in region_stack:
            errors.append(SyntaxValidationResult(
                line_number=line_num,
                column=0,
                error_type="unclosed_region",
                message=f"Незакрытая область: {region_name}",
                severity="error"
            ))
        
        return errors
    
    def _check_string_syntax(self, code: str) -> List[SyntaxValidationResult]:
        """Проверка синтаксиса строк"""
        
        errors = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            quote_count = line.count('"')
            
            # Проверка нечетного количества кавычек
            if quote_count % 2 != 0:
                errors.append(SyntaxValidationResult(
                    line_number=line_num,
                    column=0,
                    error_type="unbalanced_quotes",
                    message="Нечетное количество кавычек в строке",
                    severity="error"
                ))
            
            # Проверка экранирования
            i = 0
            while i < len(line) - 1:
                if line[i] == '"' and line[i + 1] == '"':
                    # Правильное экранирование кавычки
                    i += 2
                elif line[i] == '\\' and line[i + 1] == '"':
                    # Неправильное экранирование
                    errors.append(SyntaxValidationResult(
                        line_number=line_num,
                        column=i,
                        error_type="invalid_escape",
                        message="Неправильное экранирование кавычки",
                        severity="warning"
                    ))
                    i += 1
                else:
                    i += 1
        
        return errors
    
    def _check_comment_syntax(self, code: str) -> List[SyntaxValidationResult]:
        """Проверка синтаксиса комментариев"""
        
        errors = []
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            # Проверка корректности комментариев
            comment_pos = line.find('//')
            
            if comment_pos > 0:
                # Проверка что перед // нет кода (за исключением пробелов)
                before_comment = line[:comment_pos].strip()
                if before_comment and not before_comment.endswith(';') and not before_comment.endswith(','):
                    errors.append(SyntaxValidationResult(
                        line_number=line_num,
                        column=comment_pos,
                        error_type="comment_placement",
                        message="Комментарий должен быть после оператора",
                        severity="warning"
                    ))
        
        return errors
    
    def _check_naming_standards(self, code: str) -> StandardComplianceResult:
        """Проверка стандартов именования"""
        
        violations = []
        recommendations = []
        
        # Паттерны для проверки именования
        procedure_pattern = r'Процедура\s+([a-zA-Zа-яА-Я_][a-zA-Zа-яА-Я0-9_]*)\s*\('
        function_pattern = r'Функция\s+([a-zA-Zа-яА-Я_][a-zA-Zа-яА-Я0-9_]*)\s*\('
        variable_pattern = r'Перем\s+([a-zA-Zа-яА-Я_][a-zA-Zа-яА-Я0-9_]*)'
        
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Проверка процедур
            for match in re.finditer(procedure_pattern, line_stripped):
                proc_name = match.group(1)
                if not self._is_valid_procedure_name(proc_name):
                    violations.append(f"Строка {line_num}: Некорректное имя процедуры '{proc_name}'")
            
            # Проверка функций
            for match in re.finditer(function_pattern, line_stripped):
                func_name = match.group(1)
                if not self._is_valid_function_name(func_name):
                    violations.append(f"Строка {line_num}: Некорректное имя функции '{func_name}'")
            
            # Проверка переменных
            for match in re.finditer(variable_pattern, line_stripped):
                var_name = match.group(1)
                if not self._is_valid_variable_name(var_name):
                    violations.append(f"Строка {line_num}: Некорректное имя переменной '{var_name}'")
        
        # Рекомендации
        if violations:
            recommendations.append("Используйте CamelCase для процедур и функций")
            recommendations.append("Имена должны быть описательными")
        
        compliance_level = max(0, 1.0 - len(violations) * 0.1)
        
        return StandardComplianceResult(
            rule_id="naming_standards",
            rule_name="Стандарты именования",
            compliance_level=compliance_level,
            violations=violations,
            recommendations=recommendations
        )
    
    def _check_code_structure(self, code: str) -> StandardComplianceResult:
        """Проверка структуры кода"""
        
        violations = []
        recommendations = []
        
        lines = code.split('\n')
        has_regions = False
        has_program_interface = False
        
        for line in lines:
            if line.strip().startswith('#Область'):
                has_regions = True
            if line.strip().startswith('#Область ПрограммныйИнтерфейс'):
                has_program_interface = True
        
        # Проверка использования областей
        if not has_regions:
            violations.append("Отсутствует структурирование с помощью областей")
            recommendations.append("Используйте области для группировки кода")
        
        # Проверка области ПрограммныйИнтерфейс
        if not has_program_interface:
            violations.append("Отсутствует область ПрограммныйИнтерфейс")
            recommendations.append("Добавьте область ПрограммныйИнтерфейс для внешних методов")
        
        # Проверка пустых строк
        consecutive_empty_lines = 0
        for line in lines:
            if not line.strip():
                consecutive_empty_lines += 1
                if consecutive_empty_lines > 2:
                    violations.append(f"Слишком много пустых строк подряд: {consecutive_empty_lines}")
                    break
            else:
                consecutive_empty_lines = 0
        
        compliance_level = max(0, 1.0 - len(violations) * 0.2)
        
        return StandardComplianceResult(
            rule_id="code_structure",
            rule_name="Структура кода",
            compliance_level=compliance_level,
            violations=violations,
            recommendations=recommendations
        )
    
    def _check_documentation_standards(self, code: str) -> StandardComplianceResult:
        """Проверка стандартов документирования"""
        
        violations = []
        recommendations = []
        
        lines = code.split('\n')
        procedure_count = 0
        documented_procedures = 0
        
        for line in lines:
            line_stripped = line.strip()
            
            if line_stripped.startswith('Процедура ') or line_stripped.startswith('Функция '):
                procedure_count += 1
                
                # Проверка наличия комментария перед процедурой
                line_index = lines.index(line)
                has_comment = False
                
                # Поиск комментария в предыдущих строках
                for i in range(max(0, line_index - 3), line_index):
                    if lines[i].strip().startswith('//'):
                        has_comment = True
                        break
                
                if has_comment:
                    documented_procedures += 1
                else:
                    violations.append(f"Процедура без документации: {line_stripped}")
        
        # Проверка процента документирования
        if procedure_count > 0:
            documentation_ratio = documented_procedures / procedure_count
            if documentation_ratio < 0.8:
                recommendations.append(f"Увеличьте покрытие документацией: {documentation_ratio:.1%}")
        
        compliance_level = documented_procedures / max(1, procedure_count)
        
        return StandardComplianceResult(
            rule_id="documentation",
            rule_name="Документирование",
            compliance_level=compliance_level,
            violations=violations,
            recommendations=recommendations
        )
    
    def _check_architecture_standards(self, code: str) -> StandardComplianceResult:
        """Проверка архитектурных стандартов"""
        
        violations = []
        recommendations = []
        
        # Проверка принципа единственной ответственности
        large_procedures = self._find_large_procedures(code)
        if large_procedures:
            violations.append(f"Найдены слишком большие процедуры: {len(large_procedures)}")
            recommendations.append("Разбейте большие процедуры на более мелкие")
        
        # Проверка зависимостей
        global_usage = self._analyze_global_usage(code)
        if global_usage['count'] > 5:
            violations.append(f"Слишком много глобальных обращений: {global_usage['count']}")
            recommendations.append("Избегайте избыточного использования глобальных объектов")
        
        compliance_level = max(0, 1.0 - len(violations) * 0.15)
        
        return StandardComplianceResult(
            rule_id="architecture",
            rule_name="Архитектурные принципы",
            compliance_level=compliance_level,
            violations=violations,
            recommendations=recommendations
        )
    
    def _check_sql_injections(self, code: str) -> List[Dict[str, Any]]:
        """Проверка SQL-инъекций"""
        
        vulnerabilities = []
        
        # Паттерны потенциальных SQL-инъекций
        dangerous_patterns = [
            r'Выполнить\s*\(\s*["\'].*\+.*["\']',  # Выполнить с конкатенацией
            r'Запрос\s*\.\s*Текст\s*=.*\+',        # Конкатенация в тексте запроса
            r'СтрЗаменить.*["\']\s*\+',            # СтрЗаменить с конкатенацией
        ]
        
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulnerabilities.append({
                        'type': 'sql_injection',
                        'line': line_num,
                        'description': 'Потенциальная SQL-инъекция через конкатенацию строк',
                        'severity': 'high',
                        'line_content': line.strip()
                    })
        
        return vulnerabilities
    
    def _check_xss_vulnerabilities(self, code: str) -> List[Dict[str, Any]]:
        """Проверка XSS уязвимостей"""
        
        vulnerabilities = []
        
        # Паттерны XSS уязвимостей
        xss_patterns = [
            r'ЭлементыФормы\.[^.]+\.Значение\s*=.*\+',  # Присваивание с конкатенацией
            r'ТекстHTML\s*=.*\+',                        # Установка HTML с конкатенацией
            r'НавигационнаяСсылка\s*=.*\+',            # Установка ссылки с конкатенацией
        ]
        
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in xss_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulnerabilities.append({
                        'type': 'xss',
                        'line': line_num,
                        'description': 'Потенциальная XSS уязвимость через конкатенацию',
                        'severity': 'medium',
                        'line_content': line.strip()
                    })
        
        return vulnerabilities
    
    def _check_dangerous_functions(self, code: str) -> List[Dict[str, Any]]:
        """Проверка опасных функций"""
        
        vulnerabilities = []
        
        # Опасные функции
        dangerous_functions = {
            'Выполнить': {'severity': 'high', 'description': 'Выполнение произвольного кода'},
            'ЗагрузитьИзФайла': {'severity': 'medium', 'description': 'Загрузка произвольного файла'},
            'ПолучитьФайл': {'severity': 'medium', 'description': 'Получение файла из внешнего источника'},
            'ПодключитьВнешнююОбработку': {'severity': 'high', 'description': 'Подключение внешней обработки'},
        }
        
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for func_name, func_info in dangerous_functions.items():
                if re.search(r'\b' + func_name + r'\s*\(', line, re.IGNORECASE):
                    vulnerabilities.append({
                        'type': 'dangerous_function',
                        'function': func_name,
                        'line': line_num,
                        'description': f"Использование опасной функции: {func_info['description']}",
                        'severity': func_info['severity'],
                        'line_content': line.strip()
                    })
        
        return vulnerabilities
    
    def _check_information_leaks(self, code: str) -> List[Dict[str, Any]]:
        """Проверка утечек информации"""
        
        vulnerabilities = []
        
        # Паттерны утечек информации
        leak_patterns = [
            r'Сообщить\s*\(\s*.*[Пп]ароль.*\)',       # Вывод паролей
            r'Сообщить\s*\(\s*.*[Кк]люч.*\)',        # Вывод ключей
            r'ЗаписьЛога.*пароль',                    # Запись паролей в лог
            r'ЗаписьЛога.*ключ',                      # Запись ключей в лог
        ]
        
        lines = code.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            for pattern in leak_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulnerabilities.append({
                        'type': 'information_leak',
                        'line': line_num,
                        'description': 'Потенциальная утечка конфиденциальной информации',
                        'severity': 'high',
                        'line_content': line.strip()
                    })
        
        return vulnerabilities
    
    def _calculate_cyclomatic_complexity(self, code: str) -> int:
        """Вычисление цикломатической сложности"""
        
        complexity = 1  # Базовое значение
        
        # Ключевые слова, увеличивающие сложность
        complexity_keywords = [
            r'\bЕсли\b', r'\bИначеЕсли\b', r'\bИначе\b',
            r'\bДля\b', r'\bПо\b', r'\bПока\b',
            r'\bПопытка\b', r'\bИсключение\b',
            r'\bИ\b', r'\bИЛИ\b', r'\bНЕ\b'
        ]
        
        for keyword in complexity_keywords:
            complexity += len(re.findall(keyword, code, re.IGNORECASE))
        
        return complexity
    
    def _calculate_nesting_depth(self, code: str) -> int:
        """Вычисление максимальной глубины вложенности"""
        
        max_depth = 0
        current_depth = 0
        
        lines = code.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            
            # Увеличение глубины
            if any(keyword in line_stripped for keyword in ['Если', 'Для', 'Пока', 'Попытка']):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            
            # Уменьшение глубины
            elif line_stripped in ['КонецЕсли', 'КонецЦикла', 'КонецПопытки']:
                current_depth = max(0, current_depth - 1)
        
        return max_depth
    
    def _check_performance_issues(self, code: str) -> List[str]:
        """Проверка проблем производительности"""
        
        issues = []
        
        # Паттерны проблем производительности
        performance_patterns = [
            (r'Для\s+.*\s+Цикл\s*\n.*\n.*Запрос', 'Запрос внутри цикла'),
            (r'Получить\s*\([^)]*\)\s*\.\s*\w+\s*.*\n.*\n.*Для', 'Чтение в цикле'),
            (r'\w+\s*=\s*\w+\s*\.\s*Найти\([^)]*\)\s*\n.*\n.*\w+\s*=', 'Повторный поиск в цикле'),
        ]
        
        for pattern, issue_description in performance_patterns:
            if re.search(pattern, code, re.MULTILINE | re.IGNORECASE):
                issues.append(issue_description)
        
        return issues
    
    def _analyze_function_sizes(self, code: str) -> List[int]:
        """Анализ размеров функций"""
        
        function_sizes = []
        lines = code.split('\n')
        current_function_lines = 0
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('Процедура ') or line.startswith('Функция '):
                current_function_lines = 0
                # Считаем строки до конца процедуры/функции
                j = i + 1
                while j < len(lines):
                    inner_line = lines[j].strip()
                    if inner_line in ['КонецПроцедуры', 'КонецФункции']:
                        function_sizes.append(current_function_lines)
                        break
                    current_function_lines += 1
                    j += 1
                i = j
            
            i += 1
        
        return function_sizes
    
    def _find_large_procedures(self, code: str) -> List[str]:
        """Поиск слишком больших процедур"""
        
        large_procedures = []
        lines = code.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('Процедура ') or line.startswith('Функция '):
                proc_name = re.search(r'(?:Процедура Функция)\s+(\w+)', line)
                if proc_name:
                    name = proc_name.group(1)
                    
                    # Подсчет строк процедуры
                    current_lines = 0
                    j = i + 1
                    
                    while j < len(lines):
                        inner_line = lines[j].strip()
                        if inner_line in ['КонецПроцедуры', 'КонецФункции']:
                            break
                        current_lines += 1
                        j += 1
                    
                    if current_lines > 30:  # Порог для больших процедур
                        large_procedures.append(f"{name}: {current_lines} строк")
            
            i += 1
        
        return large_procedures
    
    def _analyze_global_usage(self, code: str) -> Dict[str, Any]:
        """Анализ использования глобальных объектов"""
        
        global_objects = [
            'Метаданные', 'ЭтотОбъект', 'Константы', 'Справочники', 
            'Документы', 'Регистры', 'Обработки', 'Отчеты'
        ]
        
        usage_count = 0
        found_objects = []
        
        for obj in global_objects:
            if re.search(r'\b' + obj + r'\b', code):
                usage_count += 1
                found_objects.append(obj)
        
        return {
            'count': usage_count,
            'objects': found_objects
        }
    
    def _calculate_security_risk_level(self, vulnerabilities: List[Dict[str, Any]]) -> str:
        """Вычисление уровня риска безопасности"""
        
        if not vulnerabilities:
            return 'low'
        
        severity_weights = {
            'critical': 4,
            'high': 3,
            'medium': 2,
            'low': 1
        }
        
        max_severity = max(severity_weights.get(vuln['severity'], 1) for vuln in vulnerabilities)
        critical_count = len([v for v in vulnerabilities if v['severity'] == 'critical'])
        
        if critical_count > 0:
            return 'critical'
        elif max_severity >= 3:
            return 'high'
        elif max_severity >= 2:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_security_score(self, vulnerabilities: List[Dict[str, Any]]) -> int:
        """Вычисление балла безопасности"""
        
        if not vulnerabilities:
            return 100
        
        penalty_per_vulnerability = {
            'critical': 30,
            'high': 20,
            'medium': 10,
            'low': 5
        }
        
        total_penalty = sum(
            penalty_per_vulnerability.get(vuln['severity'], 10) 
            for vuln in vulnerabilities
        )
        
        return max(0, 100 - total_penalty)
    
    def _calculate_performance_score(self, issues: List[str], metrics: Dict[str, Any]) -> int:
        """Вычисление балла производительности"""
        
        score = 100
        
        # Штрафы за проблемы
        score -= len(issues) * 5
        
        # Штрафы за метрики
        complexity = metrics.get('cyclomatic_complexity', 0)
        if complexity > 20:
            score -= 20
        elif complexity > 10:
            score -= 10
        
        nesting_depth = metrics.get('nesting_depth', 0)
        if nesting_depth > 5:
            score -= 15
        elif nesting_depth > 3:
            score -= 5
        
        return max(0, score)
    
    def _update_result_with_syntax(self, result: Dict[str, Any], syntax_errors: List[SyntaxValidationResult]):
        """Обновление результата с синтаксическими ошибками"""
        
        for error in syntax_errors:
            if error.severity == 'error':
                result['errors'].append(f"Строка {error.line_number}: {error.message}")
                result['valid'] = False
            elif error.severity == 'warning':
                result['warnings'].append(f"Строка {error.line_number}: {error.message}")
        
        if syntax_errors:
            result['metadata']['syntax_errors'] = len(syntax_errors)
    
    def _update_result_with_standards(self, result: Dict[str, Any], standards_results: List[StandardComplianceResult]):
        """Обновление результата со стандартами"""
        
        for standard_result in standards_results:
            for violation in standard_result.violations:
                result['warnings'].append(f"Стандарты - {violation}")
            
            for recommendation in standard_result.recommendations:
                result['recommendations'].append(f"Стандарты - {recommendation}")
        
        result['metadata']['standards_compliance'] = sum(r.compliance_level for r in standards_results) / len(standards_results)
    
    def _update_result_with_security(self, result: Dict[str, Any], security_result: SecurityAnalysisResult):
        """Обновление результата с безопасностью"""
        
        for vuln in security_result.vulnerabilities:
            if vuln['severity'] in ['critical', 'high']:
                result['errors'].append(f"Безопасность: {vuln['description']} (строка {vuln['line']})")
                result['valid'] = False
            else:
                result['warnings'].append(f"Безопасность: {vuln['description']} (строка {vuln['line']})")
        
        result['metadata']['security_risk'] = security_result.risk_level
        result['metadata']['security_score'] = security_result.security_score
    
    def _update_result_with_performance(self, result: Dict[str, Any], performance_result: Dict[str, Any]):
        """Обновление результата с производительностью"""
        
        for issue in performance_result['issues']:
            result['warnings'].append(f"Производительность: {issue}")
        
        result['metadata']['performance_metrics'] = performance_result['metrics']
        result['metadata']['performance_score'] = performance_result['performance_score']
    
    def _calculate_total_score(self, result: Dict[str, Any]) -> int:
        """Вычисление итогового балла"""
        
        base_score = 100
        errors_count = len(result['errors'])
        warnings_count = len(result['warnings'])
        recommendations_count = len(result['recommendations'])
        
        # Штрафы
        score = base_score
        score -= errors_count * 20  # Каждая ошибка - 20 баллов
        score -= warnings_count * 5  # Каждое предупреждение - 5 баллов
        score -= recommendations_count * 2  # Каждая рекомендация - 2 балла
        
        return max(0, score)
    
    def _update_validation_stats(self, result: Dict[str, Any]):
        """Обновление статистики валидации"""
        
        if result['errors']:
            self.validation_stats['validation_errors'] += len(result['errors'])
        
        if result['warnings']:
            self.validation_stats['validation_warnings'] += len(result['warnings'])
        
        # Обновление среднего балла
        total = self.validation_stats['total_validations']
        current_avg = self.validation_stats['average_score']
        new_score = result['score']
        
        self.validation_stats['average_score'] = (current_avg * (total - 1) + new_score) / total
    
    def _auto_fix_code(self, code: str, errors: List[str]) -> str:
        """Автоматическое исправление кода"""
        
        fixed_code = code
        
        # Простые автоматические исправления
        for error in errors:
            if "небаланс скобок" in error.lower():
                # Упрощенное исправление - добавление недостающих скобок
                # В реальной системе нужна более сложная логика
                pass
        
        return fixed_code
    
    def _brackets_match(self, opening: str, closing: str) -> bool:
        """Проверка соответствия скобок"""
        pairs = {'(': ')', '[': ']', '{': '}'}
        return pairs.get(opening) == closing
    
    def _is_valid_procedure_name(self, name: str) -> bool:
        """Проверка корректности имени процедуры"""
        # Имя должно начинаться с заглавной буквы и содержать только буквы и цифры
        return bool(re.match(r'^[А-ЯA-Z][а-яa-zA-Z0-9]*$', name))
    
    def _is_valid_function_name(self, name: str) -> bool:
        """Проверка корректности имени функции"""
        # Аналогично процедуре, но может возвращать значение
        return bool(re.match(r'^[А-ЯA-Z][а-яa-zA-Z0-9]*$', name))
    
    def _is_valid_variable_name(self, name: str) -> bool:
        """Проверка корректности имени переменной"""
        # Переменные могут начинаться с строчной буквы
        return bool(re.match(r'^[а-яa-z_][а-яa-zA-Z0-9_]*$', name))
    
    def _initialize_syntax_rules(self) -> Dict[str, Any]:
        """Инициализация правил синтаксиса"""
        return {
            'bracket_matching': True,
            'procedure_structure': True,
            'region_structure': True,
            'string_syntax': True
        }
    
    def _initialize_standard_rules(self) -> Dict[str, Any]:
        """Инициализация правил стандартов"""
        return {
            'naming_conventions': True,
            'code_structure': True,
            'documentation': True,
            'architecture': True
        }
    
    def _initialize_security_rules(self) -> Dict[str, Any]:
        """Инициализация правил безопасности"""
        return {
            'sql_injection': True,
            'xss_protection': True,
            'dangerous_functions': True,
            'information_leaks': True
        }
    
    def _initialize_performance_rules(self) -> Dict[str, Any]:
        """Инициализация правил производительности"""
        return {
            'complexity_check': True,
            'nesting_depth': True,
            'performance_patterns': True
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса валидатора"""
        return {
            'initialized': True,
            'enabled_checks': self.enabled_checks,
            'strict_mode': self.strict_mode,
            'auto_fix': self.auto_fix,
            'validation_stats': self.validation_stats.copy(),
            'version': '1.0'
        }