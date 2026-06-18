# AI Procurement Copilot — Architecture Design

## Overview

The AI Copilot is NOT a chatbot bolted on top of EPIMS. It is a set of **six deeply
integrated AI capabilities** each wired into existing procurement workflows.

Every AI call: goes through a service layer → structured Pydantic output → stored in DB
→ audited → retrievable. No raw LLM text ever reaches the frontend without validation.

---

## Capability Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AI PROCUREMENT COPILOT                                │
│                                                                               │
│  ① NL→PR         ② Vendor Rec.    ③ Policy Check   ④ Approval Summary      │
│  ─────────        ───────────────  ──────────────   ────────────────────     │
│  Parse text →     Historical PO    Pre-submit scan  Auto-generate exec       │
│  structured PR    data + ratings   for violations   summary for approvers    │
│                                                                               │
│  ⑤ Analytics Assistant              ⑥ Document Intelligence                 │
│  ─────────────────────              ──────────────────────────               │
│  NL→validated SQL→read-only query   PDF invoice → extracted line items       │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Model Strategy (OpenAI-compatible, configurable)

```
Primary:   claude-sonnet-4-6  (complex reasoning: NL→PR, policy, analytics)
Fast:      claude-haiku-4-5   (vendor scoring, summaries, simple extraction)
Vision:    claude-sonnet-4-6  (PDF/image document intelligence)

All accessed via Anthropic Messages API (OpenAI-compatible endpoint optional).
Model is swappable via AI_MODEL_PRIMARY / AI_MODEL_FAST env vars.
Fallback: if primary fails, retry with fast model at lower cost.
```

---

## Database Schema (New Tables)

### `ai_interactions` — Master interaction log
```sql
id UUID PK
session_id UUID (groups multi-turn conversations)
capability VARCHAR(30)  -- NL_TO_PR | VENDOR_REC | POLICY_CHECK | APPROVAL_SUMMARY | ANALYTICS | DOC_INTEL
user_id UUID FK auth_users
input_text TEXT
input_metadata JSONB          -- structured inputs beyond text
output_json JSONB             -- full structured response
model_used VARCHAR(50)
prompt_tokens INT
completion_tokens INT
latency_ms INT
status VARCHAR(20)            -- SUCCESS | FAILED | PARTIAL
error_detail TEXT
feedback_score SMALLINT       -- 1-5, user-provided
feedback_text TEXT
created_at TIMESTAMPTZ
```

### `ai_pr_drafts` — NL→PR results
```sql
id UUID PK
interaction_id UUID FK ai_interactions
pr_id UUID FK purchase_requisitions (NULL until user accepts)
raw_input TEXT
extracted_title VARCHAR(255)
extracted_items JSONB         -- [{description, quantity, estimated_price, category}]
extracted_department VARCHAR(100)
extracted_budget NUMERIC(18,2)
extracted_required_date DATE
extracted_priority VARCHAR(20)
business_justification TEXT
confidence_score NUMERIC(4,3) -- 0.000–1.000
warnings JSONB                -- ambiguities detected
status VARCHAR(20)            -- DRAFT | ACCEPTED | REJECTED | MODIFIED
created_at TIMESTAMPTZ
```

### `ai_vendor_recommendations` — Vendor scoring results
```sql
id UUID PK
interaction_id UUID FK ai_interactions
pr_id UUID FK purchase_requisitions
material_category VARCHAR(100)
recommendations JSONB         -- [{vendor_id, score, price_score, delivery_score, quality_score, explanation}]
data_snapshot JSONB           -- PO/rating data used (for reproducibility)
generated_at TIMESTAMPTZ
expires_at TIMESTAMPTZ        -- stale after 24h
```

### `ai_policy_checks` — Pre-submission compliance flags
```sql
id UUID PK
interaction_id UUID FK ai_interactions
pr_id UUID FK purchase_requisitions
overall_status VARCHAR(20)    -- PASS | WARN | BLOCK
violations JSONB              -- [{rule, severity, explanation, suggested_fix}]
checked_at TIMESTAMPTZ
overridden_by UUID FK auth_users
override_reason TEXT
```

