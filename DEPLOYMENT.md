# EPIMS Production Deployment Guide

## Option A — Render (Recommended for fast launch)

### 1. PostgreSQL

1. Create a new **PostgreSQL** service in Render.
2. Copy the **Internal Database URL** — you'll need it as `DATABASE_URL`.
3. Replace `postgresql://` with `postgresql+asyncpg://` for the async URL.
4. Keep the original as `DATABASE_URL_SYNC` (for Alembic migrations).

### 2. Redis (Upstash — free tier works)

1. Create a Redis database at [upstash.com](https://upstash.com).
2. Copy the **Redis URL** → `REDIS_URL`, `CELERY_BROKER`, `CELERY_BACKEND`.

### 3. Backend API (Web Service)

```
Build Command:   pip install -r requirements.txt && alembic upgrade head
Start Command:   uvicorn app.main:app --host 0.0.0.0 --port $PORT
Root Directory:  backend/
Runtime:         Python 3.12
```

**Environment variables:**

| Key | Value |
|-----|-------|
| `APP_ENV` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://...` (from Render DB) |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://...` (same, for migrations) |
| `REDIS_URL` | Redis URL from Upstash |
| `CELERY_BROKER` | Same Redis URL |
| `CELERY_BACKEND` | Same Redis URL |
| `SECRET_KEY` | 64-char random string (generate: `openssl rand -hex 32`) |
| `ALLOWED_ORIGINS` | `["https://your-frontend.onrender.com"]` |
| `SENTRY_DSN` | Optional: your Sentry project DSN |

### 4. Celery Worker (Background Worker)

```
Start Command:   celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
Root Directory:  backend/
```
Use the same environment variables as the API service.

### 5. Frontend (Static Site)

```
Build Command:   npm ci && npm run build
Publish Dir:     dist/
Root Directory:  frontend/
```

**Environment variable:**
```
VITE_API_URL=/api/v1
```

---

## Option B — Railway

### Deploy with Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli && railway login

# From project root
railway init
railway up

# Add services
railway add --database postgresql
railway add --database redis
```

Railway auto-detects Dockerfile. Set environment variables in the Railway dashboard.

### railway.toml (in project root)

```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
```

---

## Option C — AWS ECS (Production-Grade)

### Architecture

```
Route 53 → ALB → ECS Fargate (API × 2 tasks)
                → ECS Fargate (Celery Worker × 1)
           → CloudFront → S3 (Frontend static)
           → RDS PostgreSQL 16 (Multi-AZ)
           → ElastiCache Redis 7
           → S3 (exports bucket)
```

### ECS Task Definition (API)

```json
{
  "family": "epims-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "api",
    "image": "ghcr.io/YOUR_ORG/epims-api:latest",
    "portMappings": [{"containerPort": 8000}],
    "environment": [
      {"name": "APP_ENV", "value": "production"}
    ],
    "secrets": [
      {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."},
      {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
    ],
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3
    },
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/epims",
        "awslogs-region": "ap-south-1",
        "awslogs-stream-prefix": "api"
      }
    }
  }]
}
```

### Terraform snippet (RDS + ElastiCache)

```hcl
resource "aws_db_instance" "epims" {
  identifier        = "epims-production"
  engine            = "postgres"
  engine_version    = "16.1"
  instance_class    = "db.t3.medium"
  allocated_storage = 100
  storage_encrypted = true
  multi_az          = true
  db_name           = "epims"
  username          = "epims"
  password          = var.db_password
  skip_final_snapshot = false
}

resource "aws_elasticache_cluster" "epims" {
  cluster_id      = "epims-redis"
  engine          = "redis"
  node_type       = "cache.t3.micro"
  num_cache_nodes = 1
  engine_version  = "7.0"
  port            = 6379
}
```

---

## Post-Deployment Checklist

```bash
# 1. Run migrations
alembic upgrade head

# 2. Seed initial data (first deploy only)
python -m scripts.seed

# 3. Verify health
curl https://your-api.domain.com/health

# 4. Verify API docs (dev/staging only)
open https://your-api.domain.com/docs

# 5. Verify frontend
open https://your-frontend.domain.com
# Login: admin@epims.local / Admin@12345
# CHANGE DEFAULT PASSWORD IMMEDIATELY IN PRODUCTION

# 6. Test Celery
docker-compose exec worker celery -A app.tasks.celery_app inspect ping
```

---

## Security Hardening (Production)

```bash
# 1. Rotate SECRET_KEY (invalidates all existing tokens — log all users out)
openssl rand -hex 32

# 2. Change default admin password
#    Settings → Change Password in the UI

# 3. Restrict ALLOWED_ORIGINS to exact frontend domain
ALLOWED_ORIGINS='["https://epims.yourcompany.com"]'

# 4. Enable Sentry
SENTRY_DSN=https://xxx@sentry.io/yyy

# 5. Set up database backups (Render: automatic; AWS: RDS automated snapshots)

# 6. Configure SMTP for real email dispatch (update email_tasks.py)
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@mg.yourcompany.com
SMTP_PASSWORD=your-mailgun-key
```

---

## Monitoring

| Tool | Purpose | Setup |
|------|---------|-------|
| Sentry | Error tracking | Set `SENTRY_DSN` env var |
| Flower | Celery task monitor | `http://your-domain:5555` |
| Prometheus | Metrics | Expose `/metrics` via `prometheus-fastapi-instrumentator` |
| Grafana | Dashboards | Connect to Prometheus |
| Uptime Robot | Availability | Ping `/health` every 5 min |

---

## Scaling

| Component | Scale strategy |
|-----------|---------------|
| API | Increase ECS tasks (stateless) |
| Celery workers | Increase concurrency (`--concurrency=8`) or worker count |
| Database | RDS read replicas for reporting queries |
| Redis | ElastiCache cluster mode |
| Frontend | CloudFront CDN (already static, inherently scalable) |
