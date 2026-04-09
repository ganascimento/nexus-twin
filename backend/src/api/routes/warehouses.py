from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_warehouse_service
from src.api.models.common import StockAdjust
from src.api.models.warehouses import WarehouseCreate, WarehouseResponse, WarehouseUpdate
from src.services import NotFoundError

router = APIRouter(prefix="/entities/warehouses", tags=["warehouses"])


@router.get("/")
async def list_warehouses(service=Depends(get_warehouse_service)):
    warehouses = await service.list_warehouses()
    return [WarehouseResponse.model_validate(w) for w in warehouses]


@router.get("/{warehouse_id}")
async def get_warehouse(warehouse_id: str, service=Depends(get_warehouse_service)):
    try:
        warehouse = await service.get_warehouse(warehouse_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return WarehouseResponse.model_validate(warehouse)


@router.post("/", status_code=201)
async def create_warehouse(body: WarehouseCreate, service=Depends(get_warehouse_service)):
    result = await service.create_warehouse(body.model_dump())
    return WarehouseResponse.model_validate(result)


@router.patch("/{warehouse_id}")
async def update_warehouse(warehouse_id: str, body: WarehouseUpdate, service=Depends(get_warehouse_service)):
    try:
        result = await service.update_warehouse(warehouse_id, body.model_dump(exclude_unset=True))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return WarehouseResponse.model_validate(result)


@router.delete("/{warehouse_id}")
async def delete_warehouse(warehouse_id: str, service=Depends(get_warehouse_service)):
    try:
        await service.delete_warehouse(warehouse_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "deleted"}


@router.patch("/{warehouse_id}/stock")
async def adjust_warehouse_stock(warehouse_id: str, body: StockAdjust, service=Depends(get_warehouse_service)):
    try:
        await service.adjust_stock(warehouse_id, body.material_id, body.delta)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated"}
