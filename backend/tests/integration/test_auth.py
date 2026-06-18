"""Integration tests for auth endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session, auth_headers):
    # Create user via API
    create_resp = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "testlogin@epims.test",
            "password": "Login@12345",
            "full_name": "Login Test User",
            "employee_id": "LT001",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text

    # Login
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "testlogin@epims.test", "password": "Login@12345"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "testlogin@epims.test"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session, auth_headers):
    await client.post(
        "/api/v1/auth/users",
        json={
            "email": "wrongpw@epims.test",
            "password": "Correct@12345",
            "full_name": "Wrong Password User",
            "employee_id": "WP001",
        },
        headers=auth_headers,
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@epims.test", "password": "WrongPassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, auth_headers: dict):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "roles" in data


@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient, db_session, auth_headers):
    await client.post(
        "/api/v1/auth/users",
        json={
            "email": "refresh@epims.test",
            "password": "Refresh@12345",
            "full_name": "Refresh Test",
            "employee_id": "RF001",
        },
        headers=auth_headers,
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@epims.test", "password": "Refresh@12345"},
    )
    refresh_token = login.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    # New tokens should be different
    assert new_data["access_token"] != login.json()["access_token"]


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/purchase-requisitions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_user_creation_requires_superuser(client: AsyncClient, db_session, auth_headers):
    # Create a viewer-only user
    create_resp = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "viewer@epims.test",
            "password": "Viewer@12345",
            "full_name": "Viewer User",
            "employee_id": "VW001",
            "role_names": ["viewer"],
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    # Login as viewer
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@epims.test", "password": "Viewer@12345"},
    )
    viewer_token = login.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # Try to create another user — should fail (not superuser)
    bad_resp = await client.post(
        "/api/v1/auth/users",
        json={
            "email": "shouldfail@epims.test",
            "password": "Fail@12345",
            "full_name": "Should Fail",
            "employee_id": "SF001",
        },
        headers=viewer_headers,
    )
    assert bad_resp.status_code in (401, 403)
