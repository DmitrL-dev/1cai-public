
"""
Система алертинга для критичных ошибок и мониторинга.
Включает правила алертинга, интеграцию с уведомлениями и эскалацию.
"""

import asyncio
import json
import logging
import smtplib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MimeMultipart
from email.mime.text import MimeText
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import aiohttp


class AlertSeverity(Enum):
    """Уровни критичности алертов"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(Enum):
    """Статусы алертов"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class Alert:
    """Структура алерта"""
    id: str
    title: str
    description: str
    severity: AlertSeverity
    source: str
    timestamp: datetime
    labels: Dict[str, str]
    annotations: Dict[str, str]
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    escalation_level: int = 0
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.acknowledged_at:
            data['acknowledged_at'] = self.acknowledged_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data


@dataclass
class EscalationRule:
    """Правило эскалации"""
    alert_id: str
    escalation_delay_minutes: int
    escalation_channels: List[str]
    max_escalation_level: int = 3


class NotificationChannel:
    """Базовый класс канала уведомлений"""
    
    def __init__(self, name: str):
        self.name = name
        
    async def send(self, alert: Alert) -> bool:
        """Отправка уведомления"""
        raise NotImplementedError


class EmailChannel(NotificationChannel):
    """Канал уведомлений по email"""
    
    def __init__(self, name: str, smtp_server: str, smtp_port: int,
                 username: str, password: str, from_email: str,
                 to_emails: List[str]):
        super().__init__(name)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
        
    async def send(self, alert: Alert) -> bool:
        """Отправка email уведомления"""
        try:
            msg = MimeMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            
            # Формирование тела сообщения
            body = f"""
Система мониторинга MCP сервера

УРОВЕНЬ КРИТИЧНОСТИ: {alert.severity.value.upper()}
ЗАГОЛОВОК: {alert.title}
ОПИСАНИЕ: {alert.description}
ИСТОЧНИК: {alert.source}
ВРЕМЯ: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Метки:
{json.dumps(alert.labels, indent=2, ensure_ascii=False)}

Примечания:
{json.dumps(alert.annotations, indent=2, ensure_ascii=False)}

URL сервиса: http://localhost:8080
Дашборд: http://localhost:3000
            """
            
            msg.attach(MimeText(body, 'plain', 'utf-8'))
            
            # Отправка через SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                
            logging.info(f"Email уведомление отправлено для алерта {alert.id}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка отправки email для алерта {alert.id}: {e}")
            return False


