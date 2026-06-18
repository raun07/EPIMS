"""
Generic async repository base.

All concrete repositories inherit from AbstractRepository[T] and get
standard CRUD operations for free. Override or extend as needed.

Filtering is handled via SQLAlchemy column expressions passed as *filters.
Pagination is first-class: list() always accepts page + per_page.
"""
from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class AbstractRepository(Generic[ModelT]):
    """
    Generic async repository. Provides:
      - get(id)
      - get_or_raise(id)
      - list(filters, order_by, page, per_page)
      - count(filters)
      - create(data)
      - update(instance, data)
      - delete(instance)
      - save(instance)
      - exists(filters)
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Single-record fetches ─────────────────────────────────────────────────

    async def get(self, id: UUID) -> ModelT | None:
        """Fetch by primary key. Returns None if not found."""
        return await self.session.get(self.model, id)

    async def get_or_raise(self, id: UUID) -> ModelT:
        """Fetch by PK; raises NotFoundException if missing."""
        from app.core.exceptions import NotFoundException

        instance = await self.get(id)
        if instance is None:
            raise NotFoundException(self.model.__name__, str(id))
        return instance

    async def get_by(self, **kwargs: Any) -> ModelT | None:
        """Fetch single instance matching keyword filters (AND)."""
        stmt = select(self.model)
        for attr, value in kwargs.items():
            stmt = stmt.where(getattr(self.model, attr) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Collection fetches ────────────────────────────────────────────────────

    async def list(
        self,
        *filters: Any,
        order_by: Any = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Sequence[ModelT]:
        """
        Paginated list with optional column expression filters and ordering.

        Example:
            users = await repo.list(
                User.is_active == True,
                order_by=User.created_at.desc(),
                page=2, per_page=50,
            )
        """
        stmt = select(self.model)
        for f in filters:
            stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            # Default: newest first if created_at exists
            if hasattr(self.model, "created_at"):
                stmt = stmt.order_by(self.model.created_at.desc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self, *filters: Any, order_by: Any = None) -> Sequence[ModelT]:
        """Unpaginated list — use carefully on large tables."""
        stmt = select(self.model)
        for f in filters:
            stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count(self, *filters: Any) -> int:
        """Count rows matching filters."""
        stmt = select(func.count()).select_from(self.model)
        for f in filters:
            stmt = stmt.where(f)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists(self, **kwargs: Any) -> bool:
        """Return True if any row matches the keyword filters."""
        stmt = select(func.count()).select_from(self.model)
        for attr, value in kwargs.items():
            stmt = stmt.where(getattr(self.model, attr) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0

    # ── Writes ────────────────────────────────────────────────────────────────

    async def create(self, data: dict[str, Any]) -> ModelT:
        """Create a new instance from a dict of field values."""
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, data: dict[str, Any]) -> ModelT:
        """Apply a dict of updates to an existing instance."""
        for key, value in data.items():
            setattr(instance, key, value)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def save(self, instance: ModelT) -> ModelT:
        """Add/update an already-modified instance and flush."""
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Hard delete an instance."""
        await self.session.delete(instance)
        await self.session.flush()

    # ── Bulk ─────────────────────────────────────────────────────────────────

    async def bulk_create(self, data_list: list[dict[str, Any]]) -> list[ModelT]:
        """Create multiple instances in a single flush."""
        instances = [self.model(**d) for d in data_list]
        self.session.add_all(instances)
        await self.session.flush()
        for inst in instances:
            await self.session.refresh(inst)
        return instances

    # ── Raw query helper ─────────────────────────────────────────────────────

    async def execute(self, stmt: Select) -> Any:
        """Execute a raw SQLAlchemy select statement."""
        return await self.session.execute(stmt)
