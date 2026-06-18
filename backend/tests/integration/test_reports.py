"""Integration tests for reporting endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_dashboard_kpis(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/reports/dashboard", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "pending_pr_approvals" in data
    assert "open_po_value" in data
    assert "overdue_invoices" in data
    assert "low_stock_alerts" in data
    # All values should be non-negative integers or floats
    assert data["pending_pr_approvals"] >= 0
    assert data["open_po_value"] >= 0
    assert data["overdue_invoices"] >= 0
    assert data["low_stock_alerts"] >= 0


@pytest.mark.asyncio
async def test_pr_summary(client: AsyncClient, auth_headers: dict):
    # Create a PR first to ensure there's data
    await client.post(
        "/api/v1/purchase-requisitions",
        json={
            "title": "Report test PR",
            "items": [{"description": "Widget", "quantity": 1}],
        },
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/reports/pr-summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "by_status" in data
    assert isinstance(data["by_status"], list)


@pytest.mark.asyncio
async def test_po_summary(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/reports/po-summary", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "by_status" in data


@pytest.mark.asyncio
async def test_vendor_performance(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/reports/vendor-performance", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_inventory_valuation(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/reports/inventory-valuation", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "warehouses" in data
    assert "grand_total" in data


@pytest.mark.asyncio
async def test_invoice_aging(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/reports/invoice-aging", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # Should have 4 buckets
    buckets = [item["bucket"] for item in data]
    for expected in ["0-30", "31-60", "61-90", "90+"]:
        assert expected in buckets


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "version" in data
