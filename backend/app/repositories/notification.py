"""Notification and Audit repositories."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.domain.notification.models import Notification, NotificationTemplate
from app.repositories.base import AbstractRepository


class NotificationRepository(AbstractRepository[Notification]):
    model = Notification

    async def get_for_user(
        self, user_id: UUID, unread_only: bool = False,
        page: int = 1, per_page: int = 20
    ) -> list[Notification]:
        filters = [Notification.recipient_id == user_id]
        if unread_only:
            filters.append(Notification.is_read == False)  # noqa: E712
        return list(
            await self.list(
                *filters,
                order_by=Notification.created_at.desc(),
                page=page,
                per_page=per_page,
            )
        )

    async def count_unread(self, user_id: UUID) -> int:
        return await self.count(
            Notification.recipient_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )

    async def mark_all_read(self, user_id: UUID) -> None:
        from datetime import UTC, datetime
        from sqlalchemy import update

        stmt = (
            update(Notification)
            .where(
                Notification.recipient_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True, read_at=datetime.now(UTC))
        )
        await self.session.execute(stmt)

    async def get_template(self, event_type: str) -> NotificationTemplate | None:
        stmt = select(NotificationTemplate).where(
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.is_active == True,  # noqa: E712
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
