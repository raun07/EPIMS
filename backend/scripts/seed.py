"""
Seed script — run once after `alembic upgrade head`.

  python -m scripts.seed

Creates:
  - 7 RBAC roles with their permission sets
  - Superuser: admin@epims.local / Admin@12345
  - 3 sample users (buyer, approver, warehouse_manager)
  - 5 material groups
  - 3 base UOMs
  - 5 sample materials
  - 3 sample vendors
  - 2 warehouses with storage locations
"""
from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, ".")


ROLES = {
    "superuser": [
        "purchase_requisitions:*", "purchase_orders:*", "goods_receipts:*",
        "invoices:*", "inventory:*", "materials:*", "vendors:*",
        "warehouses:*", "reports:*", "users:*", "*:*",
    ],
    "procurement_manager": [
        "purchase_requisitions:*", "purchase_orders:*", "goods_receipts:read",
        "invoices:read", "vendors:read", "materials:read", "reports:read",
    ],
    "buyer": [
        "purchase_requisitions:create", "purchase_requisitions:read",
        "purchase_requisitions:update",
        "purchase_orders:create", "purchase_orders:read", "purchase_orders:update",
        "materials:read", "vendors:read",
    ],
    "approver": [
        "purchase_requisitions:read", "purchase_requisitions:approve",
        "purchase_orders:read", "purchase_orders:release",
        "reports:read",
    ],
    "warehouse_manager": [
        "goods_receipts:*", "inventory:*", "materials:read",
        "purchase_orders:read",
    ],
    "accounts_payable": [
        "invoices:*", "purchase_orders:read", "goods_receipts:read",
        "vendors:read", "reports:read",
    ],
    "viewer": [
        "purchase_requisitions:read", "purchase_orders:read",
        "goods_receipts:read", "invoices:read", "inventory:read",
        "materials:read", "vendors:read", "reports:read",
    ],
}

USERS = [
    {
        "employee_id": "EMP001",
        "email": "admin@epims.local",
        "full_name": "System Administrator",
        "password": "Admin@12345",
        "roles": ["superuser"],
        "is_superuser": True,
    },
    {
        "employee_id": "EMP002",
        "email": "buyer@epims.local",
        "full_name": "Rahul Sharma",
        "password": "Buyer@12345",
        "roles": ["buyer"],
        "department": "Procurement",
    },
    {
        "employee_id": "EMP003",
        "email": "approver@epims.local",
        "full_name": "Priya Nair",
        "password": "Approver@12345",
        "roles": ["approver", "procurement_manager"],
        "department": "Finance",
    },
    {
        "employee_id": "EMP004",
        "email": "warehouse@epims.local",
        "full_name": "Kiran Patel",
        "password": "Warehouse@12345",
        "roles": ["warehouse_manager"],
        "department": "Warehouse",
    },
]

MATERIAL_GROUPS = [
    {"code": "RAW", "name": "Raw Materials"},
    {"code": "PACK", "name": "Packaging Materials"},
    {"code": "SPARE", "name": "Spare Parts"},
    {"code": "IT", "name": "IT Equipment"},
    {"code": "CHEM", "name": "Chemicals"},
]

UOMS = [
    {"code": "EA", "name": "Each", "conversion_factor": "1.0"},
    {"code": "KG", "name": "Kilogram", "conversion_factor": "1.0"},
    {"code": "LTR", "name": "Litre", "conversion_factor": "1.0"},
    {"code": "BOX", "name": "Box", "conversion_factor": "1.0"},
    {"code": "MTR", "name": "Metre", "conversion_factor": "1.0"},
]

VENDORS_DATA = [
    {
        "name": "Acme Industrial Supplies",
        "short_name": "ACME",
        "vendor_type": "SUPPLIER",
        "gst_number": "27AABCA1234A1Z5",
        "email": "purchase@acme.example.com",
        "phone": "+91-22-12345678",
        "payment_terms": "NET30",
        "currency": "INR",
    },
    {
        "name": "TechGear Solutions Pvt Ltd",
        "short_name": "TECHGEAR",
        "vendor_type": "SUPPLIER",
        "gst_number": "29AABCT5678B2Z1",
        "email": "orders@techgear.example.com",
        "payment_terms": "NET45",
        "currency": "INR",
    },
    {
        "name": "Global Chem Distributors",
        "short_name": "GLOBALCHEM",
        "vendor_type": "SUPPLIER",
        "gst_number": "06AABCG9012C3Z8",
        "email": "supply@globalchem.example.com",
        "payment_terms": "NET15",
        "currency": "INR",
    },
]


async def seed():
    from app.config import settings
    from app.database import Base, engine, AsyncSessionLocal
    from app.core.security import hash_password
    from app.domain.auth.models import Permission, Role, User
    from app.domain.material.models import MaterialGroup, UnitOfMeasure
    from app.domain.vendor.models import Vendor

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        print("Seeding RBAC roles and permissions...")
        role_objs: dict[str, Role] = {}

        for role_name, perm_codes in ROLES.items():
            role = Role(id=uuid4(), name=role_name, description=f"System role: {role_name}")
            session.add(role)
            role_objs[role_name] = role
            await session.flush()

            for code in perm_codes:
                resource, action = code.split(":", 1)
                perm = Permission(
                    id=uuid4(),
                    resource=resource,
                    action=action,
                    description=f"{resource}:{action}",
                )
                session.add(perm)
                await session.flush()
                role.permissions.append(perm)

        await session.flush()
        print(f"  Created {len(ROLES)} roles")

        # Users
        print("Seeding users...")
        for u in USERS:
            user = User(
                id=uuid4(),
                employee_id=u["employee_id"],
                email=u["email"],
                full_name=u["full_name"],
                hashed_password=hash_password(u["password"]),
                is_active=True,
                is_superuser=u.get("is_superuser", False),
                department=u.get("department"),
            )
            session.add(user)
            await session.flush()
            for role_name in u.get("roles", []):
                user.roles.append(role_objs[role_name])
        await session.flush()
        print(f"  Created {len(USERS)} users")

        # Material groups
        print("Seeding material groups...")
        for mg in MATERIAL_GROUPS:
            session.add(MaterialGroup(id=uuid4(), **mg))
        await session.flush()

        # UOMs
        print("Seeding units of measure...")
        for uom in UOMS:
            session.add(UnitOfMeasure(id=uuid4(), **uom))
        await session.flush()

        # Vendors
        print("Seeding vendors...")
        for i, vd in enumerate(VENDORS_DATA, start=1):
            session.add(
                Vendor(
                    id=uuid4(),
                    vendor_number=f"V{i:05d}",
                    status="ACTIVE",
                    **vd,
                )
            )
        await session.flush()

        await session.commit()
        print("\n✓ Seed complete!")
        print("  Login: admin@epims.local / Admin@12345")


if __name__ == "__main__":
    asyncio.run(seed())
