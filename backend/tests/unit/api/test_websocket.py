from unittest.mock import AsyncMock

import pytest
from src.api.websocket import ConnectionManager

ALL_CHANNELS = {"world_state", "agent_decisions", "events"}


def _make_ws():
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestConnectionManager:
    def test_connect_adds_client(self):
        manager = ConnectionManager()
        ws = _make_ws()

        manager.connect(ws)

        assert ws in manager._clients

    def test_connect_defaults_to_all_channels(self):
        manager = ConnectionManager()
        ws = _make_ws()

        manager.connect(ws)

        assert manager._clients[ws] == ALL_CHANNELS

    def test_disconnect_removes_client(self):
        manager = ConnectionManager()
        ws = _make_ws()
        manager.connect(ws)

        manager.disconnect(ws)

        assert ws not in manager._clients

    def test_disconnect_nonexistent_client_is_silent(self):
        manager = ConnectionManager()
        ws = _make_ws()

        manager.disconnect(ws)

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_subscribed_clients(self):
        manager = ConnectionManager()
        ws = _make_ws()
        manager.connect(ws)

        await manager.broadcast("world_state", '{"tick": 1}')

        ws.send_json.assert_awaited_once_with(
            {"channel": "world_state", "payload": {"tick": 1}}
        )

    @pytest.mark.asyncio
    async def test_broadcast_skips_unsubscribed_clients(self):
        manager = ConnectionManager()
        ws = _make_ws()
        manager.connect(ws)
        manager.set_channels(ws, ["world_state"])

        await manager.broadcast("agent_decisions", '{"action": "hold"}')

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_multiple_clients_different_subscriptions(self):
        manager = ConnectionManager()
        ws_all = _make_ws()
        ws_events_only = _make_ws()
        manager.connect(ws_all)
        manager.connect(ws_events_only)
        manager.set_channels(ws_events_only, ["events"])

        await manager.broadcast("events", '{"event_id": "e1"}')

        ws_all.send_json.assert_awaited_once_with(
            {"channel": "events", "payload": {"event_id": "e1"}}
        )
        ws_events_only.send_json.assert_awaited_once_with(
            {"channel": "events", "payload": {"event_id": "e1"}}
        )

    @pytest.mark.asyncio
    async def test_broadcast_world_state_not_sent_to_events_only_client(self):
        manager = ConnectionManager()
        ws = _make_ws()
        manager.connect(ws)
        manager.set_channels(ws, ["events"])

        await manager.broadcast("world_state", '{"tick": 5}')

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_unknown_channel_no_error(self):
        manager = ConnectionManager()
        ws = _make_ws()
        manager.connect(ws)

        await manager.broadcast("nonexistent_channel", '{"data": 1}')

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_disconnects_client_on_send_error(self):
        manager = ConnectionManager()
        ws = _make_ws()
        ws.send_json.side_effect = Exception("connection lost")
        manager.connect(ws)

        await manager.broadcast("world_state", '{"tick": 1}')

        assert ws not in manager._clients

    def test_set_channels_filters_invalid_channels(self):
        manager = ConnectionManager()
        ws = _make_ws()
        manager.connect(ws)

        manager.set_channels(ws, ["world_state", "bogus_channel"])

        assert manager._clients[ws] == {"world_state"}

    def test_set_channels_empty_list_results_in_no_channels(self):
        manager = ConnectionManager()
        ws = _make_ws()
        manager.connect(ws)

        manager.set_channels(ws, [])

        assert manager._clients[ws] == set()


class TestWebSocketEndpoint:
    @pytest.fixture
    def app_with_manager(self):
        from fastapi import FastAPI
        from src.api.websocket import websocket_endpoint

        test_app = FastAPI()
        manager = ConnectionManager()
        test_app.state.ws_manager = manager
        test_app.add_api_websocket_route("/ws", websocket_endpoint)
        return test_app

    @pytest.mark.asyncio
    async def test_websocket_connection_accepted(self, app_with_manager):
        from starlette.testclient import TestClient

        with TestClient(app_with_manager) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "ping"})
                data = ws.receive_json()
                assert data == {"type": "pong"}

    @pytest.mark.asyncio
    async def test_ping_pong(self, app_with_manager):
        from starlette.testclient import TestClient

        with TestClient(app_with_manager) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "ping"})
                response = ws.receive_json()
                assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_subscribe_updates_channels(self, app_with_manager):
        from starlette.testclient import TestClient

        manager = app_with_manager.state.ws_manager

        with TestClient(app_with_manager) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "subscribe", "channels": ["events"]})
                ws.send_json({"type": "ping"})
                ws.receive_json()

                assert len(manager._clients) == 1
                registered_ws = next(iter(manager._clients))
                assert manager._clients[registered_ws] == {"events"}

    @pytest.mark.asyncio
    async def test_invalid_json_does_not_crash(self, app_with_manager):
        from starlette.testclient import TestClient

        with TestClient(app_with_manager) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_text("not valid json {{{")
                ws.send_json({"type": "ping"})
                response = ws.receive_json()
                assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_unknown_message_type_ignored(self, app_with_manager):
        from starlette.testclient import TestClient

        with TestClient(app_with_manager) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"type": "unknown_action"})
                ws.send_json({"type": "ping"})
                response = ws.receive_json()
                assert response["type"] == "pong"
