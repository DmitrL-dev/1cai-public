
import json

import pytest

from src.monitoring.prometheus_metrics import (
    ba_ws_active_participants,
    ba_ws_active_sessions,
    ba_ws_disconnects_total,
    ba_ws_events_total,
    set_ba_session_counts,
)
from src.services.ba_session_manager import BASessionManager


class MockWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent = []
        self.closed = False
        self.fail_next_send = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        if self.fail_next_send:
            self.fail_next_send = False
            raise RuntimeError("send failed")
        self.sent.append(data)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_join_broadcast_leave(tmp_path):
    audit_file = tmp_path / "audit.log"
    manager = BASessionManager(audit_file)
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()
    set_ba_session_counts(0, 0)

    join_counter = ba_ws_events_total.labels(event_type="join")
    chat_counter = ba_ws_events_total.labels(event_type="chat")
    leave_counter = ba_ws_events_total.labels(event_type="leave")
    session_closed_counter = ba_ws_events_total.labels(event_type="session_closed")
    disconnect_counter = ba_ws_disconnects_total.labels(reason="send_error")

    join_before = join_counter._value.get()
    chat_before = chat_counter._value.get()
    leave_before = leave_counter._value.get()
    closed_before = session_closed_counter._value.get()
    disconnect_before = disconnect_counter._value.get()

    await manager.join_session("session", ws1, user_id="u1", role="lead")
    await manager.join_session("session", ws2, user_id="u2", role="analyst")

    await manager.broadcast("session", {"type": "chat", "text": "Hello"}, sender="u1")

    assert len(ws1.sent) == 1
    assert ws1.sent[0]["text"] == "Hello"
    assert ws1.sent[0]["sender"] == "u1"

    await manager.leave_session("session", "u2")
    state = manager.get_session_state("session")
    assert state
    assert len(state["participants"]) == 1
    assert ba_ws_active_sessions._value.get() == 1
    assert ba_ws_active_participants._value.get() == 1

    ws1.fail_next_send = True
    await manager.broadcast("session", {"type": "chat", "text": "Fail"}, sender="u3")

    # ensure audit written
    contents = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert any(json.loads(line)["event_type"] == "chat" for line in contents)
    assert ba_ws_active_sessions._value.get() == 0
    assert ba_ws_active_participants._value.get() == 0
    assert join_counter._value.get() == join_before + 2
    assert chat_counter._value.get() >= chat_before + 2
    assert leave_counter._value.get() >= leave_before + 2
    assert session_closed_counter._value.get() == closed_before + 1
    assert disconnect_counter._value.get() == disconnect_before + 1

    manager.clear()


@pytest.mark.asyncio
async def test_multiple_sessions(tmp_path):
    manager = BASessionManager(tmp_path / "audit.log")
    ws = MockWebSocket()
    set_ba_session_counts(0, 0)
    await manager.join_session("s1", ws, user_id="u1")
    await manager.join_session("s2", ws, user_id="u1")
    sessions = manager.list_sessions()
    assert len(sessions) == 2
    assert ba_ws_active_sessions._value.get() == 2
    assert ba_ws_active_participants._value.get() == 2
    manager.clear()
