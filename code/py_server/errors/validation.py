
"""
Исключения валидации данных для 1С MCP сервера

Ошибки валидации данных (E020-E039):
- Некорректные входные данные
- Отсутствующие обязательные поля
- Недопустимые значения
- Нарушения формата данных
- Дублирование данных
- Ошибки сериализации/десериализации

Все ошибки валидации являются невосстановимыми - 
данные должны быть исправлены пользователем.
"""

from typing import Any, Dict, List, Optional

try:
    from .base import ErrorSeverity, NonRecoverableError
except ImportError:
    from base import ErrorSeverity, NonRecoverableError


class ValidationError(NonRecoverableError):
    """
    Базовый класс ошибок валидации данных (E020-E039)
    
    Все ошибки валидации являются невосстановимыми,
    так как требуют исправления входных данных.
    """
    
    def __init__(
        self,
        error_code: str,
        field_name: str = "",
        field_value: Any = None,
        validation_rule: str = "",
        **kwargs
    ):
        # По умолчанию ошибка валидации невосстановима
        kwargs.setdefault('recoverable', False)
        kwargs.setdefault('severity', ErrorSeverity.MEDIUM)
        kwargs.setdefault('context_data', {})
        
        # Добавляем информацию о поле
        if field_name:
            kwargs.setdefault('context_data', {})['field_name'] = field_name
            kwargs.setdefault('context_data', {})['field_value'] = field_value
            kwargs.setdefault('context_data', {})['validation_rule'] = validation_rule
        
        super().__init__(error_code, "ValidationError", **kwargs)


class InvalidInputDataError(ValidationError):
    """
    Некорректные входные данные (E020)
    
    Используется когда входные данные не соответствуют
    ожидаемому формату или содержат недопустимые значения.
    """
    
    def __init__(
        self,
        field_name: str,
        field_value: Any,
        expected_format: str = "",
        **kwargs
    ):
        user_message = f"Некорректные данные в поле '{field_name}': получено '{field_value}'"
        if expected_format:
            user_message += f", ожидается формат: {expected_format}"
        
        kwargs.setdefault('error_code', 'E020')
        kwargs.setdefault('context_data', {}).update({
            'expected_format': expected_format,
            'validation_type': 'invalid_input'
        })
        
        # Извлекаем error_code из kwargs, чтобы избежать конфликта
        error_code = kwargs.pop('error_code', 'E020')
        
        super().__init__(
            error_code,
            field_name,
            field_value,
            'invalid_format',
            user_message=user_message,
            **kwargs
        )


class MissingRequiredFieldError(ValidationError):
    """
    Отсутствует обязательное поле (E021)
    
    Используется когда обязательное поле отсутствует
    в входных данных.
    """
    
    def __init__(self, field_name: str, **kwargs):
        user_message = f"Отсутствует обязательное поле: '{field_name}'"
        
        kwargs.setdefault('error_code', 'E021')
        kwargs.setdefault('context_data', {}).update({
            'validation_type': 'missing_field'
        })
        
        # Извлекаем error_code из kwargs, чтобы избежать дублирования
        error_code = kwargs.pop('error_code', 'E021')
        
        super().__init__(
            error_code,
            field_name,
            None,
            'required',
            user_message=user_message,
            **kwargs
        )


class InvalidFieldValueError(ValidationError):
    """
    Недопустимое значение поля (E022)
    
    Используется когда значение поля не соответствует
    допустимым значениям или ограничениям.
    """
    
    def __init__(
        self,
        field_name: str,
        field_value: Any,
        allowed_values: Optional[List[Any]] = None,
        constraint_description: str = "",
        **kwargs
    ):
        user_message = f"Недопустимое значение поля '{field_name}': '{field_value}'"
        
        if allowed_values:
            user_message += f". Допустимые значения: {allowed_values}"
        elif constraint_description:
            user_message += f". Ограничение: {constraint_description}"
        
        kwargs.setdefault('error_code', 'E022')
        kwargs['context_data'].update({
            'allowed_values': allowed_values,
            'constraint_description': constraint_description,
            'validation_type': 'invalid_value'
        })
        
        super().__init__(
            kwargs['error_code'],
            field_name,
            field_value,
            'invalid_value',
            user_message=user_message,
            **kwargs
        )


