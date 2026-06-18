"""
Integration test fixtures — require a live Postgres + Redis.
Set env vars before running:
  DATABASE_URL=postgresql+asyncpg://epims_test:test@localhost:5432/epims_test
  REDIS_URL=redis://localhost:6379/15
"""
from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import create_app

# ── Session-scoped Postgres engine ────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://epims_test:test_password@localhost:5432/epims_test",
    )
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(pg_engine) -> AsyncGenerator[AsyncSession, None]:
    Session = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Superuser token ───────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def superuser_token(db_session: AsyncSession) -> str:
    from app.domain.auth.models import User, Role
    from sqlalchemy import select

    user_id = uuid4()
    user = User(
        id=user_id,
        employee_id=f"SU{str(user_id)[:6]}",
        email=f"su_{str(user_id)[:6]}@test.local",
        full_name="Test Superuser",
        hashed_password=hash_password("Test@12345"),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.flush()

    return create_access_token(
        subject=user.email,
        user_id=str(user.id),
        roles=["superuser"],
        permissions=["*:*"],
    )


@pytest.fixture
def auth_headers(superuser_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {superuser_token}"}
