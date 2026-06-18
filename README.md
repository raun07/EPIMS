# EPIMS — Enterprise Procurement & Inventory Management System

SAP MM-inspired full-stack procure-to-pay platform built with FastAPI + React.

## Architecture

```
epims/
├── backend/              FastAPI 0.111 · Python 3.12 · SQLAlchemy 2.0 async
│   ├── app/
│   │   ├── core/         Security · UoW · Events · Exceptions · Dependencies
│   │   ├── domain/       SQLAlchemy models (auth, procurement, inventory, invoice…)
│   │   ├── repositories/ Generic + domain-specific data access
│   │   ├── services/     Business logic (PR, PO, GRN, Invoice 3-way match, Inventory…)
│   │   ├── api/v1/       FastAPI routers (auth, procurement, invoice, inventory, reports)
│   │   ├── schemas/      Pydantic v2 request/response models
│   │   └── tasks/        Celery tasks (email, inventory, reporting)
│   ├── alembic/          Database migrations
│   ├── tests/            Unit + integration test suite
│   └── scripts/seed.py   Bootstrap data
│
├── frontend/             React 18 · TypeScript · Vite · Zustand · React Query
│   └── src/
│       ├── api/          Typed API client (axios)
│       ├── components/   UI primitives + layout shell
│       ├── pages/        Page components per domain
│       ├── store/        Zustand auth store
│       └── types/        Shared TypeScript types
│
├── docker-compose.yml    Full stack (Postgres · Redis · MinIO · API · Worker · Frontend)
└── .github/workflows/    CI/CD (test → build → push to GHCR)
```

## Core Procurement Lifecycle

```
PR (Draft) → Submit → [Approval Workflow] → Approved
  → PO Created → Released → [Email to Vendor]
    → GRN Posted → [Stock: MovementType 101]
      → Invoice Created → 3-Way Match
        → MATCHED/WITHIN_TOLERANCE → Approved → Paid
        → FAILED → DISPUTED → Override (Finance)
```

## Key Technical Decisions

| Decision | Choice | Why |
|---|---|---|
| Async runtime | asyncio + asyncpg | Non-blocking DB; handles 200+ concurrent PR submissions |
| ORM strategy | SQLAlchemy 2.0 mapped_column | Full type safety, async-native |
| Session management | Unit of Work | Atomic cross-domain operations (GRN → Stock → PO status) |
| Event bus | Custom async pub/sub | Decouples notifications from business logic |
| Auth | JWT HS256 + Redis blacklist | Stateless tokens with instant revocation |
| Number generation | PostgreSQL sequences | Guaranteed uniqueness without table locks |
| Task queue | Celery + Redis | Email dispatch, scheduled stock checks, report exports |
| Frontend state | Zustand (auth) + React Query (server) | Minimal client state; server cache as source of truth |

## Quick Start

```bash
# 1. Start all services
docker-compose up -d

# 2. Run migrations
docker-compose exec api alembic upgrade head

# 3. Seed initial data
docker-compose exec api python -m scripts.seed

# 4. Access
#   API docs:  http://localhost:8000/docs
#   Frontend:  http://localhost:80
#   Flower:    http://localhost:5555
#   MinIO:     http://localhost:9001

# Login credentials (from seed)
#   admin@epims.local / Admin@12345
```

## Running Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/unit/ -v                # No DB required
pytest tests/integration/ -v        # Requires Postgres
```

## Environment Variables (Backend)

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | `development` / `production` |
| `DATABASE_URL` | — | `postgresql+asyncpg://...` |
| `REDIS_URL` | — | `redis://...` |
| `SECRET_KEY` | — | Min 32 chars, random |
| `ALLOWED_ORIGINS` | `["*"]` | CORS origins JSON array |
| `SENTRY_DSN` | — | Optional error tracking |

## RBAC Roles

| Role | Capabilities |
|---|---|
| `superuser` | Full system access |
| `procurement_manager` | PR + PO create/approve, reports |
| `buyer` | PR/PO create and update |
| `approver` | Approve PRs and release POs |
| `warehouse_manager` | GRN post, inventory management |
| `accounts_payable` | Invoice create, 3-way match, payment |
| `viewer` | Read-only across all modules |

## Pending (Phase 4)

- [ ] Additional frontend pages: PO detail, GRN create, Invoice verification UI
- [ ] Approval queue page for approvers
- [ ] User management admin page
- [ ] Notification drawer in sidebar
- [ ] Integration tests with live Postgres
- [ ] Production deployment guide (Render / Railway / AWS ECS)
