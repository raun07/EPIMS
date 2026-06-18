"""
SQL Safety Validator for the Analytics AI Agent.

Multi-layer defense:
  1. Keyword blacklist (DROP, DELETE, UPDATE, INSERT…)
  2. Table whitelist — only allowed 14 read-only tables
  3. Must start with SELECT
  4. No semicolons (prevents statement chaining)
  5. No comment injection (-- or /* */)
  6. Row count enforcement via LIMIT injection
"""
from __future__ import annotations

import re

# ── Whitelist ─────────────────────────────────────────────────────────────────
ALLOWED_TABLES = frozenset({
    "purchase_requisitions",
    "pr_items",
    "purchase_orders",
    "po_items",
    "goods_receipts",
    "grn_items",
    "invoices",
    "invoice_items",
    "vendors",
    "materials",
    "material_groups",
    "inventory_stock",
    "stock_movements",
    "warehouses",
    "auth_users",
    "approval_instances",
})

# ── Blacklist ─────────────────────────────────────────────────────────────────
FORBIDDEN_PATTERNS = [
    r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b", r"\bDROP\b",
    r"\bTRUNCATE\b", r"\bALTER\b", r"\bCREATE\b", r"\bEXEC\b",
    r"\bEXECUTE\b", r"\bGRANT\b", r"\bREVOKE\b", r"\bCOPY\b",
    r"pg_catalog", r"information_schema", r"pg_sleep",
    r"pg_read_file", r"pg_write_file",
    r"--",          # SQL comment injection
    r"/\*",         # block comment
]

FORBIDDEN_RE = re.compile(
    "|".join(FORBIDDEN_PATTERNS),
    re.IGNORECASE,
)

TABLE_RE = re.compile(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", re.IGNORECASE)


class SQLValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def validate_sql(sql: str, max_rows: int = 1000) -> str:
    """
    Validate and sanitize a LLM-generated SQL query.
    Returns the (possibly LIMIT-injected) safe SQL string.
    Raises SQLValidationError if any check fails.
    """
    stripped = sql.strip()

    # 1. Must be SELECT
    if not re.match(r"^\s*SELECT\b", stripped, re.IGNORECASE):
        raise SQLValidationError("Query must start with SELECT")

    # 2. No semicolons (prevent chaining)
    if ";" in stripped:
        raise SQLValidationError("Semicolons not allowed — only single SELECT statements")

    # 3. No forbidden patterns
    match = FORBIDDEN_RE.search(stripped)
    if match:
        raise SQLValidationError(f"Forbidden keyword/pattern: '{match.group()}'")

    # 4. Only allowed tables
    referenced = set()
    for m in TABLE_RE.finditer(stripped):
        table = (m.group(1) or m.group(2) or "").lower()
        referenced.add(table)

    disallowed = referenced - ALLOWED_TABLES
    if disallowed:
        raise SQLValidationError(
            f"Query references disallowed table(s): {', '.join(sorted(disallowed))}. "
            f"Only these tables are permitted: {', '.join(sorted(ALLOWED_TABLES))}"
        )

    # 5. Inject LIMIT if missing (protect against large result sets)
    if not re.search(r"\bLIMIT\s+\d+", stripped, re.IGNORECASE):
        stripped = f"{stripped.rstrip().rstrip(';')} LIMIT {max_rows}"

    # 6. Replace any LIMIT > max_rows with max_rows
    def _cap_limit(m: re.Match) -> str:
        n = int(m.group(1))
        return f"LIMIT {min(n, max_rows)}"

    stripped = re.sub(r"\bLIMIT\s+(\d+)", _cap_limit, stripped, flags=re.IGNORECASE)

    return stripped


def extract_tables_referenced(sql: str) -> list[str]:
    """Return list of table names referenced in the query."""
    tables = []
    for m in TABLE_RE.finditer(sql):
        table = (m.group(1) or m.group(2) or "").lower()
        if table and table not in tables:
            tables.append(table)
    return tables