class SlackChannel(NotificationChannel):
    """Канал уведомлений в Slack"""
    
    def __init__(self, name: str, webhook_url: str, channel: str):
        super().__init__(name)
        self.webhook_url = webhook_url
        self.channel = channel
        
    async def send(self, alert: Alert) -> bool:
        """Отправка Slack уведомления"""
        try:
            # Определение цвета в зависимости от критичности
            color_map = {
                AlertSeverity.CRITICAL: "danger",
                AlertSeverity.HIGH: "warning", 
                AlertSeverity.MEDIUM: "#ffcc00",
                AlertSeverity.LOW: "good"
            }
            
            payload = {
                "channel": self.channel,
                "username": "MCP Monitoring Bot",
                "icon_emoji": ":warning:",
                "attachments": [
                    {
                        "color": color_map[alert.severity],
                        "title": f"[{alert.severity.value.upper()}] {alert.title}",
                        "text": alert.description,
                        "fields": [
                            {
                                "title": "Источник",
                                "value": alert.source,
                                "short": True
                            },
                            {
                                "title": "Время",
                                "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                                "short": True
                            },
                            {
                                "title": "Корреляционный ID",
                                "value": alert.correlation_id or "N/A",
                                "short": False
                            }
                        ],
                        "footer": "MCP Monitoring System",
                        "ts": int(alert.timestamp.timestamp())
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 200:
                        logging.info(f"Slack уведомление отправлено для алерта {alert.id}")
                        return True
                    else:
                        logging.error(f"Ошибка отправки Slack уведомления: {response.status}")
                        return False
                        
        except Exception as e:
            logging.error(f"Ошибка отправки Slack уведомления для алерта {alert.id}: {e}")
            return False


class TelegramChannel(NotificationChannel):
    """Канал уведомлений в Telegram"""
    
    def __init__(self, name: str, bot_token: str, chat_id: str):
        super().__init__(name)
        self.bot_token = bot_token
        self.chat_id = chat_id
        
    async def send(self, alert: Alert) -> bool:
        """Отправка Telegram уведомления"""
        try:
            # Формирование сообщения
            severity_emoji = {
                AlertSeverity.CRITICAL: "🚨",
                AlertSeverity.HIGH: "⚠️",
                AlertSeverity.MEDIUM: "⚡",
                AlertSeverity.LOW: "ℹ️"
            }
            
            message = f"""
{severity_emoji[alert.severity]} *{alert.severity.value.upper()}*

*Заголовок:* {alert.title}
*Описание:* {alert.description}
*Источник:* {alert.source}
*Время:* {alert.timestamp.strftime('%d.%m.%Y %H:%M:%S')}

*Корреляционный ID:* {alert.correlation_id or 'N/A'}

#mcp-monitoring #alerts
            """
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        logging.info(f"Telegram уведомление отправлено для алерта {alert.id}")
                        return True
                    else:
                        logging.error(f"Ошибка отправки Telegram уведомления: {response.status}")
                        return False
                        
        except Exception as e:
            logging.error(f"Ошибка отправки Telegram уведомления для алерта {alert.id}: {e}")
            return False


class AlertManager:
    """Менеджер алертов"""
    
    def __init__(self, retention_days: int = 30):
        """
        Инициализация менеджера алертов
        
        Args:
            retention_days: Количество дней хранения разрешенных алертов
        """
        self.alerts: Dict[str, Alert] = {}
        self.escalation_rules: Dict[str, EscalationRule] = {}
        self.notification_channels: Dict[str, NotificationChannel] = {}
        self.alert_handlers: List[Callable[[Alert], bool]] = []
        self.retention_days = retention_days
        
        # Запуск задач очистки
        asyncio.create_task(self._cleanup_old_alerts())
        
    def add_notification_channel(self, channel: NotificationChannel):
        """Добавление канала уведомлений"""
        self.notification_channels[channel.name] = channel
        
    def add_escalation_rule(self, rule: EscalationRule):
        """Добавление правила эскалации"""
        self.escalation_rules[rule.alert_id] = rule
        
    def add_alert_handler(self, handler: Callable[[Alert], bool]):
        """Добавление обработчика алертов"""
        self.alert_handlers.append(handler)
        
    async def create_alert(self, title: str, description: str, severity: AlertSeverity,
                         source: str, labels: Optional[Dict[str, str]] = None,
                         annotations: Optional[Dict[str, str]] = None,
                         correlation_id: Optional[str] = None) -> str:
        """
        Создание нового алерта
        
        Args:
            title: Заголовок алерта
            description: Описание алерта
            severity: Уровень критичности
            source: Источник алерта
            labels: Метки
            annotations: Примечания
            correlation_id: Корреляционный ID
            
        Returns:
            ID созданного алерта
        """
        alert_id = f"{source}_{int(datetime.now().timestamp())}"
        
        alert = Alert(
            id=alert_id,
            title=title,
            description=description,
            severity=severity,
            source=source,
            timestamp=datetime.now(),
            labels=labels or {},
            annotations=annotations or {},
            correlation_id=correlation_id
        )
        
        self.alerts[alert_id] = alert
        
        # Отправка уведомлений
        await self._send_notifications(alert)
        
        # Вызов обработчиков
        await self._call_handlers(alert)
        
        logging.info(f"Создан алерт {alert_id}: {title}")
        return alert_id
        
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Подтверждение алерта"""
        if alert_id not in self.alerts:
            return False
            
        alert = self.alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now()
        alert.acknowledged_by = acknowledged_by
        
        logging.info(f"Алерт {alert_id} подтвержден пользователем {acknowledged_by}")
        return True
        
    async def resolve_alert(self, alert_id: str) -> bool:
        """Разрешение алерта"""
        if alert_id not in self.alerts:
            return False
            
        alert = self.alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        
        logging.info(f"Алерт {alert_id} разрешен")
        return True
        
    async def _send_notifications(self, alert: Alert):
        """Отправка уведомлений"""
        # Определяем каналы для отправки в зависимости от критичности
        channels_to_send = []
        
        if alert.severity == AlertSeverity.CRITICAL:
            channels_to_send = list(self.notification_channels.values())
        elif alert.severity == AlertSeverity.HIGH:
            channels_to_send = [
                ch for ch in self.notification_channels.values()
                if ch.name in ['slack', 'telegram']
            ]
        elif alert.severity == AlertSeverity.MEDIUM:
            channels_to_send = [
                ch for ch in self.notification_channels.values()
                if ch.name in ['telegram']
            ]
            
        # Отправка уведомлений параллельно
        tasks = []
        for channel in channels_to_send:
            tasks.append(channel.send(alert))
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def _call_handlers(self, alert: Alert):
        """Вызов обработчиков алертов"""
        for handler in self.alert_handlers:
            try:
                result = handler(alert)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logging.error(f"Ошибка в обработчике алерта {alert.id}: {e}")
                
    async def _cleanup_old_alerts(self):
        """Очистка старых разрешенных алертов"""
        while True:
            try:
                cutoff_date = datetime.now() - timedelta(days=self.retention_days)
                to_remove = []
                
                for alert_id, alert in self.alerts.items():
                    if (alert.status == AlertStatus.RESOLVED and 
                        alert.resolved_at and 
                        alert.resolved_at < cutoff_date):
                        to_remove.append(alert_id)
                        
                for alert_id in to_remove:
                    del self.alerts[alert_id]
                    
                if to_remove:
                    logging.info(f"Удалено {len(to_remove)} старых алертов")
                    
            except Exception as e:
                logging.error(f"Ошибка очистки старых алертов: {e}")
                
            # Очистка каждые 6 часов
            await asyncio.sleep(6 * 3600)
            
    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Получение активных алертов"""
        active_alerts = [
            alert for alert in self.alerts.values()
            if alert.status == AlertStatus.ACTIVE
        ]
        
        if severity:
            active_alerts = [
                alert for alert in active_alerts
                if alert.severity == severity
            ]
            
        return sorted(active_alerts, key=lambda x: x.timestamp, reverse=True)
        
    def get_alert_stats(self) -> Dict[str, Any]:
        """Получение статистики алертов"""
        total = len(self.alerts)
        active = len([a for a in self.alerts.values() if a.status == AlertStatus.ACTIVE])
        resolved = len([a for a in self.alerts.values() if a.status == AlertStatus.RESOLVED])
        
        severity_stats = {
            AlertSeverity.CRITICAL: len([a for a in self.alerts.values() 
                                        if a.severity == AlertSeverity.CRITICAL]),
            AlertSeverity.HIGH: len([a for a in self.alerts.values() 
                                   if a.severity == AlertSeverity.HIGH]),
            AlertSeverity.MEDIUM: len([a for a in self.alerts.values() 
                                     if a.severity == AlertSeverity.MEDIUM]),
            AlertSeverity.LOW: len([a for a in self.alerts.values() 
                                  if a.severity == AlertSeverity.LOW])
        }
        
        return {
            'total': total,
            'active': active,
            'resolved': resolved,
            'by_severity': {k.value: v for k, v in severity_stats.items()}
        }


# Глобальный менеджер алертов
_global_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Получение глобального менеджера алертов"""
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()
    return _global_alert_manager


def init_alert_manager(retention_days: int = 30) -> AlertManager:
    """Инициализация глобального менеджера алертов"""
    global _global_alert_manager
    _global_alert_manager = AlertManager(retention_days=retention_days)
    return _global_alert_manager


# Функции для создания алертов
async def create_error_alert(error_type: str, operation: str, 
                           correlation_id: Optional[str] = None):
    """Создание алерта об ошибке"""
    manager = get_alert_manager()
    
    # Определяем критичность по типу ошибки
    severity_map = {
        'validation': AlertSeverity.MEDIUM,
        'transport': AlertSeverity.HIGH,
        'integration': AlertSeverity.CRITICAL,
        'auth': AlertSeverity.CRITICAL,
        'circuit_breaker': AlertSeverity.HIGH
    }
    
    severity = severity_map.get(error_type, AlertSeverity.MEDIUM)
    
    title = f"Ошибка {error_type} в операции {operation}"
    description = f"Обнаружена ошибка типа '{error_type}' при выполнении операции '{operation}'"
    
    await manager.create_alert(
        title=title,
        description=description,
        severity=severity,
        source="mcp_server",
        labels={
            'error_type': error_type,
            'operation': operation,
            'component': 'mcp'
        },
        annotations={
            'error_class': error_type,
            'operation_name': operation,
            'requires_attention': 'true'
        },
        correlation_id=correlation_id
    )


async def create_performance_alert(metric_name: str, value: float, 
                                 threshold: float, operation: str):
    """Создание алерта о производительности"""
    manager = get_alert_manager()
    
    severity = AlertSeverity.HIGH if value > threshold * 1.5 else AlertSeverity.MEDIUM
    
    title = f"Превышен порог метрики {metric_name}"
    description = f"Значение метрики {metric_name} ({value:.2f}) превышает порог ({threshold:.2f}) в операции {operation}"
    
    await manager.create_alert(
        title=title,
        description=description,
        severity=severity,
        source="performance_monitor",
        labels={
            'metric_name': metric_name,
            'operation': operation,
            'component': 'performance'
        },
        annotations={
            'metric_value': str(value),
            'threshold_value': str(threshold),
            'performance_issue': 'true'
        }
    )


async def create_integration_alert(integration_type: str, operation: str,
                                 error_message: str, correlation_id: Optional[str] = None):
    """Создание алерта о проблемах интеграции"""
    manager = get_alert_manager()
    
    title = f"Ошибка интеграции {integration_type}"
    description = f"Ошибка при выполнении операции {operation} в интеграции {integration_type}: {error_message}"
    
    await manager.create_alert(
        title=title,
        description=description,
        severity=AlertSeverity.CRITICAL,
        source="integration_monitor",
        labels={
            'integration_type': integration_type,
            'operation': operation,
            'component': 'integration'
        },
        annotations={
            'integration_name': integration_type,
            'operation_name': operation,
            'error_message': error_message[:200],
            'integration_issue': 'true'
        },
        correlation_id=correlation_id
    )