
#!/usr/bin/env python3
"""
Audit Logger для 1C AI MCP Code Generation

Система логирования действий генерации кода для аудита и аналитики.

Версия: 1.0
Дата: 30.10.2025
"""

import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class AuditEvent:
    """Событие для аудита"""
    event_id: str
    event_type: str  # generation_start, generation_success, generation_error, validation, etc.
    timestamp: datetime
    user_id: Optional[str]
    session_id: str
    request_data: Dict[str, Any]
    response_data: Optional[Dict[str, Any]]
    execution_time: Optional[float]
    metadata: Dict[str, Any]

class AuditLogger:
    """Логгер аудита для системы генерации кода"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация логгера аудита
        
        Args:
            config: Конфигурация логгера
        """
        self.config = config
        
        # Настройки
        self.enabled = config.get('enabled', True)
        self.log_level = config.get('log_level', 'INFO')
        self.log_file = config.get('log_file', './logs/audit.log')
        self.retention_days = config.get('retention_days', 30)
        self.max_file_size = config.get('max_file_size', 10 * 1024 * 1024)  # 10MB
        
        # Создание директории для логов
        if self.enabled and self.log_file:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
        # Настройка логгера
        self._setup_logger()
        
        # Статистика
        self.stats = {
            'events_logged': 0,
            'errors_logged': 0,
            'total_execution_time': 0.0
        }
        
        self.logger.info("AuditLogger инициализирован")
    
    async def log_generation_start(self, request):
        """Логирование начала генерации кода"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='generation_start',
            timestamp=datetime.now(timezone.utc),
            user_id=getattr(request, 'user_id', None),
            session_id=getattr(request, 'request_id', str(uuid.uuid4())),
            request_data=self._serialize_request(request),
            response_data=None,
            execution_time=None,
            metadata={
                'object_type': getattr(request, 'object_type', 'unknown'),
                'code_style': getattr(request, 'code_style', 'unknown'),
                'include_comments': getattr(request, 'include_comments', False),
                'use_standards': getattr(request, 'use_standards', False)
            }
        )
        
        await self._log_event(event)
    
    async def log_generation_success(self, request, result):
        """Логирование успешной генерации кода"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='generation_success',
            timestamp=datetime.now(timezone.utc),
            user_id=getattr(request, 'user_id', None),
            session_id=getattr(request, 'request_id', str(uuid.uuid4())),
            request_data=self._serialize_request(request),
            response_data=self._serialize_result(result),
            execution_time=getattr(result, 'execution_time', None),
            metadata={
                'generated_code_sections': len(getattr(result, 'generated_code', {})),
                'validation_score': getattr(result, 'validation_score', None),
                'security_status': getattr(result, 'security_status', None),
                'recommendations_count': len(getattr(result, 'recommendations', [])),
                'warnings_count': len(getattr(result, 'warnings', []))
            }
        )
        
        await self._log_event(event)
    
    async def log_generation_error(self, request, error_message: str):
        """Логирование ошибки генерации кода"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='generation_error',
            timestamp=datetime.now(timezone.utc),
            user_id=getattr(request, 'user_id', None),
            session_id=getattr(request, 'request_id', str(uuid.uuid4())),
            request_data=self._serialize_request(request),
            response_data={'error': error_message},
            execution_time=None,
            metadata={
                'error_type': 'generation_failure',
                'error_category': self._categorize_error(error_message)
            }
        )
        
        await self._log_event(event)
        self.stats['errors_logged'] += 1
    
    async def log_validation_start(self, code: str, validation_params: Dict[str, Any]):
        """Логирование начала валидации"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='validation_start',
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            session_id=str(uuid.uuid4()),
            request_data={
                'code_length': len(code),
                'code_lines': len(code.split('\n')),
                'validation_params': validation_params
            },
            response_data=None,
            execution_time=None,
            metadata={
                'validation_level': validation_params.get('level', 'unknown')
            }
        )
        
        await self._log_event(event)
    
    async def log_validation_result(self, validation_result: Dict[str, Any], execution_time: float):
        """Логирование результата валидации"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='validation_result',
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            session_id=str(uuid.uuid4()),
            request_data={},
            response_data=validation_result,
            execution_time=execution_time,
            metadata={
                'validation_score': validation_result.get('score', 0),
                'errors_count': len(validation_result.get('errors', [])),
                'warnings_count': len(validation_result.get('warnings', [])),
                'valid': validation_result.get('valid', False)
            }
        )
        
        await self._log_event(event)
    
    async def log_security_scan(self, security_result: Dict[str, Any], execution_time: float):
        """Логирование результата сканирования безопасности"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='security_scan',
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            session_id=str(uuid.uuid4()),
            request_data={},
            response_data=security_result,
            execution_time=execution_time,
            metadata={
                'risk_level': security_result.get('risk_level', 'unknown'),
                'threats_count': len(security_result.get('threats', [])),
                'security_score': security_result.get('security_score', 0),
                'blocked': security_result.get('blocked', False)
            }
        )
        
        await self._log_event(event)
    
    async def log_template_usage(self, template_id: str, template_name: str, 
                                object_type: str, success: bool):
        """Логирование использования шаблона"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='template_usage',
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            session_id=str(uuid.uuid4()),
            request_data={
                'template_id': template_id,
                'template_name': template_name,
                'object_type': object_type
            },
            response_data={'success': success},
            execution_time=None,
            metadata={
                'template_type': 'standard'  # Может быть расширено
            }
        )
        
        await self._log_event(event)
    
    async def log_user_feedback(self, request_id: str, rating: int, 
                               feedback_text: Optional[str] = None):
        """Логирование обратной связи пользователя"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type='user_feedback',
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            session_id=request_id,
            request_data={
                'rating': rating,
                'feedback_text': feedback_text
            },
            response_data={},
            execution_time=None,
            metadata={
                'feedback_source': 'user_interface'
            }
        )
        
        await self._log_event(event)
    
    async def log_system_event(self, event_type: str, event_data: Dict[str, Any]):
        """Логирование системных событий"""
        
        if not self.enabled:
            return
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=f'system_{event_type}',
            timestamp=datetime.now(timezone.utc),
            user_id=None,
            session_id=str(uuid.uuid4()),
            request_data=event_data,
            response_data={},
            execution_time=None,
            metadata={
                'event_category': 'system'
            }
        )
        
        await self._log_event(event)
    
    async def _log_event(self, event: AuditEvent):
        """Запись события в лог"""
        
        try:
            # Преобразование события в JSON
            event_json = json.dumps(asdict(event), default=self._json_serializer, ensure_ascii=False)
            
            # Запись в файл
            if self.log_file:
                await self._write_to_file(event_json)
            
            # Запись в стандартный логгер
            self.logger.info(f"AUDIT: {event_json}")
            
            # Обновление статистики
            self.stats['events_logged'] += 1
            if event.execution_time:
                self.stats['total_execution_time'] += event.execution_time
            
        except Exception as e:
            # Логирование ошибки логгера (осторожно с рекурсией)
            print(f"Ошибка записи в аудит лог: {e}")
    
    async def _write_to_file(self, event_json: str):
        """Запись события в файл с ротацией"""
        
        try:
            # Проверка размера файла
            if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > self.max_file_size:
                await self._rotate_log_file()
            
            # Запись в файл
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(event_json + '\n')
                
        except Exception as e:
            self.logger.error(f"Ошибка записи в файл аудита: {e}")
    
    async def _rotate_log_file(self):
        """Ротация лог файла"""
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f"{self.log_file}.{timestamp}.bak"
            
            if os.path.exists(self.log_file):
                os.rename(self.log_file, backup_file)
                self.logger.info(f"Лог файл ротирован: {backup_file}")
                
        except Exception as e:
            self.logger.error(f"Ошибка ротации лог файла: {e}")
    
    def _setup_logger(self):
        """Настройка логгера"""
        
        if not self.enabled:
            return
        
        # Создание логгера
        self.logger = logging.getLogger('audit_logger')
        self.logger.setLevel(getattr(logging, self.log_level.upper()))
        
        # Очистка существующих обработчиков
        self.logger.handlers.clear()
        
        # Форматирование сообщений
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Обработчик для файла
        if self.log_file:
            try:
                file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                print(f"Ошибка создания файлового обработчика: {e}")
        
        # Обработчик для консоли
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def _serialize_request(self, request) -> Dict[str, Any]:
        """Сериализация запроса"""
        
        if hasattr(request, '__dict__'):
            data = request.__dict__.copy()
            # Исключаем чувствительные данные
            sensitive_fields = ['password', 'api_key', 'token', 'secret']
            for field in sensitive_fields:
                if field in data:
                    data[field] = '***MASKED***'
            return data
        else:
            return {'type': type(request).__name__}
    
    def _serialize_result(self, result) -> Dict[str, Any]:
        """Сериализация результата"""
        
        if hasattr(result, '__dict__'):
            data = result.__dict__.copy()
            # Исключаем большой код из лога для экономии места
            if 'generated_code' in data:
                code_sizes = {k: len(str(v)) for k, v in data['generated_code'].items()}
                data['generated_code_sizes'] = code_sizes
                data['generated_code'] = f"<{len(data['generated_code'])} sections>"
            return data
        else:
            return {'type': type(result).__name__}
    
    def _categorize_error(self, error_message: str) -> str:
        """Категоризация ошибки"""
        
        error_lower = error_message.lower()
        
        if 'syntax' in error_lower:
            return 'syntax_error'
        elif 'validation' in error_lower:
            return 'validation_error'
        elif 'security' in error_lower:
            return 'security_error'
        elif 'network' in error_lower or 'connection' in error_lower:
            return 'network_error'
        elif 'timeout' in error_lower:
            return 'timeout_error'
        else:
            return 'unknown_error'
    
    def _json_serializer(self, obj):
        """JSON сериализатор для специальных типов"""
        
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (set, frozenset)):
            return list(obj)
        else:
            return str(obj)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики аудита"""
        
        stats = self.stats.copy()
        
        # Дополнительные метрики
        if stats['events_logged'] > 0:
            stats['average_execution_time'] = stats['total_execution_time'] / stats['events_logged']
            stats['error_rate'] = stats['errors_logged'] / stats['events_logged']
        else:
            stats['average_execution_time'] = 0.0
            stats['error_rate'] = 0.0
        
        return stats
    
    def export_audit_data(self, start_date: datetime, end_date: datetime, 
                         output_file: str) -> bool:
        """
        Экспорт данных аудита за период
        
        Args:
            start_date: Начальная дата
            end_date: Конечная дата
            output_file: Файл для экспорта
            
        Returns:
            True если экспорт успешен
        """
        
        try:
            exported_events = 0
            
            if not os.path.exists(self.log_file):
                return False
            
            with open(self.log_file, 'r', encoding='utf-8') as infile, \
                 open(output_file, 'w', encoding='utf-8') as outfile:
                
                for line in infile:
                    try:
                        event_data = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event_data['timestamp'])
                        
                        if start_date <= event_time <= end_date:
                            outfile.write(line)
                            exported_events += 1
                            
                    except (json.JSONDecodeError, KeyError, ValueError):
                        # Пропускаем некорректные строки
                        continue
            
            self.logger.info(f"Экспортировано {exported_events} событий в {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка экспорта аудита: {e}")
            return False
    
    def cleanup_old_logs(self, days_to_keep: int = None):
        """
        Очистка старых логов
        
        Args:
            days_to_keep: Количество дней для хранения
        """
        
        if days_to_keep is None:
            days_to_keep = self.retention_days
        
        try:
            cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
            
            if os.path.exists(self.log_file):
                file_mtime = os.path.getmtime(self.log_file)
                
                if file_mtime < cutoff_date:
                    backup_file = f"{self.log_file}.old.{int(time.time())}"
                    os.rename(self.log_file, backup_file)
                    self.logger.info(f"Старый лог перемещен в: {backup_file}")
            
        except Exception as e:
            self.logger.error(f"Ошибка очистки старых логов: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса логгера"""
        
        return {
            'enabled': self.enabled,
            'log_file': self.log_file,
            'log_level': self.log_level,
            'retention_days': self.retention_days,
            'statistics': self.get_statistics(),
            'version': '1.0'
        }