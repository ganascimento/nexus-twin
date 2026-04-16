import re

from src.services import ConflictError, NotFoundError


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:50]


class MaterialService:
    def __init__(self, repo):
        self._repo = repo

    async def list_materials(self, active_only: bool = False):
        return await self._repo.get_all(active_only=active_only)

    async def create_material(self, data: dict):
        payload = data.copy()
        if "id" not in payload:
            payload["id"] = _slugify(payload["name"])
        return await self._repo.create(payload)

    async def update_material(self, id: str, data: dict):
        existing = await self._repo.get_by_id(id)
        if existing is None:
            raise NotFoundError(f"Material '{id}' not found")
        return await self._repo.update(id, data)

    async def deactivate_material(self, id: str):
        if await self._repo.has_linked_entities(id):
            raise ConflictError(f"Material '{id}' is still referenced by active entities")
        return await self._repo.update(id, {"is_active": False})
