"""
Integration tests: PR full lifecycle.

Creates → Submits → Rejects → Resubmits → Approves (direct)
Requires live Postgres.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_pr_create(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        "/api/v1/purchase-requisitions",
        json={
            "title": "Test PR — Integration",
            "description": "Integration test PR",
            "priority": "NORMAL",
            "items": [
                {
                    "description": "Office Chairs",
                    "quantity": 10,
                    "estimated_price": 5000.00,
                }
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "DRAFT"
    assert data["pr_number"].startswith("PR-")
    assert len(data["items"]) == 1
    return data["id"]


@pytest.mark.asyncio
async def test_pr_submit(client: AsyncClient, auth_headers: dict):
    # Create
    create_resp = await client.post(
        "/api/v1/purchase-requisitions",
        json={
            "title": "Submit test PR",
            "items": [{"description": "Laptop Stand", "quantity": 2, "estimated_price": 1500}],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    pr_id = create_resp.json()["id"]

    # Submit
    submit_resp = await client.post(
        f"/api/v1/purchase-requisitions/{pr_id}/submit",
        headers=auth_headers,
    )
    assert submit_resp.status_code == 200, submit_resp.text
    data = submit_resp.json()
    assert data["status"] in ("SUBMITTED", "PENDING_APPROVAL")


@pytest.mark.asyncio
async def test_pr_cancel_from_draft(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/purchase-requisitions",
        json={
            "title": "Cancel test PR",
            "items": [{"description": "Whiteboard Markers", "quantity": 5}],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    pr_id = create_resp.json()["id"]

    cancel_resp = await client.post(
        f"/api/v1/purchase-requisitions/{pr_id}/cancel",
        headers=auth_headers,
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_pr_list_pagination(client: AsyncClient, auth_headers: dict):
    # Create 5 PRs
    for i in range(5):
        await client.post(
            "/api/v1/purchase-requisitions",
            json={
                "title": f"Pagination test PR {i}",
                "items": [{"description": f"Item {i}", "quantity": 1}],
            },
            headers=auth_headers,
        )

    resp = await client.get(
        "/api/v1/purchase-requisitions",
        params={"page": 1, "per_page": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert data["meta"]["per_page"] == 3


@pytest.mark.asyncio
async def test_pr_reject_requires_reason(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/purchase-requisitions",
        json={
            "title": "Reject test PR",
            "items": [{"description": "Keyboard", "quantity": 1, "estimated_price": 2000}],
        },
        headers=auth_headers,
    )
    pr_id = create_resp.json()["id"]

    # Submit first
    await client.post(f"/api/v1/purchase-requisitions/{pr_id}/submit", headers=auth_headers)

    # Reject with too-short reason should fail
    reject_resp = await client.post(
        f"/api/v1/purchase-requisitions/{pr_id}/reject",
        json={"reason": "no"},  # too short
        headers=auth_headers,
    )
    assert reject_resp.status_code == 422


@pytest.mark.asyncio
async def test_pr_detail_includes_items(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(
        "/api/v1/purchase-requisitions",
        json={
            "title": "Multi-line PR",
            "items": [
                {"description": "Monitor", "quantity": 2, "estimated_price": 15000},
                {"description": "Keyboard", "quantity": 2, "estimated_price": 2000},
                {"description": "Mouse", "quantity": 2, "estimated_price": 1000},
            ],
        },
        headers=auth_headers,
    )
    pr_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/purchase-requisitions/{pr_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert len(data["items"]) == 3
    assert data["items"][0]["line_number"] == 1
    assert data["items"][1]["line_number"] == 2
    assert data["items"][2]["line_number"] == 3
