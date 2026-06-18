"""
Pytest fixtures for EPIMS.

Strategy:
  - Uses SQLite in-memory (via aiosqlite) for unit tests → no Postgres needed
  - Uses a real test Postgres for integration tests (requires TEST_DATABASE_URL env var)
  - Factory-boy factories generate test data without repetition
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import create_app

# ── Event loop ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ── Test database (SQLite in-memory for unit tests) ───────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


# ── FastAPI test client ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── Auth helpers ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def superuser_token(client: AsyncClient) -> str:
    """Register a superuser and return its access token."""
    from app.core.security import create_access_token
    token = create_access_token(
        subject="admin@epims.test",
        user_id=str(uuid4()),
        roles=["superuser"],
        permissions=["*:*"],
    )
    return token


@pytest.fixture
def auth_headers(superuser_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {superuser_token}"}
