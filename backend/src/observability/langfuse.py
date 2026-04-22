import os
from typing import Optional

from loguru import logger

try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    _LANGFUSE_V4 = True
except ImportError:
    Langfuse = None
    _LANGFUSE_V4 = False
    try:
        from langfuse.callback import CallbackHandler
    except ImportError:
        CallbackHandler = None


_initialized: bool = False
_cached_handler: Optional["CallbackHandler"] = None


def get_callback_handler():
    global _initialized, _cached_handler

    if _initialized:
        return _cached_handler

    _initialized = True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    if not public_key or not secret_key:
        _cached_handler = None
        return None

    if CallbackHandler is None:
        logger.warning(
            "langfuse package not importable; observability disabled"
        )
        _cached_handler = None
        return None

    host = os.environ.get("LANGFUSE_HOST", "").strip() or "http://localhost:3100"

    try:
        if _LANGFUSE_V4:
            Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            _cached_handler = CallbackHandler()
        else:
            _cached_handler = CallbackHandler(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
    except Exception as exc:
        logger.warning("Failed to initialize Langfuse handler: {}", exc)
        _cached_handler = None

    return _cached_handler


def build_trace_metadata(trigger) -> dict:
    return {
        "agent_type": trigger.entity_type,
        "entity_id": trigger.entity_id,
        "trigger_event": trigger.event_type,
        "trigger_payload": trigger.payload or {},
        "tick": trigger.tick,
    }


def extract_session_id(trigger):
    payload = trigger.payload or {}
    order_id = payload.get("order_id")
    if not order_id:
        return None
    return str(order_id)


def build_invoke_config(trigger) -> dict:
    handler = get_callback_handler()
    metadata = build_trace_metadata(trigger)
    session_id = extract_session_id(trigger)
    if session_id is not None:
        metadata["langfuse_session_id"] = session_id
    return {
        "callbacks": [handler] if handler is not None else [],
        "metadata": metadata,
        "run_name": (
            f"{metadata['agent_type']}:{metadata['entity_id']}:"
            f"{metadata['trigger_event']}"
        ),
        "tags": [
            f"agent:{metadata['agent_type']}",
            f"event:{metadata['trigger_event']}",
        ],
    }
