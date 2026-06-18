"""Integration tests for master data (materials and vendors)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_material(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/materials",
        json={
            "description": "Stainless Steel Bolt M8x30",
            "material_type": "RAW",
            "standard_price": 2.50,
            "reorder_point": 500,
            "min_order_qty": 100,
            "lead_time_days": 7,
            "currency": "INR",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["material_number"].startswith("MAT-")
    assert data["description"] == "Stainless Steel Bolt M8x30"
    assert data["is_active"] is True

    # Get by ID
    get_resp = await client.get(f"/api/v1/materials/{data['id']}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == data["id"]


@pytest.mark.asyncio
async def test_material_list_and_search(client: AsyncClient, auth_headers: dict):
    # Create 3 materials
    for desc in ["Copper Wire 1.5mm", "Copper Wire 2.5mm", "Aluminium Cable 4mm"]:
        await client.post(
            "/api/v1/materials",
            json={"description": desc, "material_type": "RAW", "currency": "INR"},
            headers=auth_headers,
        )

    # List all
    list_resp = await client.get("/api/v1/materials", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["meta"]["total"] >= 3

    # Search
    search_resp = await client.get("/api/v1/materials?q=Copper", headers=auth_headers)
    assert search_resp.status_code == 200


@pytest.mark.asyncio
async def test_create_vendor(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/vendors",
        json={
            "name": "Tata Steel Ltd",
            "short_name": "TATA",
            "vendor_type": "SUPPLIER",
            "gst_number": "27AAACT2727Q1ZW",
            "email": "purchase@tatasteel.example.com",
            "payment_terms": "NET30",
            "currency": "INR",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["vendor_number"].startswith("V")
    assert data["name"] == "Tata Steel Ltd"
    assert data["status"] == "ACTIVE"
    return data["id"]


@pytest.mark.asyncio
async def test_block_and_unblock_vendor(client: AsyncClient, auth_headers: dict):
    # Create
    create = await client.post(
        "/api/v1/vendors",
        json={"name": "Shady Supplies Inc", "vendor_type": "SUPPLIER", "currency": "INR"},
        headers=auth_headers,
    )
    vid = create.json()["id"]

    # Block
    block = await client.post(
        f"/api/v1/vendors/{vid}/block",
        json={"reason": "Multiple quality failures and delayed deliveries"},
        headers=auth_headers,
    )
    assert block.status_code == 200
    assert block.json()["status"] == "BLOCKED"

    # Unblock
    unblock = await client.post(f"/api/v1/vendors/{vid}/unblock", headers=auth_headers)
    assert unblock.status_code == 200
    assert unblock.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_vendor_block_too_short_reason(client: AsyncClient, auth_headers: dict):
    create = await client.post(
        "/api/v1/vendors",
        json={"name": "Quick Block Vendor", "vendor_type": "SUPPLIER", "currency": "INR"},
        headers=auth_headers,
    )
    vid = create.json()["id"]

    resp = await client.post(
        f"/api/v1/vendors/{vid}/block",
        json={"reason": "bad"},  # too short
        headers=auth_headers,
    )
    assert resp.status_code == 422
