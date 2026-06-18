"""
Material Master service.
"""
from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ConflictException, NotFoundException
from app.core.unit_of_work import UnitOfWork
from app.domain.material.models import Material, MaterialGroup, UnitOfMeasure
from app.utils.number_gen import generate_material_number


class MaterialService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create_material(self, data: dict, created_by_id: UUID) -> Material:
        mat_number = await generate_material_number(self.uow.session)
        data["material_number"] = mat_number
        data["created_by"] = created_by_id

        material = await self.uow.materials.create(data)

        await self.uow.audit.log(
            entity_type="Material",
            entity_id=material.id,
            action="CREATE",
            performed_by=created_by_id,
            new_values={"material_number": mat_number, "description": data.get("description")},
        )

        return material

    async def update_material(
        self, material_id: UUID, data: dict, updated_by_id: UUID
    ) -> Material:
        material = await self.uow.materials.get_or_raise(material_id)
        allowed = {
            "description", "material_type", "material_group_id", "standard_price",
            "reorder_point", "min_order_qty", "max_order_qty", "lead_time_days",
            "shelf_life_days", "storage_conditions", "is_active",
        }
        filtered = {k: v for k, v in data.items() if k in allowed}
        old_values = {k: str(getattr(material, k)) for k in filtered}

        updated = await self.uow.materials.update(material, filtered)

        await self.uow.audit.log(
            entity_type="Material",
            entity_id=material.id,
            action="UPDATE",
            performed_by=updated_by_id,
            old_values=old_values,
            new_values=filtered,
            changed_fields=list(filtered.keys()),
        )

        return updated

    async def get_material(self, material_id: UUID) -> Material:
        return await self.uow.materials.get_or_raise(material_id)

    async def search_materials(self, query: str, page: int = 1, per_page: int = 20):
        return await self.uow.materials.search(query, page=page, per_page=per_page)

    async def list_materials(self, page: int = 1, per_page: int = 20):
        items = await self.uow.materials.get_active(page=page, per_page=per_page)
        total = await self.uow.materials.count(Material.is_active == True)  # noqa: E712
        return items, total
