"""Central configuration. Everything is an environment variable with a sane
default so the prototype runs with zero setup."""
from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# --- storage ---------------------------------------------------------------
DB_PATH = os.getenv("TWIN_DB_PATH", "/data/twin.db")

# --- synthetic data -------------------------------------------------------
SEED = _int("TWIN_SEED", 42)
N_CUSTOMERS = _int("TWIN_CUSTOMERS", 1000)
N_MONTHS = _int("TWIN_MONTHS", 12)

# "Today" for the synthetic world. Fixed so the demo is reproducible.
REFERENCE_DATE = os.getenv("TWIN_REFERENCE_DATE", "2026-09-30")

# --- Tier 3 (LLM) ---------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or ""
LLM_MODEL = os.getenv("TWIN_LLM_MODEL", "claude-opus-5-5")
LLM_TIMEOUT_SECONDS = _float("TWIN_LLM_TIMEOUT_SECONDS", 12.0)
LLM_ENABLED = bool(ANTHROPIC_API_KEY)

# --- benchmark -----------------------------------------------------------
BENCHMARK_CUSTOMERS = _int("TWIN_BENCHMARK_CUSTOMERS", 100_000)
BENCHMARK_EVENTS_PER_CUSTOMER = _int("TWIN_BENCHMARK_EVENTS_PER_CUSTOMER", 12)
TARGET_POPULATION = _int("TWIN_TARGET_POPULATION", 2_300_000)
BENCHMARK_ON_STARTUP = _bool("TWIN_BENCHMARK_ON_STARTUP", True)
BENCHMARK_PRODUCTION_WORKERS = _int("TWIN_BENCHMARK_PRODUCTION_WORKERS", 20)

# --- cost model (see README section "Cost") -------------------------------
# All configurable: we never hardcode a production price claim.
LLM_PRICE_INPUT_PER_MTOK = _float("TWIN_LLM_PRICE_INPUT_PER_MTOK", 4.00)
LLM_PRICE_OUTPUT_PER_MTOK = _float("TWIN_LLM_PRICE_OUTPUT_PER_MTOK", 20.00)
LLM_TOKENS_IN = _int("TWIN_LLM_TOKENS_IN", 900)
LLM_TOKENS_OUT = _int("TWIN_LLM_TOKENS_OUT", 160)
DAILY_APP_OPEN_RATE = _float("TWIN_ASSUMPTION_DAILY_APP_OPEN_RATE", 0.05)
MONTHLY_TWIN_CHANGE_RATE = _float("TWIN_ASSUMPTION_MONTHLY_TWIN_CHANGE_RATE", 0.10)
PRICE_SOURCE_NOTE = os.getenv(
    "TWIN_PRICE_SOURCE_NOTE",
    "Configured value, not a quoted contract price. Verify against current "
    "Anthropic pricing before using in any business case.",
)
