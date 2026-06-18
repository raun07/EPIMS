# EPIMS — Enterprise Procurement & Inventory Management System

> A production-grade SAP MM-equivalent built with Python, React, and AI — from scratch.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green) ![React](https://img.shields.io/badge/React-18-blue) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue) ![Docker](https://img.shields.io/badge/Docker-Compose-blue)

## What is EPIMS?

Large enterprises run procurement on SAP — a system that costs crores to license. EPIMS replicates the core SAP MM (Materials Management) workflows using modern open-source technology, with an AI Copilot layer on top.

## Core Modules

### Procurement (SAP MM equivalent)
- **Purchase Requisition (ME51N)** — Create, submit, approve PRs with multi-level workflow
- **Purchase Order (ME21N)** — Convert approved PRs to POs, release to vendors
- **Goods Receipt (MIGO)** — Post GRNs against POs, update inventory
- **3-Way Invoice Match (MIRO)** — Automatic PO × GRN × Invoice verification with tolerance

### Inventory Management (SAP WM equivalent)
- Material master with UOM, reorder points, valuation
- Warehouse and storage location management
- Stock movements with SAP movement type codes (101, 201, 261...)
- Low stock alerts

### Finance (SAP FI equivalent)
- Invoice verification and approval
- Payment processing
- Invoice aging dashboard

### Vendor Master (SAP MM Vendor)
- Complete vendor master with GST, PAN, bank details
- Vendor rating and performance tracking
- Approved vendor list management

### AI Procurement Copilot
- **NL → PR**: "Need 25 Dell laptops for new engineering batch" → structured Purchase Requisition
- **Vendor Recommendations**: AI scores vendors on price, delivery, quality from historical PO data
- **Policy Compliance**: Pre-submission check against 10 procurement policy rules
- **Approval Summary**: Auto-generated executive summary for approvers
- **Analytics Assistant**: "Which vendors caused the most delays?" → validated SQL → chart
- **Document Intelligence**: PDF invoice → extracted line items → pre-filled invoice record

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI 0.111, Python 3.12, Pydantic v2 |
| ORM | SQLAlchemy 2.0 async, asyncpg |
| Database | PostgreSQL 16 |
| Cache / Queue | Redis 7, Celery 5 |
| AI | Anthropic Claude (claude-sonnet-4-6) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| State | Zustand, React Query |
| Auth | JWT HS256 + Redis blacklist |
| Storage | MinIO (S3-compatible) |
| Infra | Docker Compose, Nginx, GitHub Actions CI |

## Architecture Highlights

- **Unit of Work + Repository pattern** — clean separation of domain, service, and data layers
- **Async throughout** — FastAPI + asyncpg + async SQLAlchemy, no sync blocking
- **State machines** — PR/PO/GRN/Invoice each have enforced status transitions
- **RBAC** — Role-based access: SUPERUSER, MM_MANAGER, BUYER, FINANCE, WAREHOUSE, APPROVER
- **Audit trail** — Every state change logged with actor, timestamp, old/new values
- **AI safety** — SQL whitelist guard, Pydantic output validation, cost tracking, eval framework

## SAP Terminology Mapping

| EPIMS | SAP Equivalent |
|-------|---------------|
| Purchase Requisition | ME51N / ME52N / ME53N |
| Purchase Order | ME21N / ME22N / ME23N |
| Goods Receipt | MIGO (Movement Type 101) |
| 3-Way Match | MIRO Invoice Verification |
| Material Master | MM01 / MM02 / MM03 |
| Vendor Master | XK01 / XK02 / XK03 |
| Approval Workflow | SAP Release Strategy |
| Cost Centre | CO Cost Centre |
| Movement Types | SAP MM Movement Types |

## Quick Start

```bash
# Clone
git clone https://github.com/raun07/EPIMS.git
cd EPIMS

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — set ANTHROPIC_API_KEY for AI features (optional)

# Start all services
docker compose up --build -d

# Run migrations
docker compose exec api alembic upgrade head

# Access
# Frontend: http://localhost
# API Docs: http://localhost:8000/docs
# Login: admin@epims.com / Admin@123456
```

## Demo Credentials

| Role | Email | Password |
|------|-------|----------|
| System Admin | admin@epims.com | Admin@123456 |
| Procurement Buyer | buyer@epims.com | Buyer@123456 |
| Finance Manager | finance@epims.com | Finance@123456 |
| Warehouse Staff | warehouse@epims.com | Warehouse@123456 |
| MM Manager | manager@epims.com | Manager@123456 |

## Project Structure
epims/

├── backend/

│   ├── app/

│   │   ├── ai/              # AI Copilot — 6 agents, prompts, schemas, SQL validator

│   │   ├── api/v1/          # FastAPI routers — 8 modules + AI

│   │   ├── core/            # UoW, auth, events, exceptions

│   │   ├── domain/          # SQLAlchemy models — 10 domains, 41 tables

│   │   ├── repositories/    # Data access layer

│   │   └── services/        # Business logic — state machines, 3-way match

│   └── alembic/             # Database migrations

├── frontend/

│   └── src/

│       ├── pages/           # 20+ pages including 3 AI pages

│       ├── components/      # Reusable UI + AI components

│       └── api/             # Typed API clients

└── docker-compose.yml

## Built By

**Vaibhav Kumar** — CSE Graduate, Sir M Visvesvaraya Institute of Technology, Bengaluru


