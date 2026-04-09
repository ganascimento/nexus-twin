from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_material_service
from src.api.models.materials import MaterialCreate, MaterialResponse, MaterialUpdate
from src.services import ConflictError, NotFoundError

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("/")
async def list_materials(active_only: bool = False, service=Depends(get_material_service)):
    materials = await service.list_materials(active_only=active_only)
    return [MaterialResponse.model_validate(m) for m in materials]


@router.post("/", status_code=201)
async def create_material(body: MaterialCreate, service=Depends(get_material_service)):
    result = await service.create_material(body.model_dump())
    return MaterialResponse.model_validate(result)


@router.patch("/{material_id}")
async def update_material(material_id: str, body: MaterialUpdate, service=Depends(get_material_service)):
    try:
        result = await service.update_material(material_id, body.model_dump())
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return MaterialResponse.model_validate(result)


@router.patch("/{material_id}/deactivate")
async def deactivate_material(material_id: str, service=Depends(get_material_service)):
    try:
        result = await service.deactivate_material(material_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return MaterialResponse.model_validate(result)
