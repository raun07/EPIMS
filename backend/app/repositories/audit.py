"""Audit log repository — append-only."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.domain.audit.models import AuditLog
from app.repositories.base import AbstractRepository


class AuditRepository(AbstractRepository[AuditLog]):
    model = AuditLog

    async def log(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        performed_by: UUID | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        changed_fields: list[str] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Append an audit log entry. Never updates existing entries."""
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            performed_by=performed_by,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
        page: int = 1,
        per_page: int = 50,
    ) -> list[AuditLog]:
        return list(
            await self.list(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
                order_by=AuditLog.performed_at.desc(),
                page=page,
                per_page=per_page,
            )
        )

    async def get_by_user(
        self,
        user_id: UUID,
        page: int = 1,
        per_page: int = 50,
    ) -> list[AuditLog]:
        return list(
            await self.list(
                AuditLog.performed_by == user_id,
                order_by=AuditLog.performed_at.desc(),
                page=page,
                per_page=per_page,
            )
        )
