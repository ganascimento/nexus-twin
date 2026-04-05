import typing


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class Publisher(typing.Protocol):
    async def publish_event(self, event_type: str, payload: dict) -> None: ...
