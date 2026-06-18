"""
EPIMS FastAPI application factory.

Startup order:
  1. Connect to DB (check_db_connection)
  2. Connect to Redis
  3. Register domain event handlers (notification, audit)
  4. Mount all API routers
  5. Instrument Prometheus metrics

All exception handlers convert AppException subclasses → HTTP responses,
so services never need to raise HTTPException directly.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.core.exceptions import AppException
from app.database import check_db_connection

logger = logging.getLogger(__name__)


# ── Sentry ────────────────────────────────────────────────────────────────────
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        release=settings.APP_VERSION,
        traces_sample_rate=0.1 if settings.APP_ENV == "production" else 1.0,
    )


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup → yield → shutdown."""
    logger.info("Starting EPIMS v%s [%s]", settings.APP_VERSION, settings.APP_ENV)

    # 1. DB health check
    if not await check_db_connection():
        logger.error("Database connection failed on startup")
        raise RuntimeError("Cannot connect to database")
    logger.info("Database connection OK")

    # 2. Register event handlers
    from app.services.notification_service import register_notification_handlers
    register_notification_handlers()

    yield  # ── application running ──

    logger.info("Shutting down EPIMS")


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="EPIMS — Enterprise Procurement & Inventory Management",
        description=(
            "SAP MM-inspired procure-to-pay system. "
            "Covers PR → Approval → PO → GRN → Invoice (3-way match)."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.APP_ENV == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    @app.middleware("http")
    async def request_timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{duration:.4f}"
        return response

    # ── Exception handlers ────────────────────────────────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
        return JSONResponse(
            status_code=status_code,
            content={"success": False, "detail": exc.message, "extra": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "detail": "Validation error",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
        return await http_exception_handler(request, exc)

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.api.v1.auth import router as auth_router
    from app.api.v1.inventory import router as inventory_router
    from app.api.v1.invoice import router as invoice_router
    from app.api.v1.master_data import router as master_data_router
    from app.api.v1.procurement import router as procurement_router
    from app.api.v1.reports import router as reports_router

    prefix = "/api/v1"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(master_data_router, prefix=prefix)
    app.include_router(procurement_router, prefix=prefix)
    app.include_router(inventory_router, prefix=prefix)
    app.include_router(invoice_router, prefix=prefix)
    app.include_router(reports_router, prefix=prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], include_in_schema=False)
    async def health():
        db_ok = await check_db_connection()
        return {
            "status": "ok" if db_ok else "degraded",
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "database": "ok" if db_ok else "unreachable",
        }

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }

    logger.info("EPIMS application configured with %d routes", len(app.routes))
    return app


app = create_app()
