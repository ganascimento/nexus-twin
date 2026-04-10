import asyncio
import json

from fastapi import WebSocket
from loguru import logger


REDIS_TO_WS = {
    "nexus:world_state": "world_state",
    "nexus:agent_decisions": "agent_decisions",
    "nexus:events": "events",
}


class ConnectionManager:
    ALL_CHANNELS: set[str] = {"world_state", "agent_decisions", "events"}

    def __init__(self):
        self._clients: dict[WebSocket, set[str]] = {}

    def connect(self, ws: WebSocket) -> None:
        self._clients[ws] = set(self.ALL_CHANNELS)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.pop(ws, None)

    def set_channels(self, ws: WebSocket, channels: list[str]) -> None:
        self._clients[ws] = set(channels) & self.ALL_CHANNELS

    async def broadcast(self, channel: str, payload: str) -> None:
        parsed = json.loads(payload)
        message = {"channel": channel, "payload": parsed}
        disconnected = []
        for ws, subscribed in self._clients.items():
            if channel in subscribed:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


async def redis_subscriber(redis_client, manager: ConnectionManager) -> None:
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(*REDIS_TO_WS.keys())
    logger.info("Redis subscriber started for channels: {}", list(REDIS_TO_WS.keys()))
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                redis_channel = msg["channel"]
                if isinstance(redis_channel, bytes):
                    redis_channel = redis_channel.decode()
                ws_channel = REDIS_TO_WS.get(redis_channel)
                if ws_channel:
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    await manager.broadcast(ws_channel, data)
            else:
                await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        await pubsub.unsubscribe()
        await pubsub.close()
        raise
    except Exception as exc:
        logger.error("Redis subscriber error: {}", exc)


async def websocket_endpoint(ws: WebSocket) -> None:
    manager: ConnectionManager = ws.app.state.ws_manager
    await ws.accept()
    manager.connect(ws)
    logger.info("WebSocket client connected")
    try:
        while True:
            text = await ws.receive_text()
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                continue
            msg_type = data.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "subscribe" and isinstance(data.get("channels"), list):
                manager.set_channels(ws, data["channels"])
    except Exception:
        pass
    finally:
        manager.disconnect(ws)
        logger.info("WebSocket client disconnected")
