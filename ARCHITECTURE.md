# Enterprise Procurement & Inventory Management System (EPIMS)
> Inspired by SAP MM · FastAPI · PostgreSQL · React + TypeScript · Production-Grade

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Folder Structure](#folder-structure)
4. [Database Schema](#database-schema)
5. [Module Breakdown](#module-breakdown)
6. [API Design Conventions](#api-design-conventions)
7. [RBAC Matrix](#rbac-matrix)
8. [Implementation Roadmap](#implementation-roadmap)

---

## 1. System Overview

EPIMS covers the full procure-to-pay (P2P) cycle:

```
Requisition → Approval → RFQ/Vendor → Purchase Order
     → Goods Receipt → Invoice Verification (3-way match) → Payment
```

Secondary: Inventory Management, Warehouse Management, Reporting, Notifications, Audit.

### Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Zustand, React Query, React Hook Form, Shadcn/UI, Tailwind CSS |
| API Gateway | FastAPI 0.111, Python 3.12, Pydantic v2, Uvicorn |
| Auth | JWT (HS256/RS256), python-jose, passlib[bcrypt] |
| ORM | SQLAlchemy 2.0 (async), asyncpg |
| Migrations | Alembic |
| Cache | Redis 7 (aioredis) |
| Background Jobs | Celery 5 + Redis broker + Flower monitoring |
| Database | PostgreSQL 16 |
| Object Storage | MinIO (S3-compatible) |
| Containerization | Docker, Docker Compose, Nginx |
| CI/CD | GitHub Actions |
| Testing | pytest, pytest-asyncio, factory-boy, httpx |
| Observability | Prometheus, Grafana, Sentry |

---

## 2. Architecture Principles

### Clean Architecture Layers
```
┌─────────────────────────────────────────────────────┐
│  Presentation (FastAPI Routers / React Components)  │
├─────────────────────────────────────────────────────┤
│  Application (Service Layer — orchestrates use-cases│
├─────────────────────────────────────────────────────┤
│  Domain (Models, Entities, Business Rules)          │
├─────────────────────────────────────────────────────┤
│  Infrastructure (Repos, DB, Cache, Email, Storage)  │
└─────────────────────────────────────────────────────┘
```

### Key Patterns Used
- **Repository Pattern** — one abstract repo per aggregate root, concrete implementations injected
- **Service Layer Pattern** — all business logic lives in services, never in routers
- **Unit of Work Pattern** — wraps database sessions and ensures transactional integrity
- **CQRS-lite** — separate query objects for complex reads (reports) vs. command-style writes
- **Domain Events** — services emit events picked up by the notification and audit services
- **Dependency Injection** — FastAPI `Depends()` wires repos and services; testable with mocks

---

## 3. Folder Structure

```
epims/
├── backend/
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app factory
│   │   ├── config.py                   # Settings (pydantic-settings)
│   │   ├── database.py                 # Async engine + session factory
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── security.py             # JWT encode/decode, password hashing
│   │   │   ├── dependencies.py         # get_db, get_current_user, require_role
│   │   │   ├── exceptions.py           # Custom HTTP exceptions
│   │   │   ├── unit_of_work.py         # UnitOfWork context manager
│   │   │   └── events.py               # Domain event dispatcher
│   │   │
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── auth/
│   │   │   │   ├── models.py           # User, Role, Permission, RolePermission
│   │   │   │   └── enums.py
│   │   │   ├── material/
│   │   │   │   ├── models.py           # Material, MaterialGroup, UOM
│   │   │   │   └── enums.py            # MaterialType, ValuationClass
│   │   │   ├── vendor/
│   │   │   │   ├── models.py           # Vendor, VendorContact, VendorEvaluation
│   │   │   │   └── enums.py
│   │   │   ├── warehouse/
│   │   │   │   ├── models.py           # Warehouse, StorageLocation, Bin
│   │   │   │   └── enums.py
│   │   │   ├── inventory/
│   │   │   │   ├── models.py           # InventoryStock, StockMovement, Reservation
│   │   │   │   └── enums.py            # MovementType (GR, GI, TR, RE)
│   │   │   ├── procurement/
│   │   │   │   ├── models.py           # PR, PRItem, PO, POItem, GRN, GRNItem
│   │   │   │   └── enums.py            # PRStatus, POStatus, GRNStatus
│   │   │   ├── invoice/
│   │   │   │   ├── models.py           # Invoice, InvoiceItem, ThreeWayMatch
│   │   │   │   └── enums.py
│   │   │   ├── approval/
│   │   │   │   ├── models.py           # ApprovalWorkflow, ApprovalStep, Delegation
│   │   │   │   └── enums.py
│   │   │   ├── notification/
│   │   │   │   └── models.py           # Notification, NotificationTemplate
│   │   │   └── audit/
│   │   │       └── models.py           # AuditLog
│   │   │
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # AbstractRepository[T] generic base
│   │   │   ├── auth.py                 # UserRepository, RoleRepository
│   │   │   ├── material.py
│   │   │   ├── vendor.py
│   │   │   ├── warehouse.py
│   │   │   ├── inventory.py
│   │   │   ├── procurement.py          # PRRepository, PORepository, GRNRepository
│   │   │   ├── invoice.py
│   │   │   ├── approval.py
│   │   │   └── audit.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py         # Login, token refresh, RBAC checks
│   │   │   ├── material_service.py
│   │   │   ├── vendor_service.py
│   │   │   ├── warehouse_service.py
│   │   │   ├── inventory_service.py    # Stock movements, reservations, reorder
│   │   │   ├── pr_service.py           # Create/amend/cancel PR, trigger approval
│   │   │   ├── po_service.py           # Create PO from PR, release, close
│   │   │   ├── approval_service.py     # Evaluate rules, advance workflow
│   │   │   ├── grn_service.py          # Post GRN, update stock
│   │   │   ├── invoice_service.py      # Three-way match logic
│   │   │   ├── reporting_service.py    # KPI queries, export
│   │   │   ├── notification_service.py # Dispatch notifications
│   │   │   └── audit_service.py        # Write immutable audit entries
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py           # Include all sub-routers
│   │   │   │   ├── auth.py
│   │   │   │   ├── users.py
│   │   │   │   ├── materials.py
│   │   │   │   ├── vendors.py
│   │   │   │   ├── warehouses.py
│   │   │   │   ├── inventory.py
│   │   │   │   ├── purchase_requisitions.py
│   │   │   │   ├── purchase_orders.py
│   │   │   │   ├── approvals.py
│   │   │   │   ├── goods_receipts.py
│   │   │   │   ├── invoices.py
│   │   │   │   ├── reports.py
│   │   │   │   └── notifications.py
│   │   │   └── deps.py                 # Shared FastAPI dependencies
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                 # Pydantic v2 request/response schemas
│   │   │   ├── material.py
│   │   │   ├── vendor.py
│   │   │   ├── warehouse.py
│   │   │   ├── inventory.py
│   │   │   ├── procurement.py
│   │   │   ├── invoice.py
│   │   │   ├── approval.py
│   │   │   └── reports.py
│   │   │
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py           # Celery factory
│   │   │   ├── email_tasks.py
│   │   │   ├── report_tasks.py
│   │   │   ├── po_tasks.py             # Auto-release POs
│   │   │   └── reorder_tasks.py        # Reorder point alerts
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── cache.py                # Redis helpers
│   │       ├── pagination.py
│   │       ├── filters.py
│   │       └── number_gen.py           # PR/PO/GRN number generation
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── unit/
│   │   │   ├── test_approval_engine.py
│   │   │   ├── test_three_way_match.py
│   │   │   ├── test_inventory_service.py
│   │   │   └── test_pr_service.py
│   │   └── integration/
│   │       ├── test_auth_flow.py
│   │       ├── test_pr_to_po_flow.py
│   │       └── test_invoice_verification.py
│   │
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── alembic.ini
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── router.tsx                  # TanStack Router or React Router v6
│   │   │
│   │   ├── api/
│   │   │   ├── client.ts               # Axios instance + interceptors
│   │   │   ├── auth.ts
│   │   │   ├── materials.ts
│   │   │   ├── vendors.ts
│   │   │   ├── procurement.ts
│   │   │   ├── inventory.ts
│   │   │   └── reports.ts
│   │   │
│   │   ├── store/
│   │   │   ├── authStore.ts            # Zustand auth state
│   │   │   └── uiStore.ts
│   │   │
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useMaterials.ts
│   │   │   ├── useProcurement.ts
│   │   │   └── useInventory.ts
│   │   │
│   │   ├── pages/
│   │   │   ├── auth/
│   │   │   │   └── LoginPage.tsx
│   │   │   ├── dashboard/
│   │   │   │   └── DashboardPage.tsx
│   │   │   ├── materials/
│   │   │   │   ├── MaterialListPage.tsx
│   │   │   │   └── MaterialDetailPage.tsx
│   │   │   ├── vendors/
│   │   │   ├── inventory/
│   │   │   ├── procurement/
│   │   │   │   ├── PRListPage.tsx
│   │   │   │   ├── PRCreatePage.tsx
│   │   │   │   ├── POListPage.tsx
│   │   │   │   └── PODetailPage.tsx
│   │   │   ├── approvals/
│   │   │   │   └── ApprovalQueuePage.tsx
│   │   │   ├── goods-receipt/
│   │   │   ├── invoice/
│   │   │   └── reports/
│   │   │       └── ReportsPage.tsx
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                     # Shadcn/UI base components
│   │   │   ├── layout/
│   │   │   │   ├── AppShell.tsx
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   └── TopBar.tsx
│   │   │   ├── procurement/
│   │   │   │   ├── PRForm.tsx
│   │   │   │   ├── POTable.tsx
│   │   │   │   └── ApprovalTimeline.tsx
│   │   │   ├── inventory/
│   │   │   │   ├── StockCard.tsx
│   │   │   │   └── MovementTable.tsx
│   │   │   └── reports/
│   │   │       ├── KPICard.tsx
│   │   │       └── ProcurementChart.tsx
│   │   │
│   │   └── types/
│   │       ├── auth.ts
│   │       ├── material.ts
│   │       ├── vendor.ts
│   │       ├── procurement.ts
│   │       └── inventory.ts
│   │
│   ├── public/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
│
├── nginx/
│   ├── nginx.conf
│   └── Dockerfile
│
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── docker-compose.prod.yml
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
└── README.md
```

---

## 4. Database Schema

### Core Tables

#### auth_users
```sql
CREATE TABLE auth_users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id VARCHAR(20) UNIQUE NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    full_name   VARCHAR(255) NOT NULL,
    hashed_password TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    department  VARCHAR(100),
    cost_center VARCHAR(20),
    manager_id  UUID REFERENCES auth_users(id),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### auth_roles + auth_permissions (RBAC)
```sql
CREATE TABLE auth_roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(50) UNIQUE NOT NULL,  -- 'admin','buyer','approver','store_keeper','finance'
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE auth_permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource    VARCHAR(100) NOT NULL,  -- 'purchase_orders'
    action      VARCHAR(50) NOT NULL,   -- 'create','read','update','delete','approve'
    UNIQUE(resource, action)
);

CREATE TABLE auth_role_permissions (
    role_id       UUID REFERENCES auth_roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES auth_permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE auth_user_roles (
    user_id UUID REFERENCES auth_users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES auth_roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);
```

#### material_master
```sql
CREATE TABLE material_groups (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(20) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    parent_id   UUID REFERENCES material_groups(id),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE units_of_measure (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(10) UNIQUE NOT NULL,  -- 'EA','KG','LTR','MTR'
    name        VARCHAR(50) NOT NULL,
    base_unit   VARCHAR(10),
    conversion_factor NUMERIC(18,6) DEFAULT 1
);

CREATE TABLE materials (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_number     VARCHAR(30) UNIQUE NOT NULL,   -- Auto-generated: MAT-000001
    description         VARCHAR(255) NOT NULL,
    material_type       VARCHAR(30) NOT NULL,          -- RAW, SEMI_FINISHED, FINISHED, SERVICE, CONSUMABLE
    material_group_id   UUID REFERENCES material_groups(id),
    base_uom_id         UUID REFERENCES units_of_measure(id),
    purchase_uom_id     UUID REFERENCES units_of_measure(id),
    valuation_class     VARCHAR(20),
    standard_price      NUMERIC(18,4),
    moving_average_price NUMERIC(18,4),
    price_unit          NUMERIC(10,3) DEFAULT 1,
    currency            VARCHAR(3) DEFAULT 'INR',
    weight_gross        NUMERIC(10,3),
    weight_net          NUMERIC(10,3),
    weight_unit         VARCHAR(5),
    volume              NUMERIC(10,3),
    volume_unit         VARCHAR(5),
    storage_conditions  VARCHAR(100),
    shelf_life_days     INTEGER,
    reorder_point       NUMERIC(18,3),
    min_order_qty       NUMERIC(18,3),
    max_order_qty       NUMERIC(18,3),
    lead_time_days      INTEGER,
    is_active           BOOLEAN DEFAULT TRUE,
    created_by          UUID REFERENCES auth_users(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

#### vendor_master
```sql
CREATE TABLE vendors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_number   VARCHAR(20) UNIQUE NOT NULL,  -- VEN-000001
    name            VARCHAR(255) NOT NULL,
    short_name      VARCHAR(50),
    vendor_type     VARCHAR(30) NOT NULL,  -- SUPPLIER, SERVICE_PROVIDER, CONTRACTOR
    tax_id          VARCHAR(50),
    gst_number      VARCHAR(20),
    pan_number      VARCHAR(20),
    email           VARCHAR(255),
    phone           VARCHAR(30),
    website         VARCHAR(255),
    payment_terms   VARCHAR(50),  -- 'NET30','NET60','IMMEDIATE'
    payment_method  VARCHAR(30),  -- 'BANK_TRANSFER','CHEQUE','NEFT'
    bank_name       VARCHAR(100),
    bank_account    VARCHAR(50),
    bank_ifsc       VARCHAR(20),
    credit_limit    NUMERIC(18,2),
    currency        VARCHAR(3) DEFAULT 'INR',
    status          VARCHAR(20) DEFAULT 'ACTIVE',  -- ACTIVE, BLOCKED, INACTIVE
    blocked_reason  TEXT,
    rating          NUMERIC(3,2),  -- 0.00–5.00
    created_by      UUID REFERENCES auth_users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE vendor_addresses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id   UUID REFERENCES vendors(id) ON DELETE CASCADE,
    address_type VARCHAR(20),  -- BILLING, SHIPPING, REGISTERED
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    city        VARCHAR(100) NOT NULL,
    state       VARCHAR(100),
    pincode     VARCHAR(10),
    country     VARCHAR(3) DEFAULT 'IND',
    is_default  BOOLEAN DEFAULT FALSE
);

CREATE TABLE vendor_contacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id   UUID REFERENCES vendors(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    designation VARCHAR(100),
    email       VARCHAR(255),
    phone       VARCHAR(30),
    is_primary  BOOLEAN DEFAULT FALSE
);

CREATE TABLE vendor_material_info (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id       UUID REFERENCES vendors(id) ON DELETE CASCADE,
    material_id     UUID REFERENCES materials(id) ON DELETE CASCADE,
    vendor_mat_num  VARCHAR(50),   -- Vendor's own part number
    last_price      NUMERIC(18,4),
    last_currency   VARCHAR(3),
    last_po_date    DATE,
    lead_time_days  INTEGER,
    min_order_qty   NUMERIC(18,3),
    UNIQUE(vendor_id, material_id)
);
```

#### warehouse & storage
```sql
CREATE TABLE warehouses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(10) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    type        VARCHAR(30),  -- MAIN, TRANSIT, COLD_STORAGE, QUARANTINE
    address     TEXT,
    manager_id  UUID REFERENCES auth_users(id),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE storage_locations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    warehouse_id    UUID REFERENCES warehouses(id) ON DELETE CASCADE,
    code            VARCHAR(20) NOT NULL,
    name            VARCHAR(100),
    location_type   VARCHAR(30),  -- RACK, SHELF, BIN, FLOOR
    aisle           VARCHAR(10),
    rack            VARCHAR(10),
    level           VARCHAR(10),
    bin             VARCHAR(10),
    capacity_weight NUMERIC(10,2),
    capacity_volume NUMERIC(10,2),
    is_active       BOOLEAN DEFAULT TRUE,
    UNIQUE(warehouse_id, code)
);
```

#### inventory_stock
```sql
CREATE TABLE inventory_stock (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id         UUID REFERENCES materials(id) ON DELETE RESTRICT,
    warehouse_id        UUID REFERENCES warehouses(id) ON DELETE RESTRICT,
    storage_location_id UUID REFERENCES storage_locations(id),
    batch_number        VARCHAR(50),
    stock_type          VARCHAR(20) DEFAULT 'UNRESTRICTED',  -- UNRESTRICTED, QUALITY_INSPECTION, BLOCKED, RESERVED
    quantity            NUMERIC(18,3) NOT NULL DEFAULT 0,
    uom_id              UUID REFERENCES units_of_measure(id),
    valuation_price     NUMERIC(18,4),
    currency            VARCHAR(3) DEFAULT 'INR',
    last_movement_date  DATE,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(material_id, warehouse_id, storage_location_id, batch_number, stock_type)
);

CREATE TABLE stock_movements (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    movement_number     VARCHAR(30) UNIQUE NOT NULL,  -- MOV-20240101-000001
    movement_type       VARCHAR(30) NOT NULL,  -- GR(101), GI(201), TRANSFER(311), RETURN(122)
    movement_date       DATE NOT NULL,
    material_id         UUID REFERENCES materials(id),
    from_warehouse_id   UUID REFERENCES warehouses(id),
    from_location_id    UUID REFERENCES storage_locations(id),
    to_warehouse_id     UUID REFERENCES warehouses(id),
    to_location_id      UUID REFERENCES storage_locations(id),
    quantity            NUMERIC(18,3) NOT NULL,
    uom_id              UUID REFERENCES units_of_measure(id),
    unit_price          NUMERIC(18,4),
    total_value         NUMERIC(18,2),
    currency            VARCHAR(3) DEFAULT 'INR',
    reference_doc_type  VARCHAR(30),  -- PO, GRN, PR, MANUAL
    reference_doc_id    UUID,
    batch_number        VARCHAR(50),
    reason              TEXT,
    posted_by           UUID REFERENCES auth_users(id),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

#### procurement — PR
```sql
CREATE TABLE purchase_requisitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pr_number       VARCHAR(20) UNIQUE NOT NULL,  -- PR-2024-000001
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(30) DEFAULT 'DRAFT',
    -- DRAFT → SUBMITTED → PENDING_APPROVAL → APPROVED → PO_CREATED → CANCELLED
    priority        VARCHAR(20) DEFAULT 'NORMAL',  -- LOW, NORMAL, HIGH, URGENT
    required_date   DATE,
    cost_center     VARCHAR(20),
    plant           VARCHAR(20),
    warehouse_id    UUID REFERENCES warehouses(id),
    requested_by    UUID REFERENCES auth_users(id) NOT NULL,
    department      VARCHAR(100),
    total_value     NUMERIC(18,2) DEFAULT 0,
    currency        VARCHAR(3) DEFAULT 'INR',
    notes           TEXT,
    rejection_reason TEXT,
    submitted_at    TIMESTAMPTZ,
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pr_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pr_id               UUID REFERENCES purchase_requisitions(id) ON DELETE CASCADE,
    line_number         INTEGER NOT NULL,
    material_id         UUID REFERENCES materials(id),
    description         VARCHAR(255) NOT NULL,  -- for service items
    quantity            NUMERIC(18,3) NOT NULL,
    uom_id              UUID REFERENCES units_of_measure(id),
    estimated_price     NUMERIC(18,4),
    estimated_value     NUMERIC(18,2),
    currency            VARCHAR(3) DEFAULT 'INR',
    required_date       DATE,
    preferred_vendor_id UUID REFERENCES vendors(id),
    delivery_address    TEXT,
    specifications      TEXT,
    status              VARCHAR(20) DEFAULT 'OPEN',  -- OPEN, PO_CREATED, CANCELLED
    UNIQUE(pr_id, line_number)
);
```

#### procurement — PO
```sql
CREATE TABLE purchase_orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_number       VARCHAR(20) UNIQUE NOT NULL,  -- PO-2024-000001
    pr_id           UUID REFERENCES purchase_requisitions(id),
    vendor_id       UUID REFERENCES vendors(id) NOT NULL,
    status          VARCHAR(30) DEFAULT 'DRAFT',
    -- DRAFT → RELEASED → SENT → PARTIALLY_RECEIVED → RECEIVED → INVOICED → CLOSED → CANCELLED
    po_type         VARCHAR(20) DEFAULT 'STANDARD',  -- STANDARD, BLANKET, FRAMEWORK
    order_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    delivery_date   DATE,
    payment_terms   VARCHAR(50),
    incoterms       VARCHAR(20),
    delivery_address TEXT,
    warehouse_id    UUID REFERENCES warehouses(id),
    currency        VARCHAR(3) DEFAULT 'INR',
    subtotal        NUMERIC(18,2) DEFAULT 0,
    tax_amount      NUMERIC(18,2) DEFAULT 0,
    discount_amount NUMERIC(18,2) DEFAULT 0,
    total_amount    NUMERIC(18,2) DEFAULT 0,
    amount_received NUMERIC(18,2) DEFAULT 0,
    amount_invoiced NUMERIC(18,2) DEFAULT 0,
    notes           TEXT,
    internal_notes  TEXT,
    created_by      UUID REFERENCES auth_users(id),
    approved_by     UUID REFERENCES auth_users(id),
    released_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE po_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_id           UUID REFERENCES purchase_orders(id) ON DELETE CASCADE,
    pr_item_id      UUID REFERENCES pr_items(id),
    line_number     INTEGER NOT NULL,
    material_id     UUID REFERENCES materials(id),
    description     VARCHAR(255) NOT NULL,
    quantity        NUMERIC(18,3) NOT NULL,
    uom_id          UUID REFERENCES units_of_measure(id),
    unit_price      NUMERIC(18,4) NOT NULL,
    discount_pct    NUMERIC(5,2) DEFAULT 0,
    tax_pct         NUMERIC(5,2) DEFAULT 0,
    net_value       NUMERIC(18,2) NOT NULL,
    delivery_date   DATE,
    qty_received    NUMERIC(18,3) DEFAULT 0,
    qty_invoiced    NUMERIC(18,3) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'OPEN',
    UNIQUE(po_id, line_number)
);
```

#### procurement — GRN
```sql
CREATE TABLE goods_receipts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_number      VARCHAR(20) UNIQUE NOT NULL,  -- GRN-2024-000001
    po_id           UUID REFERENCES purchase_orders(id) NOT NULL,
    vendor_id       UUID REFERENCES vendors(id),
    warehouse_id    UUID REFERENCES warehouses(id) NOT NULL,
    status          VARCHAR(20) DEFAULT 'DRAFT',
    -- DRAFT → POSTED → REVERSED
    receipt_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    delivery_note   VARCHAR(100),
    vehicle_number  VARCHAR(30),
    driver_name     VARCHAR(100),
    total_value     NUMERIC(18,2) DEFAULT 0,
    currency        VARCHAR(3) DEFAULT 'INR',
    notes           TEXT,
    posted_by       UUID REFERENCES auth_users(id),
    posted_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE grn_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_id              UUID REFERENCES goods_receipts(id) ON DELETE CASCADE,
    po_item_id          UUID REFERENCES po_items(id),
    line_number         INTEGER NOT NULL,
    material_id         UUID REFERENCES materials(id),
    quantity_delivered  NUMERIC(18,3) NOT NULL,
    quantity_accepted   NUMERIC(18,3) NOT NULL,
    quantity_rejected   NUMERIC(18,3) DEFAULT 0,
    uom_id              UUID REFERENCES units_of_measure(id),
    unit_price          NUMERIC(18,4),
    net_value           NUMERIC(18,2),
    storage_location_id UUID REFERENCES storage_locations(id),
    batch_number        VARCHAR(50),
    expiry_date         DATE,
    inspection_note     TEXT,
    rejection_reason    TEXT,
    UNIQUE(grn_id, line_number)
);
```

#### invoice verification
```sql
CREATE TABLE invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number  VARCHAR(50) UNIQUE NOT NULL,  -- EPIMS internal: INV-2024-000001
    vendor_invoice_number VARCHAR(100),           -- Vendor's own invoice #
    vendor_id       UUID REFERENCES vendors(id) NOT NULL,
    po_id           UUID REFERENCES purchase_orders(id),
    status          VARCHAR(30) DEFAULT 'PENDING_VERIFICATION',
    -- PENDING_VERIFICATION → MATCHED → PARTIALLY_MATCHED → DISPUTED → APPROVED → PAID → CANCELLED
    invoice_date    DATE NOT NULL,
    due_date        DATE,
    currency        VARCHAR(3) DEFAULT 'INR',
    subtotal        NUMERIC(18,2) NOT NULL,
    tax_amount      NUMERIC(18,2) DEFAULT 0,
    total_amount    NUMERIC(18,2) NOT NULL,
    paid_amount     NUMERIC(18,2) DEFAULT 0,
    match_status    VARCHAR(20),  -- TWO_WAY, THREE_WAY, FAILED
    tolerance_pct   NUMERIC(5,2) DEFAULT 2,  -- Tolerance for 3-way match
    dispute_reason  TEXT,
    notes           TEXT,
    created_by      UUID REFERENCES auth_users(id),
    verified_by     UUID REFERENCES auth_users(id),
    verified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE invoice_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id      UUID REFERENCES invoices(id) ON DELETE CASCADE,
    po_item_id      UUID REFERENCES po_items(id),
    grn_item_id     UUID REFERENCES grn_items(id),
    line_number     INTEGER NOT NULL,
    material_id     UUID REFERENCES materials(id),
    description     VARCHAR(255),
    quantity        NUMERIC(18,3) NOT NULL,
    unit_price      NUMERIC(18,4) NOT NULL,
    net_value       NUMERIC(18,2) NOT NULL,
    match_flag      VARCHAR(20),   -- MATCHED, PRICE_VARIANCE, QTY_VARIANCE, UNMATCHED
    variance_pct    NUMERIC(8,4)
);

CREATE TABLE three_way_match_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id      UUID REFERENCES invoices(id),
    po_id           UUID REFERENCES purchase_orders(id),
    grn_id          UUID REFERENCES goods_receipts(id),
    match_result    VARCHAR(20),  -- PASSED, FAILED, WITHIN_TOLERANCE
    price_variance  NUMERIC(18,4),
    qty_variance    NUMERIC(18,3),
    value_variance  NUMERIC(18,2),
    tolerance_pct   NUMERIC(5,2),
    notes           TEXT,
    checked_by      UUID REFERENCES auth_users(id),
    checked_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### approval engine
```sql
CREATE TABLE approval_workflows (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) UNIQUE NOT NULL,
    document_type VARCHAR(30) NOT NULL,  -- PR, PO, INVOICE
    is_active   BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE approval_rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id         UUID REFERENCES approval_workflows(id),
    step_order          INTEGER NOT NULL,
    approver_type       VARCHAR(30) NOT NULL,  -- USER, ROLE, MANAGER, DEPARTMENT_HEAD
    approver_id         UUID,   -- specific user if approver_type=USER
    approver_role       VARCHAR(50), -- if approver_type=ROLE
    min_amount          NUMERIC(18,2),
    max_amount          NUMERIC(18,2),
    department          VARCHAR(100),
    is_mandatory        BOOLEAN DEFAULT TRUE,
    timeout_hours       INTEGER DEFAULT 48,  -- Auto-escalate
    escalate_to_id      UUID REFERENCES auth_users(id),
    UNIQUE(workflow_id, step_order)
);

CREATE TABLE approval_instances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID REFERENCES approval_workflows(id),
    document_type   VARCHAR(30) NOT NULL,
    document_id     UUID NOT NULL,
    current_step    INTEGER DEFAULT 1,
    status          VARCHAR(20) DEFAULT 'PENDING',
    -- PENDING → IN_PROGRESS → APPROVED → REJECTED → CANCELLED
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE approval_actions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id     UUID REFERENCES approval_instances(id) ON DELETE CASCADE,
    rule_id         UUID REFERENCES approval_rules(id),
    step_order      INTEGER NOT NULL,
    approver_id     UUID REFERENCES auth_users(id),
    action          VARCHAR(20),  -- APPROVED, REJECTED, DELEGATED, RETURNED
    comments        TEXT,
    delegated_to_id UUID REFERENCES auth_users(id),
    acted_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE approval_delegations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delegator_id    UUID REFERENCES auth_users(id),
    delegate_id     UUID REFERENCES auth_users(id),
    document_type   VARCHAR(30),  -- NULL = all types
    valid_from      DATE NOT NULL,
    valid_to        DATE NOT NULL,
    reason          TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### notifications & audit
```sql
CREATE TABLE notification_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type  VARCHAR(100) UNIQUE NOT NULL,  -- 'PR_SUBMITTED','PO_RELEASED' etc
    channel     VARCHAR(20) NOT NULL,  -- EMAIL, IN_APP, WEBHOOK
    subject     VARCHAR(255),
    body_html   TEXT,
    body_text   TEXT,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id    UUID REFERENCES auth_users(id) ON DELETE CASCADE,
    event_type      VARCHAR(100) NOT NULL,
    title           VARCHAR(255) NOT NULL,
    message         TEXT,
    channel         VARCHAR(20) DEFAULT 'IN_APP',
    reference_type  VARCHAR(30),  -- PR, PO, GRN, INVOICE
    reference_id    UUID,
    is_read         BOOLEAN DEFAULT FALSE,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     VARCHAR(50) NOT NULL,  -- 'PurchaseOrder','Material' etc
    entity_id       UUID NOT NULL,
    action          VARCHAR(30) NOT NULL,  -- CREATE, UPDATE, DELETE, STATUS_CHANGE
    old_values      JSONB,
    new_values      JSONB,
    changed_fields  TEXT[],
    performed_by    UUID REFERENCES auth_users(id),
    performed_at    TIMESTAMPTZ DEFAULT NOW(),
    ip_address      VARCHAR(45),
    user_agent      TEXT
);

-- Partial index for fast per-entity audit queries
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id, performed_at DESC);
CREATE INDEX idx_audit_user ON audit_logs(performed_by, performed_at DESC);
```

### Key Indexes
```sql
-- Materials
CREATE INDEX idx_materials_number ON materials(material_number);
CREATE INDEX idx_materials_group ON materials(material_group_id);
CREATE INDEX idx_materials_active ON materials(is_active) WHERE is_active = TRUE;

-- Inventory
CREATE INDEX idx_stock_material ON inventory_stock(material_id);
CREATE INDEX idx_stock_warehouse ON inventory_stock(warehouse_id);
CREATE INDEX idx_movements_date ON stock_movements(movement_date DESC);
CREATE INDEX idx_movements_material ON stock_movements(material_id, movement_date DESC);

-- Procurement
CREATE INDEX idx_pr_status ON purchase_requisitions(status);
CREATE INDEX idx_pr_requester ON purchase_requisitions(requested_by);
CREATE INDEX idx_po_vendor ON purchase_orders(vendor_id, status);
CREATE INDEX idx_po_status ON purchase_orders(status);
CREATE INDEX idx_grn_po ON goods_receipts(po_id);

-- Approvals
CREATE INDEX idx_approval_instance ON approval_instances(document_type, document_id);
CREATE INDEX idx_approval_status ON approval_instances(status);

-- Notifications
CREATE INDEX idx_notif_recipient ON notifications(recipient_id, is_read, created_at DESC);
```

---

## 5. Module Breakdown

### Module 1: Authentication & Authorization
- JWT access token (15 min) + refresh token (7 days, rotated)
- Bcrypt password hashing
- RBAC: permission checked via `require_permission("purchase_orders", "approve")`
- Redis session blacklist for logout/revoke
- Audit every login/logout event

### Module 2: Material Master
- Material number auto-generation (`MAT-YYYYMM-NNNNNN`)
- Material groups with hierarchical categorization
- Multiple UOMs with conversion factors
- Valuation classes for accounting integration
- Bulk import via CSV

### Module 3: Vendor Master
- Vendor number auto-generation (`VEN-NNNNNN`)
- Block/unblock vendors with reason
- Vendor-material info record (last price, lead time)
- Vendor evaluation score (quality, delivery, price)

### Module 4: Warehouse Management
- Multi-warehouse, multi-location support
- Bin location management (Aisle/Rack/Level/Bin)
- Warehouse types: Main, Cold Storage, Quarantine, Transit

### Module 5: Inventory Management
- Stock types: Unrestricted, QI (quality inspection), Blocked, Reserved
- Movement types mirror SAP: 101 (GR vs PO), 122 (GR return), 201 (GI), 311 (transfer)
- Automatic reorder point monitoring (Celery beat)
- Stock valuation: Standard Price and Moving Average Price

### Module 6: Purchase Requisition Workflow
- PR with line items, required date, cost center
- Status machine: DRAFT → SUBMITTED → PENDING_APPROVAL → APPROVED → PO_CREATED
- PR amendment with version tracking

### Module 7: Purchase Order
- PO created from approved PR (or standalone)
- PO types: Standard, Blanket, Framework Agreement
- Line-level delivery tracking
- PO amendment creates new version

### Module 8: Dynamic Approval Engine
- Configurable workflows per document type
- Rules: amount range, department, material group
- Multi-level sequential approval
- Timeout and auto-escalation
- Delegation: delegate approvals with date range

### Module 9: Goods Receipt Processing
- GRN tied to PO
- Over-delivery and under-delivery tolerance
- Quality inspection integration (Accept / Reject quantity)
- Auto-update inventory stock on GRN posting
- GRN reversal support

### Module 10: Invoice Verification (3-Way Match)
- Compare: Invoice vs PO vs GRN (quantity and price)
- Configurable tolerance (default 2%)
- Match results: MATCHED, WITHIN_TOLERANCE, FAILED
- Failed match → dispute workflow

### Module 11: Reporting & Analytics
- KPIs: Spend by vendor, by department, by material group
- PO cycle time, approval cycle time
- Stock turnover, slow-moving inventory
- Open POs, overdue GRNs
- Export to Excel/CSV/PDF

### Module 12: Notification System
- Celery tasks send notifications on state changes
- Templates per event type
- Channels: Email (SMTP), In-app (polling/WebSocket)
- Per-user notification preferences

### Module 13: Audit Logging
- Every write operation captured (entity, field, old/new value)
- Immutable — no UPDATE/DELETE on audit_logs
- User, timestamp, IP captured automatically via middleware

---

## 6. API Design Conventions

```
Base URL: /api/v1

Auth:
  POST   /auth/login
  POST   /auth/refresh
  POST   /auth/logout
  GET    /auth/me

Materials:
  GET    /materials                  (list + filter + search)
  POST   /materials
  GET    /materials/{id}
  PUT    /materials/{id}
  DELETE /materials/{id}
  POST   /materials/import           (CSV bulk import)

Purchase Requisitions:
  GET    /purchase-requisitions
  POST   /purchase-requisitions
  GET    /purchase-requisitions/{id}
  PUT    /purchase-requisitions/{id}
  POST   /purchase-requisitions/{id}/submit
  POST   /purchase-requisitions/{id}/cancel

Approvals:
  GET    /approvals/queue             (current user's pending approvals)
  POST   /approvals/{instance_id}/approve
  POST   /approvals/{instance_id}/reject
  POST   /approvals/{instance_id}/delegate

Purchase Orders:
  GET    /purchase-orders
  POST   /purchase-orders
  GET    /purchase-orders/{id}
  PUT    /purchase-orders/{id}
  POST   /purchase-orders/{id}/release
  POST   /purchase-orders/{id}/cancel

Goods Receipts:
  GET    /goods-receipts
  POST   /goods-receipts
  GET    /goods-receipts/{id}
  POST   /goods-receipts/{id}/post
  POST   /goods-receipts/{id}/reverse

Invoices:
  GET    /invoices
  POST   /invoices
  GET    /invoices/{id}
  POST   /invoices/{id}/verify        (trigger 3-way match)
  POST   /invoices/{id}/approve
  POST   /invoices/{id}/dispute

Reports:
  GET    /reports/spend-analysis
  GET    /reports/open-orders
  GET    /reports/inventory-valuation
  GET    /reports/vendor-performance
  POST   /reports/export              (async → Celery → file ready notification)
```

Response envelope:
```json
{
  "success": true,
  "data": { ... },
  "meta": { "page": 1, "per_page": 20, "total": 150 },
  "message": null
}
```

---

## 7. RBAC Matrix

| Permission / Role | Admin | Procurement Manager | Buyer | Approver | Store Keeper | Finance | Viewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Manage users | ✓ | | | | | | |
| Material master (write) | ✓ | ✓ | | | ✓ | | |
| Vendor master (write) | ✓ | ✓ | | | | | |
| Create PR | ✓ | ✓ | ✓ | | | | |
| Approve PR | ✓ | ✓ | | ✓ | | | |
| Create PO | ✓ | ✓ | ✓ | | | | |
| Release PO | ✓ | ✓ | | ✓ | | | |
| Post GRN | ✓ | | | | ✓ | | |
| Create Invoice | ✓ | | | | | ✓ | |
| Approve Invoice | ✓ | ✓ | | ✓ | | ✓ | |
| View Reports | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Configure Workflows | ✓ | ✓ | | | | | |
| View Audit Log | ✓ | | | | | | |

---

## 8. Implementation Roadmap

### Phase 1 — Foundation (Week 1–2)
- [ ] Docker Compose: postgres, redis, backend, celery, flower, nginx, frontend
- [ ] FastAPI app factory + config (pydantic-settings)
- [ ] Alembic: migration 001 — auth schema
- [ ] SQLAlchemy async models: User, Role, Permission
- [ ] JWT auth: login, refresh, logout, me
- [ ] RBAC middleware: `require_permission()` dependency
- [ ] Base Repository + Unit of Work
- [ ] Audit middleware (auto-captures every write)
- [ ] Number generation service (PR, PO, GRN)
- [ ] Health check endpoints

### Phase 2 — Master Data (Week 3)
- [ ] Material Master: models, repo, service, API, schemas
- [ ] Material Groups + UOM
- [ ] Vendor Master: models, repo, service, API
- [ ] Warehouse + Storage Location: models, repo, API
- [ ] Redis cache layer (material/vendor reads)
- [ ] CSV bulk import for materials

### Phase 3 — Inventory (Week 4)
- [ ] Inventory stock model + stock movement model
- [ ] Stock movement engine (debit/credit logic)
- [ ] Inventory service: receive, issue, transfer, reserve
- [ ] Reorder point monitoring (Celery beat task)
- [ ] Inventory API endpoints + schemas

### Phase 4 — Procurement Core (Week 5–6)
- [ ] PR: model, repo, service, API (full status machine)
- [ ] PO: model, repo, service, API
- [ ] PR → PO conversion logic
- [ ] Approval Engine: workflow config, rules, instance runner
- [ ] Delegation support
- [ ] Celery task: approval timeout + escalation
- [ ] Notification service + templates

### Phase 5 — Procure to Pay (Week 7)
- [ ] GRN: model, repo, service, API
- [ ] GRN posting → stock movement (auto)
- [ ] Invoice: model, repo, service, API
- [ ] 3-way match engine (price + qty tolerance)
- [ ] Invoice dispute workflow

### Phase 6 — Reporting (Week 8)
- [ ] Reporting service: spend, open POs, vendor perf, inventory
- [ ] Async export (Celery → file → notify)
- [ ] Recharts-based dashboard
- [ ] KPI cards with drill-down

### Phase 7 — Frontend (Week 9–10)
- [ ] App shell: sidebar, topbar, breadcrumbs
- [ ] Auth pages: login, password reset
- [ ] Dashboard with KPI cards and charts
- [ ] Material, Vendor CRUD screens
- [ ] PR create/list/detail with workflow timeline
- [ ] PO screens
- [ ] Approval queue page
- [ ] GRN form
- [ ] Invoice verification screen with 3-way match UI
- [ ] Inventory stock view
- [ ] Reports page

### Phase 8 — Hardening (Week 11)
- [ ] Unit tests: approval engine, 3-way match, inventory service
- [ ] Integration tests: full PR→PO→GRN→Invoice flow
- [ ] GitHub Actions CI pipeline
- [ ] Prometheus metrics + Grafana dashboards
- [ ] Nginx config (rate limiting, SSL termination)
- [ ] Production docker-compose with secrets management

---

*Next: Phase 2 — Backend Implementation begins with `backend/app/main.py`, `database.py`, `core/security.py`, and migration 001.*
