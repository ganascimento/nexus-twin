import typing


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class Publisher(typing.Protocol):
    async def publish_event(self, event_type: str, payload: dict) -> None: ...
    async def publish_decision(self, entity_id: str, entity_type: str, decision: dict) -> None: ...
