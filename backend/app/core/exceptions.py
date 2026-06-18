"""
Custom exception hierarchy for EPIMS.

Convention:
  - AppException           — base for all domain/business errors
  - HTTP-mapped exceptions — raised in services, caught by FastAPI exception handlers
  - DomainException        — business rule violations (400)
  - NotFoundException      — entity not found (404)
  - PermissionDenied       — RBAC rejection (403)
  - ConflictException      — duplicate / state conflict (409)
  - UnprocessableEntity    — validation that Pydantic can't catch (422)
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


# ── Base ─────────────────────────────────────────────────────────────────────

class AppException(Exception):
    """Root exception. Carries a human-readable message and optional detail."""

    def __init__(self, message: str, detail: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


# ── HTTP-mapped domain exceptions ─────────────────────────────────────────────

class NotFoundException(AppException):
    """Resource does not exist — maps to HTTP 404."""
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, resource: str, identifier: Any = None) -> None:
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(message=detail)
        self.resource = resource
        self.identifier = identifier


class PermissionDenied(AppException):
    """Caller lacks required permission — maps to HTTP 403."""
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, action: str = "", resource: str = "") -> None:
        msg = "Permission denied"
        if action and resource:
            msg = f"Permission denied: cannot '{action}' on '{resource}'"
        elif action:
            msg = f"Permission denied: '{action}'"
        super().__init__(message=msg)


class ConflictException(AppException):
    """Duplicate or state conflict — maps to HTTP 409."""
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, message: str, detail: Any = None) -> None:
        super().__init__(message=message, detail=detail)


class DomainException(AppException):
    """Business rule violation — maps to HTTP 400."""
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, detail: Any = None) -> None:
        super().__init__(message=message, detail=detail)


class UnprocessableEntity(AppException):
    """Semantically invalid input — maps to HTTP 422."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message=message)
        self.field = field


class ServiceUnavailable(AppException):
    """External dependency unavailable — maps to HTTP 503."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


# ── Auth exceptions ───────────────────────────────────────────────────────────

class InvalidCredentials(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self) -> None:
        super().__init__(message="Invalid email or password")


class TokenExpired(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self) -> None:
        super().__init__(message="Token has expired")


class InvalidToken(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self) -> None:
        super().__init__(message="Could not validate credentials")


class AccountDisabled(AppException):
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self) -> None:
        super().__init__(message="Account is disabled")


# ── Domain-specific exceptions ────────────────────────────────────────────────

class InvalidStatusTransition(DomainException):
    """Raised when a document status change is not allowed."""

    def __init__(self, entity: str, from_status: str, to_status: str) -> None:
        super().__init__(
            message=f"{entity}: transition from '{from_status}' to '{to_status}' is not allowed"
        )
        self.from_status = from_status
        self.to_status = to_status


class InsufficientStock(DomainException):
    """Raised when stock quantity is insufficient for an operation."""

    def __init__(self, material: str, required: float, available: float) -> None:
        super().__init__(
            message=(
                f"Insufficient stock for '{material}': "
                f"required {required}, available {available}"
            )
        )


class ApprovalWorkflowError(DomainException):
    """Raised when approval engine encounters an invalid state."""


class ThreeWayMatchFailed(DomainException):
    """Raised when PO/GRN/Invoice quantities or prices don't reconcile."""

    def __init__(self, variances: dict[str, Any]) -> None:
        super().__init__(
            message="Three-way match failed — variances exceed tolerance",
            detail=variances,
        )


class VendorBlocked(DomainException):
    """Raised when a blocked vendor is used in a transaction."""

    def __init__(self, vendor_name: str) -> None:
        super().__init__(
            message=f"Vendor '{vendor_name}' is blocked and cannot be used in new transactions"
        )


# ── FastAPI exception handler helper ─────────────────────────────────────────

def to_http_exception(exc: AppException) -> HTTPException:
    """Convert any AppException to a FastAPI HTTPException."""
    status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = exc.detail if exc.detail is not None else exc.message
    return HTTPException(status_code=status_code, detail=detail)
