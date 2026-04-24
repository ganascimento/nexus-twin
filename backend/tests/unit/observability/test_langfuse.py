import importlib
import json
from unittest.mock import MagicMock, patch

import pytest

from src.simulation.events import SimulationEvent


def _reload_module():
    import src.observability.langfuse as module

    importlib.reload(module)
    return module


@pytest.fixture(autouse=True)
def _reset_handler_cache(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    yield
    _reload_module()


def _make_trigger(
    event_type: str = "low_stock_trigger",
    entity_type: str = "store",
    entity_id: str = "store-001",
    payload: dict | None = None,
    tick: int = 42,
) -> SimulationEvent:
    return SimulationEvent(
        event_type=event_type,
        source="engine",
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload if payload is not None else {},
        tick=tick,
    )


def test_get_callback_handler_returns_none_when_public_key_missing(monkeypatch):
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-secret")
    module = _reload_module()
    assert module.get_callback_handler() is None


def test_get_callback_handler_returns_none_when_secret_key_missing(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-public")
    module = _reload_module()
    assert module.get_callback_handler() is None


def test_get_callback_handler_returns_none_when_both_empty_strings(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    module = _reload_module()
    assert module.get_callback_handler() is None


def test_get_callback_handler_returns_handler_when_both_keys_set(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-secret")
    module = _reload_module()

    fake_handler = MagicMock(name="CallbackHandler()")
    with patch.object(module, "CallbackHandler", return_value=fake_handler) as factory:
        handler = module.get_callback_handler()
        assert handler is fake_handler
        factory.assert_called_once()


def test_get_callback_handler_defaults_host_to_localhost(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-secret")
    module = _reload_module()

    with patch.object(module, "CallbackHandler") as factory:
        module.get_callback_handler()
        kwargs = factory.call_args.kwargs
        assert kwargs.get("host") == "http://localhost:3100"


def test_get_callback_handler_caches_instance(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-secret")
    module = _reload_module()

    with patch.object(module, "CallbackHandler") as factory:
        factory.return_value = MagicMock(name="Handler")
        first = module.get_callback_handler()
        second = module.get_callback_handler()
        assert first is second
        assert factory.call_count == 1


def test_get_callback_handler_returns_none_when_handler_init_raises(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-public")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-secret")
    module = _reload_module()

    with patch.object(
        module, "CallbackHandler", side_effect=RuntimeError("langfuse down")
    ):
        assert module.get_callback_handler() is None


def test_build_trace_metadata_extracts_all_fields():
    module = _reload_module()
    event = _make_trigger(
        event_type="low_stock_trigger",
        entity_type="store",
        entity_id="store-001",
        payload={"order_id": "abc-123", "material_id": "cimento"},
        tick=42,
    )
    metadata = module.build_trace_metadata(event)
    assert metadata == {
        "agent_type": "store",
        "entity_id": "store-001",
        "trigger_event": "low_stock_trigger",
        "trigger_payload": json.dumps(
            {"order_id": "abc-123", "material_id": "cimento"}
        ),
        "tick": "42",
    }


def test_build_trace_metadata_handles_null_payload():
    module = _reload_module()
    event = SimulationEvent(
        event_type="truck_arrived",
        source="engine",
        entity_type="truck",
        entity_id="truck-004",
        payload={},
        tick=7,
    )
    metadata = module.build_trace_metadata(event)
    assert metadata["trigger_payload"] == "{}"
    assert metadata["tick"] == "7"
    assert metadata["agent_type"] == "truck"


def test_extract_session_id_returns_order_id_when_present():
    module = _reload_module()
    event = _make_trigger(payload={"order_id": "abc-123"})
    assert module.extract_session_id(event) == "abc-123"


def test_extract_session_id_returns_none_when_payload_empty():
    module = _reload_module()
    event = _make_trigger(payload={})
    assert module.extract_session_id(event) is None


def test_extract_session_id_returns_none_when_payload_missing_order_id():
    module = _reload_module()
    event = _make_trigger(payload={"material_id": "cimento", "quantity_tons": 10})
    assert module.extract_session_id(event) is None


def test_extract_session_id_returns_none_when_order_id_is_falsy():
    module = _reload_module()
    for payload in ({"order_id": None}, {"order_id": ""}, {"order_id": 0}):
        event = _make_trigger(payload=payload)
        assert module.extract_session_id(event) is None


def test_extract_session_id_coerces_non_string_order_id():
    module = _reload_module()
    event = _make_trigger(payload={"order_id": 42})
    assert module.extract_session_id(event) == "42"