class DataSizeExceededError(ValidationError):
    """
    Превышен размер данных (E023)
    
    Используется когда размер данных превышает
    установленные ограничения.
    """
    
    def __init__(
        self,
        data_type: str,
        actual_size: int,
        max_size: int,
        size_unit: str = "bytes",
        **kwargs
    ):
        user_message = (
            f"Превышен максимальный размер {data_type}: "
            f"{actual_size}{size_unit} (максимум: {max_size}{size_unit})"
        )
        
        kwargs.setdefault('error_code', 'E023')
        kwargs['context_data'].update({
            'data_type': data_type,
            'actual_size': actual_size,
            'max_size': max_size,
            'size_unit': size_unit,
            'validation_type': 'size_exceeded'
        })
        
        super().__init__(
            kwargs['error_code'],
            "",
            None,
            'size_limit',
            user_message=user_message,
            **kwargs
        )


class InvalidDataFormatError(ValidationError):
    """
    Неверный формат данных (E024)
    
    Используется когда данные не соответствуют
    ожидаемому формату (JSON, XML, дата, число и т.д.).
    """
    
    def __init__(
        self,
        field_name: str,
        data: str,
        expected_format: str,
        parsing_error: Optional[str] = None,
        **kwargs
    ):
        user_message = f"Неверный формат данных в поле '{field_name}': ожидается {expected_format}"
        if parsing_error:
            user_message += f". Ошибка парсинга: {parsing_error}"
        
        kwargs.setdefault('error_code', 'E024')
        kwargs['context_data'].update({
            'expected_format': expected_format,
            'parsing_error': parsing_error,
            'raw_data': data[:100] + "..." if len(data) > 100 else data,
            'validation_type': 'invalid_format'
        })
        
        super().__init__(
            kwargs['error_code'],
            field_name,
            data,
            'format_validation',
            user_message=user_message,
            **kwargs
        )


class DataDuplicationError(ValidationError):
    """
    Дублирование данных (E025)
    
    Используется когда обнаружены дублирующиеся записи
    или данные, которые должны быть уникальными.
    """
    
    def __init__(
        self,
        field_name: str,
        duplicated_value: Any,
        existing_records_count: int = 0,
        **kwargs
    ):
        user_message = f"Обнаружено дублирование данных: значение '{duplicated_value}' в поле '{field_name}'"
        if existing_records_count > 0:
            user_message += f" (найдено {existing_records_count} существующих записей)"
        
        kwargs.setdefault('error_code', 'E025')
        kwargs['context_data'].update({
            'duplicated_value': duplicated_value,
            'existing_records_count': existing_records_count,
            'validation_type': 'duplication'
        })
        
        super().__init__(
            kwargs['error_code'],
            field_name,
            duplicated_value,
            'uniqueness',
            user_message=user_message,
            **kwargs
        )


class UniquenessViolationError(ValidationError):
    """
    Нарушение уникальности (E026)
    
    Используется когда операция нарушает ограничение уникальности
    в базе данных или бизнес-логике.
    """
    
    def __init__(
        self,
        constraint_name: str,
        violating_value: Any,
        table_name: Optional[str] = None,
        **kwargs
    ):
        user_message = f"Нарушение ограничения уникальности '{constraint_name}': значение '{violating_value}'"
        if table_name:
            user_message += f" в таблице '{table_name}'"
        
        kwargs.setdefault('error_code', 'E026')
        kwargs['context_data'].update({
            'constraint_name': constraint_name,
            'table_name': table_name,
            'violating_value': violating_value,
            'validation_type': 'uniqueness_violation'
        })
        
        super().__init__(
            kwargs['error_code'],
            "",
            violating_value,
            'uniqueness_constraint',
            user_message=user_message,
            **kwargs
        )


class SerializationError(ValidationError):
    """
    Ошибка сериализации (E027)
    
    Используется когда не удается сериализовать данные
    в требуемый формат (JSON, XML и т.д.).
    """
    
    def __init__(
        self,
        data: Any,
        target_format: str,
        serialization_error: str,
        **kwargs
    ):
        user_message = f"Ошибка сериализации в формат {target_format}: {serialization_error}"
        
        kwargs.setdefault('error_code', 'E027')
        kwargs['context_data'].update({
            'target_format': target_format,
            'serialization_error': serialization_error,
            'data_type': type(data).__name__,
            'validation_type': 'serialization_error'
        })
        
        super().__init__(
            kwargs['error_code'],
            "",
            None,
            'serialization',
            user_message=user_message,
            **kwargs
        )


