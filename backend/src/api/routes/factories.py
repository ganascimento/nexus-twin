from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_factory_service
from src.api.models.common import StockAdjust
from src.api.models.factories import FactoryCreate, FactoryResponse, FactoryUpdate
from src.services import NotFoundError

router = APIRouter(prefix="/entities/factories", tags=["factories"])


@router.get("/")
async def list_factories(service=Depends(get_factory_service)):
    factories = await service.list_factories()
    return [FactoryResponse.model_validate(f) for f in factories]


@router.get("/{factory_id}")
async def get_factory(factory_id: str, service=Depends(get_factory_service)):
    try:
        factory = await service.get_factory(factory_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return FactoryResponse.model_validate(factory)


@router.post("/", status_code=201)
async def create_factory(body: FactoryCreate, service=Depends(get_factory_service)):
    result = await service.create_factory(body.model_dump())
    return FactoryResponse.model_validate(result)


@router.patch("/{factory_id}")
async def update_factory(factory_id: str, body: FactoryUpdate, service=Depends(get_factory_service)):
    try:
        result = await service.update_factory(factory_id, body.model_dump(exclude_unset=True))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return FactoryResponse.model_validate(result)


@router.delete("/{factory_id}")
async def delete_factory(factory_id: str, service=Depends(get_factory_service)):
    try:
        await service.delete_factory(factory_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "deleted"}


@router.patch("/{factory_id}/stock")
async def adjust_factory_stock(factory_id: str, body: StockAdjust, service=Depends(get_factory_service)):
    try:
        await service.adjust_stock(factory_id, body.material_id, body.delta)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "updated"}
