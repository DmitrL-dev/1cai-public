# WebSocket API Reference

**Version:** 1.0  
**Base URL:** `ws://localhost:8000/api/v1/websocket`

## Connection

### Connect
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/websocket/connect');
```

## Channels

### Subscribe to Notifications
```javascript
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'notifications'
}));
```

### Subscribe to Live Updates
```javascript
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'dashboard_updates'
}));
```

### Join Chat Room
```javascript
ws.send(JSON.stringify({
  type: 'join_room',
  room: 'project_123'
}));
```

## Server-Side

### Notify User
```python
await notify_user(
    user_id="usr_123",
    title="Build completed",
    message="..."
)
```

### Broadcast to Room
```python
await broadcast_to_room(
    room="project_123",
    message={...}
)
```

**See:** [WebSocket Guide](../06-features/WEBSOCKET_GUIDE.md)
