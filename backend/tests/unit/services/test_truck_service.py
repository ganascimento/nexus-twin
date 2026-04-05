import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.truck import TruckService
from src.services import NotFoundError


@pytest.fixture
def repo():
    return AsyncMock()


@pytest.fixture
def publisher():
    return AsyncMock()


@pytest.fixture
def service(repo, publisher):
    return TruckService(repo, publisher)


@pytest.mark.asyncio
async def test_list_trucks_returns_all_with_position_and_cargo(service, repo):
    expected = [MagicMock(), MagicMock()]
    repo.get_all.return_value = expected
    result = await service.list_trucks()
    repo.get_all.assert_called_once()
    assert result == expected


@pytest.mark.asyncio
async def test_get_truck_raises_not_found(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.get_truck("nonexistent")


@pytest.mark.asyncio
async def test_get_truck_returns_complete_detail(service, repo):
    truck = MagicMock()
    repo.get_by_id.return_value = truck
    result = await service.get_truck("truck-001")
    repo.get_by_id.assert_called_once_with("truck-001")
    assert result == truck


@pytest.mark.asyncio
async def test_create_truck_sets_status_idle_and_degradation_zero(service, repo):
    data = {"id": "truck-001", "truck_type": "proprietario", "capacity_tons": 20.0}
    created = MagicMock()
    created.status = "idle"
    created.degradation = 0.0
    repo.create.return_value = created

    result = await service.create_truck(data)

    call_data = repo.create.call_args[0][0]
    assert call_data["status"] == "idle"
    assert call_data["degradation"] == 0.0
    assert result == created


@pytest.mark.asyncio
async def test_delete_truck_idle_removes_without_event(service, repo, publisher):
    truck = MagicMock()
    truck.status = "idle"
    truck.cargo = None
    repo.get_by_id.return_value = truck

    await service.delete_truck("truck-001")

    repo.delete.assert_called_once_with("truck-001")
    publisher.publish_event.assert_not_called()


@pytest.mark.asyncio
async def test_delete_truck_in_transit_publishes_truck_deleted_in_transit_with_cargo(
    service, repo, publisher
):
    truck = MagicMock()
    truck.status = "in_transit"
    truck.cargo = {"material_id": "tijolos", "quantity_tons": 10.0}
    repo.get_by_id.return_value = truck

    await service.delete_truck("truck-001")

    publisher.publish_event.assert_called_once_with(
        "truck_deleted_in_transit",
        {"truck_id": "truck-001", "cargo": truck.cargo},
    )
    repo.delete.assert_called_once_with("truck-001")


@pytest.mark.asyncio
async def test_delete_truck_raises_not_found_if_missing(service, repo):
    repo.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.delete_truck("nonexistent")


@pytest.mark.asyncio
async def test_try_lock_for_evaluation_returns_true_when_repo_succeeds(service, repo):
    repo.try_lock_for_evaluation.return_value = True
    result = await service.try_lock_for_evaluation("truck-001")
    repo.try_lock_for_evaluation.assert_called_once_with("truck-001")
    assert result is True


@pytest.mark.asyncio
async def test_try_lock_for_evaluation_returns_false_when_repo_returns_none(service, repo):
    repo.try_lock_for_evaluation.return_value = False
    result = await service.try_lock_for_evaluation("truck-001")
    assert result is False


@pytest.mark.asyncio
async def test_assign_route_raises_not_implemented(service):
    with pytest.raises(NotImplementedError):
        await service.assign_route("truck-001", {})


@pytest.mark.asyncio
async def test_complete_route_raises_not_implemented(service):
    with pytest.raises(NotImplementedError):
        await service.complete_route("truck-001")


@pytest.mark.asyncio
async def test_interrupt_route_raises_not_implemented(service):
    with pytest.raises(NotImplementedError):
        await service.interrupt_route("truck-001", "breakdown")


@pytest.mark.asyncio
async def test_schedule_maintenance_raises_not_implemented(service):
    with pytest.raises(NotImplementedError):
        await service.schedule_maintenance("truck-001")
