# WebSocket — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/websocket`

## Обзор
**WebSocket Module** — real-time коммуникация. Уведомления, live updates, chat.

**Возможности:** 🔔 Real-time Notifications | 📊 Live Updates | 💬 Chat | 🔄 Auto-reconnect | 📡 Broadcasting | 🎯 Room-based Messaging

## Quick Start

```javascript
// JavaScript client
const ws = new WebSocket('ws://localhost:8000/api/v1/websocket/connect');

ws.onopen = () => {
    console.log('Connected');
    ws.send(JSON.stringify({type: 'subscribe', channel: 'notifications'}));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
};
```

```python
# Python client
import websockets

async with websockets.connect('ws://localhost:8000/api/v1/websocket/connect') as ws:
    await ws.send(json.dumps({'type': 'subscribe', 'channel': 'notifications'}))
    
    async for message in ws:
        data = json.loads(message)
        print(f"Received: {data}")
```

## Channels

### Notifications
```javascript
ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'notifications'
}));

// Получение уведомлений
{
    "type": "notification",
    "title": "New code review",
    "message": "Your PR #123 has been reviewed",
    "priority": "high"
}
```

### Live Updates
```javascript
ws.send(JSON.stringify({
    type: 'subscribe',
    channel: 'dashboard_updates'
}));

// Получение обновлений дашборда
{
    "type": "update",
    "metric": "active_users",
    "value": 523
}
```

### Chat
```javascript
ws.send(JSON.stringify({
    type: 'join_room',
    room: 'project_123'
}));

ws.send(JSON.stringify({
    type: 'message',
    room: 'project_123',
    text: 'Hello team!'
}));
```

## Server-Side

```python
from src.modules.websocket.api.routes import notify_user

# Отправка уведомления пользователю
await notify_user(
    user_id="usr_123",
    title="Build completed",
    message="Your build #456 completed successfully",
    priority="medium"
)

# Broadcasting всем в комнате
await broadcast_to_room(
    room="project_123",
    message={"type": "update", "data": {...}}
)
```

## Best Practices

1. **Reconnection:** Реализуйте exponential backoff
2. **Heartbeat:** Отправляйте ping каждые 30 секунд
3. **Message Queue:** Используйте очередь для offline messages
4. **Authentication:** Передавайте token в query string

## Troubleshooting

**Проблема: Connection drops**
```javascript
let reconnectDelay = 1000;
ws.onclose = () => {
    setTimeout(() => {
        reconnect();
        reconnectDelay *= 2; // Exponential backoff
    }, reconnectDelay);
};
```

## FAQ
**Q: Максимум подключений?** A: 10,000 одновременных (настраивается)  
**Q: Поддерживается ли Socket.IO?** A: Нет, только нативный WebSocket

---

**Документация:** [WebSocket API](../api/WEBSOCKET_API.md)
