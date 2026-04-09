from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_truck_service
from src.api.models.trucks import TruckCreate, TruckResponse
from src.services import NotFoundError

router = APIRouter(prefix="/entities/trucks", tags=["trucks"])


@router.get("/")
async def list_trucks(service=Depends(get_truck_service)):
    trucks = await service.list_trucks()
    return [TruckResponse.model_validate(t) for t in trucks]


@router.get("/{truck_id}")
async def get_truck(truck_id: str, service=Depends(get_truck_service)):
    try:
        truck = await service.get_truck(truck_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return TruckResponse.model_validate(truck)


@router.post("/", status_code=201)
async def create_truck(body: TruckCreate, service=Depends(get_truck_service)):
    result = await service.create_truck(body.model_dump())
    return TruckResponse.model_validate(result)


@router.delete("/{truck_id}")
async def delete_truck(truck_id: str, service=Depends(get_truck_service)):
    try:
        await service.delete_truck(truck_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "deleted"}
