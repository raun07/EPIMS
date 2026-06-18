"""
Document number generators.

All use a PostgreSQL sequence-style approach: lock a counter row,
increment it, and return the formatted number — all within the UoW transaction.

Format examples:
  PR-2024-000001, PO-2024-000001, GRN-2024-000001
  MAT-000001, VEN-000001, MOV-20240115-000001
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def _next_sequence(session: "AsyncSession", seq_name: str) -> int:
    """Get next value from a named PostgreSQL sequence."""
    result = await session.execute(text(f"SELECT nextval('{seq_name}')"))
    return result.scalar_one()


async def generate_pr_number(session: "AsyncSession") -> str:
    year = date.today().year
    n = await _next_sequence(session, "seq_pr_number")
    return f"PR-{year}-{n:06d}"


async def generate_po_number(session: "AsyncSession") -> str:
    year = date.today().year
    n = await _next_sequence(session, "seq_po_number")
    return f"PO-{year}-{n:06d}"


async def generate_grn_number(session: "AsyncSession") -> str:
    year = date.today().year
    n = await _next_sequence(session, "seq_grn_number")
    return f"GRN-{year}-{n:06d}"


async def generate_invoice_number(session: "AsyncSession") -> str:
    year = date.today().year
    n = await _next_sequence(session, "seq_inv_number")
    return f"INV-{year}-{n:06d}"


async def generate_material_number(session: "AsyncSession") -> str:
    n = await _next_sequence(session, "seq_mat_number")
    return f"MAT-{n:06d}"


async def generate_vendor_number(session: "AsyncSession") -> str:
    n = await _next_sequence(session, "seq_ven_number")
    return f"VEN-{n:06d}"


async def generate_movement_number(session: "AsyncSession") -> str:
    today = date.today().strftime("%Y%m%d")
    n = await _next_sequence(session, "seq_mov_number")
    return f"MOV-{today}-{n:06d}"


# SQL to create sequences (added to Alembic migration)
SEQUENCE_DDL = """
CREATE SEQUENCE IF NOT EXISTS seq_pr_number  START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS seq_po_number  START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS seq_grn_number START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS seq_inv_number START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS seq_mat_number START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS seq_ven_number START 1 INCREMENT 1;
CREATE SEQUENCE IF NOT EXISTS seq_mov_number START 1 INCREMENT 1;
"""