class DeserializationError(ValidationError):
    """
    Ошибка десериализации (E028)
    
    Используется когда не удается десериализовать данные
    из требуемого формата.
    """
    
    def __init__(
        self,
        data: str,
        target_format: str,
        deserialization_error: str,
        **kwargs
    ):
        user_message = f"Ошибка десериализации из формата {target_format}: {deserialization_error}"
        
        kwargs.setdefault('error_code', 'E028')
        kwargs['context_data'].update({
            'source_format': target_format,
            'deserialization_error': deserialization_error,
            'raw_data': data[:100] + "..." if len(data) > 100 else data,
            'validation_type': 'deserialization_error'
        })
        
        super().__init__(
            kwargs['error_code'],
            "",
            None,
            'deserialization',
            user_message=user_message,
            **kwargs
        )


class DatabaseConstraintViolationError(ValidationError):
    """
    Нарушение ограничений БД (E029)
    
    Используется когда операция нарушает ограничения
    базы данных (foreign key, check constraint и т.д.).
    """
    
    def __init__(
        self,
        constraint_name: str,
        constraint_type: str,
        table_name: str,
        violating_value: Any,
        **kwargs
    ):
        user_message = (
            f"Нарушение ограничения '{constraint_type}' '{constraint_name}' "
            f"в таблице '{table_name}' для значения '{violating_value}'"
        )
        
        kwargs.setdefault('error_code', 'E029')
        kwargs['context_data'].update({
            'constraint_name': constraint_name,
            'constraint_type': constraint_type,
            'table_name': table_name,
            'violating_value': violating_value,
            'validation_type': 'database_constraint'
        })
        
        super().__init__(
            kwargs['error_code'],
            "",
            violating_value,
            'database_constraint',
            user_message=user_message,
            **kwargs
        )


class SchemaValidationError(ValidationError):
    """
    Ошибка валидации схемы данных
    
    Используется когда данные не соответствуют
    определенной схеме (JSON Schema, Pydantic модель и т.д.).
    """
    
    def __init__(
        self,
        schema_name: str,
        validation_errors: List[Dict[str, Any]],
        **kwargs
    ):
        error_messages = [err.get('message', str(err)) for err in validation_errors]
        user_message = f"Ошибки валидации схемы '{schema_name}': " + "; ".join(error_messages)
        
        kwargs.setdefault('context_data', {})
        kwargs['context_data'].update({
            'schema_name': schema_name,
            'validation_errors': validation_errors,
            'validation_type': 'schema_validation'
        })
        
        super().__init__(
            'E024',
            "",
            None,
            'schema_validation',
            user_message=user_message,
            **kwargs
        )


class BusinessRuleValidationError(ValidationError):
    """
    Ошибка валидации бизнес-правил
    
    Используется когда данные проходят техническую валидацию,
    но нарушают бизнес-логику системы.
    """
    
    def __init__(
        self,
        rule_name: str,
        rule_description: str,
        violating_data: Dict[str, Any],
        **kwargs
    ):
        user_message = f"Нарушение бизнес-правила '{rule_name}': {rule_description}"
        
        kwargs.setdefault('context_data', {})
        kwargs['context_data'].update({
            'rule_name': rule_name,
            'rule_description': rule_description,
            'violating_data': violating_data,
            'validation_type': 'business_rule'
        })
        
        super().__init__(
            'E020',
            "",
            None,
            'business_rule',
            user_message=user_message,
            **kwargs
        )


# Фабрика для создания стандартных ошибок валидации
class ValidationErrorFactory:
    """Фабрика для создания ошибок валидации"""
    
    @staticmethod
    def invalid_format(field_name: str, expected_format: str) -> ValidationError:
        """Создает ошибку неверного формата"""
        return InvalidInputDataError(
            field_name=field_name,
            field_value="",
            expected_format=expected_format
        )
    
    @staticmethod
    def required_field(field_name: str) -> ValidationError:
        """Создает ошибку отсутствующего обязательного поля"""
        return MissingRequiredFieldError(field_name)
    
    @staticmethod
    def duplicate_value(field_name: str, value: Any) -> ValidationError:
        """Создает ошибку дублирования"""
        return DataDuplicationError(field_name, value)
    
    @staticmethod
    def size_limit(data_type: str, actual: int, max_size: int) -> ValidationError:
        """Создает ошибку превышения размера"""
        return DataSizeExceededError(data_type, actual, max_size)