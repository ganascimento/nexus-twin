from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.truck import TruckService


@pytest.mark.asyncio
async def test_schedule_maintenance_saves_tracking_fields():
    mock_repo = AsyncMock()
    mock_truck = MagicMock()
    mock_truck.id = "truck_01"
    mock_truck.status = "idle"
    mock_truck.degradation = 0.7
    mock_repo.get_by_id.return_value = mock_truck

    mock_publisher = AsyncMock()
    service = TruckService(mock_repo, mock_publisher)

    with patch("src.services.truck.calculate_maintenance_ticks", return_value=17) as mock_calc:
        await service.schedule_maintenance("truck_01", current_tick=10)

    mock_calc.assert_called_once_with(0.7)
    mock_repo.set_maintenance_info.assert_called_once_with("truck_01", 10, 17)
    mock_repo.update_status.assert_called_once_with("truck_01", "maintenance")
    mock_repo.update_degradation.assert_called_once_with("truck_01", 0.0, 0.0)
