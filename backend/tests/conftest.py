"""Test fixtures.

Each test module gets its own throwaway SQLite file and a small population,
so tests are fast and cannot interfere with a running demo database.
"""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure BEFORE app modules are imported - config.py reads the environment
# at import time.
_TMP = tempfile.mkdtemp(prefix="twin-test-")
os.environ["TWIN_DB_PATH"] = os.path.join(_TMP, "twin.db")
os.environ["TWIN_CUSTOMERS"] = "40"
os.environ["TWIN_BENCHMARK_ON_STARTUP"] = "0"
os.environ["TWIN_BENCHMARK_CUSTOMERS"] = "2000"
os.environ.pop("ANTHROPIC_API_KEY", None)      # test 5: no key must be fine

from fastapi.testclient import TestClient      # noqa: E402

from app import db, seed                       # noqa: E402
from app.main import app                       # noqa: E402

HERO_A = "KBC-HERO-A"      # student -> first job
HERO_B = "KBC-HERO-B"      # possible family expansion
HERO_C = "KBC-HERO-C"      # nearing retirement


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_world(client):
    """Fresh seeded world before every test, so tests are order-independent."""
    seed.seed(force=True)
    with db.connect() as conn:
        conn.execute("DELETE FROM corrections")
        conn.execute("DELETE FROM pipeline_trace")
    yield


def signal(twin: dict, signal_id: str) -> dict:
    return next(s for s in twin["signals"] if s["id"] == signal_id)


def goal_ids(twin: dict) -> set[str]:
    return {g["id"] for g in twin["goals"]}


def playbook_ids(twin: dict) -> set[str]:
    return {p["id"] for p in twin["playbooks"]}
