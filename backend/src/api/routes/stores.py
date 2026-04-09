from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_store_service
from src.api.models.common import StockAdjust
from src.api.models.stores import StoreCreate, StoreResponse, StoreUpdate
from src.services import NotFoundError

router = APIRouter(prefix="/entities/stores", tags=["stores"])


@router.get("/")
async def list_stores(service=Depends(get_store_service)):
    stores = await service.list_stores()
    return [StoreResponse.model_validate(s) for s in stores]


@router.get("/{store_id}")
async def get_store(store_id: str, service=Depends(get_store_service)):
    try:
        store = await service.get_store(store_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return StoreResponse.model_validate(store)


@router.post("/", status_code=201)
async def create_store(body: StoreCreate, service=Depends(get_store_service)):
    result = await service.create_store(body.model_dump())
    return StoreResponse.model_validate(result)


@router.patch("/{store_id}")
async def update_store(store_id: str, body: StoreUpdate, service=Depends(get_store_service)):
    try:
        result = await service.update_store(store_id, body.model_dump(exclude_unset=True))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return StoreResponse.model_validate(result)


@router.delete("/{store_id}")
async def delete_store(store_id: str, service=Depends(get_store_service)):
    try:
        await service.delete_store(store_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "deleted"}


@router.patch("/{store_id}/stock")
async def adjust_store_stock(store_id: str, body: StockAdjust, service=Depends(get_store_service)):
    try:
        await service.adjust_stock(store_id, body.material_id, body.delta)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated"}
