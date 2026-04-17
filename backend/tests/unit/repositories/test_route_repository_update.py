from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.repositories.route import RouteRepository


@pytest.mark.asyncio
async def test_update_route_data():
    route_id = uuid4()
    session = AsyncMock()
    session.execute.return_value = MagicMock()

    repo = RouteRepository(session)
    await repo.update_route_data(
        route_id,
        path=[[-46.6, -23.5], [-45.8, -22.8]],
        timestamps=[5, 10],
        eta_ticks=5,
    )

    session.execute.assert_called_once()
