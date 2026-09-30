"""Lightweight SQLite access.

Deliberately stdlib `sqlite3` rather than an ORM: the whole storage layer is
~120 lines, which keeps the prototype readable. In production this is the
seam where SQLite is swapped for a scalable operational store - every caller
below goes through `connect()` / the helpers, nothing writes SQL inline.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id     TEXT PRIMARY KEY,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    age             INTEGER NOT NULL,
    household_type  TEXT NOT NULL,
    partner_name    TEXT,
    children        INTEGER NOT NULL DEFAULT 0,
    housing         TEXT NOT NULL,
    city            TEXT NOT NULL,
    employer        TEXT,
    declared_json   TEXT NOT NULL,   -- customer-declared facts (source of truth)
    is_hero         INTEGER NOT NULL DEFAULT 0,
    hero_key        TEXT,
    hero_label      TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id  TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    merchant        TEXT NOT NULL,
    category        TEXT NOT NULL,
    amount          REAL NOT NULL,    -- positive = money in, negative = money out
    description     TEXT NOT NULL,
    channel         TEXT NOT NULL DEFAULT 'core_banking',
    injected        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_txn_customer ON transactions(customer_id, timestamp);

-- Tier 1 output: the online feature state, one row per customer.
CREATE TABLE IF NOT EXISTS features (
    customer_id     TEXT PRIMARY KEY,
    state_json      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- The Twin itself. Versioned; every channel reads this one row.
CREATE TABLE IF NOT EXISTS twins (
    customer_id     TEXT PRIMARY KEY,
    version         INTEGER NOT NULL,
    twin_json       TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Append-only audit trail of Twin versions (explainability / governance).
CREATE TABLE IF NOT EXISTS twin_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT NOT NULL,
    version         INTEGER NOT NULL,
    change_summary  TEXT NOT NULL,
    twin_json       TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hist_customer ON twin_history(customer_id, version);

-- Customer corrections. These OVERRIDE machine inference, permanently.
CREATE TABLE IF NOT EXISTS corrections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT NOT NULL,
    field           TEXT NOT NULL,
    value_json      TEXT NOT NULL,
    note            TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corr_customer ON corrections(customer_id, created_at);

-- Observability for the demo: what the event pipeline did, stage by stage.
CREATE TABLE IF NOT EXISTS pipeline_trace (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL,
    customer_id     TEXT NOT NULL,
    label           TEXT NOT NULL,
    stages_json     TEXT NOT NULL,
    total_ms        REAL NOT NULL,
    twin_version    INTEGER NOT NULL,
    changed_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trace_created ON pipeline_trace(id DESC);

-- Measured benchmark results (never hardcoded in the UI).
CREATE TABLE IF NOT EXISTS benchmark_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    result_json     TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL
);
"""


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


@contextmanager
def connect(path: str | None = None) -> Iterator[sqlite3.Connection]:
    """One short-lived connection per unit of work. WAL keeps concurrent
    readers (API requests) from blocking the writer (event worker)."""
    db_path = path or config.DB_PATH
    _ensure_parent(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return list(conn.execute(sql, tuple(params)))


def query_one(sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(sql, tuple(params)).fetchone()


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    with connect() as conn:
        conn.execute(sql, tuple(params))


def get_meta(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def loads(raw: str | None, fallback: Any = None) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
