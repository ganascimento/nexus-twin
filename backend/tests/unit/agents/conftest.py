from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel as FakeListChatModel,
)
from langchain_core.messages import AIMessage
from pydantic import BaseModel


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    savepoint = MagicMock()
    savepoint.rollback = AsyncMock()
    savepoint.commit = AsyncMock()
    savepoint.is_active = True
    session.begin_nested = AsyncMock(return_value=savepoint)
    session.close = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def mock_publisher():
    publisher = MagicMock()
    publisher.publish_decision = AsyncMock()
    return publisher


@pytest.fixture
def mock_decision_repo():
    repo = AsyncMock()
    repo.get_recent_by_entity.return_value = []
    repo.create.return_value = None
    return repo


def stub_guardrail():
    class StubDecision(BaseModel):
        action: str
        payload: dict = {}
        reasoning_summary: str = ""

    return StubDecision


def fake_llm(response_json: str):
    return FakeListChatModel(responses=[AIMessage(content=response_json)])