### `ai_approval_summaries` — Auto-generated exec summaries
```sql
id UUID PK
interaction_id UUID FK ai_interactions
pr_id UUID FK purchase_requisitions UNIQUE
summary_text TEXT
cost_impact_analysis TEXT
business_value_text TEXT
risk_flags JSONB
comparable_purchases JSONB    -- similar past PRs
generated_at TIMESTAMPTZ
```

### `ai_analytics_queries` — Validated analytics queries
```sql
id UUID PK
interaction_id UUID FK ai_interactions
user_question TEXT
classified_intent VARCHAR(50) -- VENDOR_PERFORMANCE | SPEND_ANALYSIS | INVENTORY | DEPARTMENT_SPEND
generated_sql TEXT
sql_validated BOOLEAN
allowed_tables TEXT[]
result_json JSONB             -- stored result
row_count INT
executed_at TIMESTAMPTZ
```

### `ai_document_extractions` — PDF/invoice intelligence results
```sql
id UUID PK
interaction_id UUID FK ai_interactions
invoice_id UUID FK invoices (NULL until linked)
source_filename VARCHAR(255)
source_s3_key VARCHAR(500)
extracted_invoice_number VARCHAR(100)
extracted_vendor_name VARCHAR(255)
extracted_po_number VARCHAR(100)
extracted_date DATE
extracted_due_date DATE
extracted_line_items JSONB
extracted_total NUMERIC(18,2)
confidence_score NUMERIC(4,3)
raw_extraction JSONB          -- full LLM output pre-mapping
status VARCHAR(20)            -- EXTRACTED | LINKED | REJECTED
created_at TIMESTAMPTZ
```

---

## Service Architecture

```
app/ai/
├── __init__.py
├── client.py               # Anthropic client wrapper, retry logic, cost tracking
├── schemas/
│   ├── nl_to_pr.py         # Pydantic models for NL→PR extraction
│   ├── vendor_rec.py       # Vendor recommendation output schema
│   ├── policy.py           # Policy violation schema
│   ├── approval.py         # Approval summary schema
│   ├── analytics.py        # Analytics query + result schema
│   └── document.py         # Document extraction schema
├── prompts/
│   ├── nl_to_pr.py         # System + user prompt templates
│   ├── vendor_rec.py
│   ├── policy.py
│   ├── approval.py
│   ├── analytics.py
│   └── document.py
├── agents/
│   ├── nl_to_pr_agent.py   # LangGraph agent: parse → validate → draft
│   ├── vendor_rec_agent.py # fetch context → score → rank → explain
│   ├── policy_agent.py     # check each rule → aggregate violations
│   ├── approval_agent.py   # gather context → generate summary
│   ├── analytics_agent.py  # classify → generate SQL → validate → execute
│   └── document_agent.py   # extract → validate → map to schema
├── tools/
│   ├── procurement_tools.py  # DB read tools for agents
│   ├── sql_validator.py      # Whitelist-based SQL safety checker
│   └── pdf_extractor.py      # S3 fetch + base64 for vision API
└── evaluators/
    ├── pr_eval.py            # Evaluate NL→PR extraction quality
    ├── vendor_eval.py        # Evaluate recommendation accuracy
    └── analytics_eval.py     # Evaluate SQL generation correctness
```

---

## LangGraph Agent Flows

### ① NL→PR Agent (3-node graph)
```
[parse_intent]──→[extract_entities]──→[validate_and_score]
     │                  │                      │
  classify          structured            confidence +
  request           PR fields             warnings
```

### ② Vendor Recommendation Agent (4-node graph)
```
[load_context]──→[score_vendors]──→[rank_and_explain]──→[cache_result]
     │                │                   │
  historical       per-vendor          narrative
  PO data          scoring             explanation
```

### ③ Policy Check Agent (parallel nodes)
```
         ┌──[check_budget_rule]
         ├──[check_duplicate_rule]
[start]──┼──[check_vendor_status]──→[aggregate_violations]──→[classify_severity]
         ├──[check_quantity_rule]
         └──[check_category_rule]
```

