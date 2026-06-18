"""
Lightweight synchronous domain event dispatcher.

Services emit events; the notification and audit services subscribe to them.
Events are dispatched in-process (not via Celery) so handlers run within
the same request context and can participate in the unit of work transaction.

Heavy work (sending emails, generating reports) is always delegated to
Celery tasks from within the handlers — never done inline.

Usage:
    # 1. Define an event (dataclass)
    @dataclass
    class PRSubmittedEvent:
        pr_id: str
        requested_by_id: str
        total_value: float

    # 2. Subscribe a handler
    @event_dispatcher.on(PRSubmittedEvent)
    async def notify_approver(event: PRSubmittedEvent) -> None:
        await some_service.notify(...)

    # 3. Emit from a service
    await event_dispatcher.emit(PRSubmittedEvent(pr_id=pr.id, ...))
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

HandlerFn = Callable[..., Coroutine[Any, Any, None]]
T = TypeVar("T")


class EventDispatcher:
    """
    Simple pub-sub dispatcher for domain events.
    All handlers are async; they run sequentially within the same task.
    Errors in one handler are logged and do NOT abort subsequent handlers.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[HandlerFn]] = defaultdict(list)

    def on(self, event_type: type[T]) -> Callable[[HandlerFn], HandlerFn]:
        """Decorator to register a handler for a specific event type."""

        def decorator(fn: HandlerFn) -> HandlerFn:
            self._handlers[event_type].append(fn)
            return fn

        return decorator

    def subscribe(self, event_type: type[T], handler: HandlerFn) -> None:
        """Programmatically subscribe a handler."""
        self._handlers[event_type].append(handler)

    async def emit(self, event: Any) -> None:
        """Dispatch an event to all registered handlers."""
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                logger.exception(
                    "Event handler '%s' failed for event '%s': %s",
                    handler.__name__,
                    type(event).__name__,
                    exc,
                )


# Singleton instance — import and use directly
event_dispatcher = EventDispatcher()


# ── Domain Events ─────────────────────────────────────────────────────────────
# Defined here so they can be imported by both emitters (services)
# and handlers (notification/audit services).

@dataclass
class UserCreatedEvent:
    user_id: str
    email: str
    full_name: str
    created_by_id: str


@dataclass
class PRSubmittedEvent:
    pr_id: str
    pr_number: str
    requested_by_id: str
    total_value: float
    currency: str


@dataclass
class PRApprovedEvent:
    pr_id: str
    pr_number: str
    approved_by_id: str


@dataclass
class PRRejectedEvent:
    pr_id: str
    pr_number: str
    rejected_by_id: str
    reason: str


@dataclass
class POCreatedEvent:
    po_id: str
    po_number: str
    vendor_id: str
    total_amount: float
    currency: str
    created_by_id: str


@dataclass
class POReleasedEvent:
    po_id: str
    po_number: str
    vendor_id: str
    released_by_id: str


@dataclass
class GRNPostedEvent:
    grn_id: str
    grn_number: str
    po_id: str
    warehouse_id: str
    posted_by_id: str
    total_value: float


@dataclass
class InvoiceCreatedEvent:
    invoice_id: str
    invoice_number: str
    vendor_id: str
    total_amount: float
    created_by_id: str


@dataclass
class InvoiceMatchedEvent:
    invoice_id: str
    invoice_number: str
    match_result: str  # MATCHED | WITHIN_TOLERANCE | FAILED
    verified_by_id: str


@dataclass
class ApprovalRequiredEvent:
    instance_id: str
    document_type: str
    document_id: str
    approver_id: str
    document_number: str


@dataclass
class ApprovalActionTakenEvent:
    instance_id: str
    document_type: str
    document_id: str
    action: str  # APPROVED | REJECTED | DELEGATED
    actor_id: str
    comments: str | None


@dataclass
class LowStockEvent:
    material_id: str
    material_number: str
    warehouse_id: str
    current_qty: float
    reorder_point: float