### ⑤ Analytics Agent (guarded pipeline)
```
[classify_intent]──→[generate_sql]──→[validate_sql]──→[execute_query]──→[format_response]
        │                 │                │
   whitelist          Pydantic         allowed_tables
   check              output            check + EXPLAIN
```

---

## Security Model

### Analytics SQL Guard
- Query classification: only 6 intent types allowed
- Whitelist of allowed tables (14 read-only tables)
- Forbidden keywords: DROP, DELETE, UPDATE, INSERT, TRUNCATE, EXEC, COPY
- Query must pass EXPLAIN (dry-run) before execution
- Maximum row count: 1000
- 5-second query timeout
- All queries logged in `ai_analytics_queries`

### API Security
- All AI endpoints require authenticated user
- Rate limiting: 30 req/min per user (separate from main API)
- Cost guard: max $0.50 per request (reject if estimated > threshold)
- PII stripping in logs (email, phone, employee IDs redacted)

---

## Prompt Engineering Strategy

### Structured Output Pattern (all agents)
```python
# ALWAYS use JSON mode + Pydantic validation
# Never parse unstructured text
# If LLM output fails Pydantic validation → retry once with error context
# If second attempt fails → return graceful error, log for eval

system_prompt = """
You are EPIMS AI, an enterprise procurement assistant.
Output ONLY valid JSON matching this exact schema: {schema}
Do not include explanations outside the JSON structure.
"""
```

### Context Injection Strategy
```
NL→PR:        inject material categories, department list, budget policies
Vendor Rec:   inject last 12 months PO history per vendor per category
Policy:       inject budget limits table, approved vendor list, past duplicates
Approval:     inject comparable past PRs, vendor history, budget utilization
Analytics:    inject table schemas, sample data (no PII), intent classification
Document:     inject expected format hints, vendor name list for fuzzy matching
```

### Few-Shot Examples
Each prompt includes 2-3 domain-specific examples curated from Indian enterprise procurement:
- Laptop purchases with INR pricing
- Consumables with bulk quantities  
- IT services with monthly retainers

---

## Cost Optimization

| Capability | Model | Est. tokens | Est. cost/call |
|-----------|-------|-------------|----------------|
| NL→PR | claude-sonnet-4-6 | 1,500 in / 500 out | ~$0.005 |
| Vendor Rec | claude-haiku-4-5 | 2,000 in / 800 out | ~$0.002 |
| Policy Check | claude-haiku-4-5 | 1,200 in / 400 out | ~$0.001 |
| Approval Summary | claude-haiku-4-5 | 1,800 in / 600 out | ~$0.002 |
| Analytics | claude-sonnet-4-6 | 1,000 in / 300 out | ~$0.003 |
| Document Intel | claude-sonnet-4-6 | 2,500 in / 1,000 out | ~$0.010 |

**Caching**: Vendor recommendations cached 24h. Policy rules cached 1h.
**Batching**: Approval summaries generated async via Celery, not on request path.

---

## Evaluation Framework

### Metrics Per Capability

**NL→PR Extraction**
- Entity accuracy: field-level match rate vs human-labeled test set (target: >90%)
- Quantity precision: numeric accuracy
- Date extraction accuracy
- Confidence calibration: ECE (Expected Calibration Error)

**Vendor Recommendation**
- Rank correlation with actual selection history (Spearman ρ)
- Precision@3: top-3 recommendation hit rate
- Explanation quality (human eval: 1-5)

**Policy Check**
- Precision/recall on violation detection (test set of known violations)
- False positive rate (must be < 5%)

**Analytics SQL**
- SQL validity rate (parses correctly)
- Result accuracy vs baseline queries
- Safety: zero arbitrary execution incidents

**Document Intelligence**
- Field extraction accuracy (per field)
- Invoice number: >99% (exact match)
- Line items: >95% (amount within 1%)

### Feedback Loop
- Every AI response has thumbs up/down in UI
- Negative feedback auto-creates eval case for review
- Weekly report of accuracy metrics per capability
- Prompt version tracked in DB (ai_interactions.model_used includes prompt hash)
