"""SCALE BENCHMARK.

Measures the deterministic hot path - Tier 1 feature updates plus Tier 2
scoring - for a large synthetic population, then extrapolates linearly to
KBC's customer base.

What is measured, honestly:
  * IN  : Tier 1 `apply_transaction`, Tier 1 `recompute_derived`,
          Tier 2 `score_all` over every scoring model.
  * OUT : SQLite writes and HTTP. Those are I/O that a production system
          replaces wholesale (Kafka + a feature store), so including them
          would measure SQLite, not the Twin engine.

Every number the UI shows comes from an actual run of this code. The
extrapolation is arithmetic on the measured rate and is labelled as an
estimate in the UI, because that is what it is.
"""
from __future__ import annotations

import gc
import platform
import random
import resource
import sys
import time
from datetime import datetime, timezone

from . import config, db, features, scoring

# A compact, representative month of events per customer. Enough to exercise
# income detection, fixed costs, savings and a life-event signal.
EVENT_TEMPLATE = [
    ("salary", 2600.00), ("rent", -900.00), ("utilities", -130.00),
    ("telecom", -45.00), ("groceries", -320.00), ("groceries", -180.00),
    ("transport_public", -55.00), ("restaurants", -70.00),
    ("insurance", -80.00), ("savings_transfer", -250.00),
    ("baby_retail", -45.00), ("investment_contribution", -120.00),
]


def _rss_mb() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # ru_maxrss is bytes on macOS, kilobytes on Linux.
    return round(usage / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)


def run(customers: int | None = None, events_per_customer: int | None = None,
        target_population: int | None = None, persist: bool = True) -> dict:
    customers = customers or config.BENCHMARK_CUSTOMERS
    events_per_customer = events_per_customer or config.BENCHMARK_EVENTS_PER_CUSTOMER
    target_population = target_population or config.TARGET_POPULATION

    rng = random.Random(config.SEED)
    template = EVENT_TEMPLATE[:events_per_customer] or EVENT_TEMPLATE
    per_customer = len(template)

    # Pre-build the event dicts for one customer so the loop measures the
    # engine, not dict construction.
    base_customer = {"age": 33, "children": 0, "household_type": "couple",
                     "housing": "renting", "partner_name": "partner"}

    gc.collect()
    rss_before = _rss_mb()
    latencies: list[float] = []
    processed = 0

    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    for index in range(customers):
        state = features.new_state(savings_balance=rng.uniform(500, 40000))
        month = f"2026-{(index % 12) + 1:02d}"
        t0 = time.perf_counter()
        for day, (category, amount) in enumerate(template, start=1):
            features.apply_transaction(state, {
                "timestamp": f"{month}-{day:02d}T09:00:00",
                "merchant": "benchmark",
                "category": category,
                "amount": amount,
            })
            processed += 1
        # Tier 1 derive + Tier 2 score once per customer, as the real pipeline
        # does at the end of a micro-batch.
        derived = features.recompute_derived(state)
        ctx = scoring.build_context(derived, base_customer)
        scoring.score_all(ctx)
        # Sample latencies rather than storing millions of floats.
        if index % 97 == 0:
            latencies.append((time.perf_counter() - t0) * 1000)

    wall = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    gc.collect()
    rss_after = _rss_mb()

    events_per_second = processed / wall if wall > 0 else 0.0
    avg_event_latency_us = (wall / processed * 1_000_000) if processed else 0.0
    latencies.sort()
    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        return round(latencies[min(len(latencies) - 1, int(p * len(latencies)))], 3)

    # --- extrapolation. Arithmetic on the measured rate. -------------------
    scale = target_population / customers if customers else 0.0
    equivalent_events = int(processed * scale)
    single_worker_seconds = equivalent_events / events_per_second if events_per_second else 0.0
    workers = max(1, config.BENCHMARK_PRODUCTION_WORKERS)

    result = {
        "measured": {
            "customers": customers,
            "events_per_customer": per_customer,
            "events_processed": processed,
            "wall_seconds": round(wall, 3),
            "cpu_seconds": round(cpu, 3),
            "events_per_second": round(events_per_second, 1),
            "avg_event_latency_us": round(avg_event_latency_us, 2),
            "per_customer_latency_ms": {
                "p50": pct(0.50), "p95": pct(0.95), "p99": pct(0.99),
            },
            "peak_rss_mb": rss_after,
            "rss_growth_mb": round(rss_after - rss_before, 1),
        },
        "extrapolation": {
            "is_estimate": True,
            "basis": "Linear extrapolation of the measured single-process rate.",
            "target_population": target_population,
            "equivalent_events": equivalent_events,
            "single_worker_seconds": round(single_worker_seconds, 1),
            "single_worker_minutes": round(single_worker_seconds / 60, 1),
            "parallel_workers": workers,
            "parallel_seconds": round(single_worker_seconds / workers, 1),
            "caveats": [
                "One Python process, one core, no network and no durable writes.",
                "Production adds Kafka, a feature store and replication - so real "
                "throughput per worker will be lower, but scales out across partitions.",
                "Events are partitioned by customer, so this scales horizontally: "
                "the per-customer path is single-writer and lock-free.",
            ],
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "scope": {
            "included": ["Tier 1 feature updates", "Tier 1 derived features",
                         "Tier 2 scoring across all models"],
            "excluded": ["SQLite writes", "HTTP", "Tier 3 narrative generation"],
            "why": ("Storage and transport are exactly what production replaces "
                    "(Kafka + feature store), so timing SQLite would measure the "
                    "wrong thing. Tier 3 is excluded because it is not on this path."),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if persist:
        db.execute(
            "INSERT INTO benchmark_runs(result_json, created_at) VALUES(?, datetime('now'))",
            (db.dumps(result),),
        )
    return result


def latest() -> dict | None:
    row = db.query_one(
        "SELECT result_json, created_at FROM benchmark_runs ORDER BY id DESC LIMIT 1"
    )
    if not row:
        return None
    result = db.loads(row["result_json"])
    result["stored_at"] = row["created_at"]
    return result


# --------------------------------------------------------------------------
# Cost model. Every input is configurable; nothing here is a price quote.
# --------------------------------------------------------------------------
def cost_model(bench: dict | None = None) -> dict:
    bench = bench or latest()
    population = config.TARGET_POPULATION

    daily_opens = population * config.DAILY_APP_OPEN_RATE
    monthly_changes = population * config.MONTHLY_TWIN_CHANGE_RATE
    daily_changes = monthly_changes / 30.0
    daily_calls = daily_opens + daily_changes
    monthly_calls = daily_calls * 30

    tokens_in = config.LLM_TOKENS_IN
    tokens_out = config.LLM_TOKENS_OUT
    cost_per_call = (
        tokens_in / 1_000_000 * config.LLM_PRICE_INPUT_PER_MTOK
        + tokens_out / 1_000_000 * config.LLM_PRICE_OUTPUT_PER_MTOK
    )

    # The counterfactual: one LLM call per transaction. This is the number the
    # architecture exists to avoid.
    txns_per_customer_per_month = 45
    naive_monthly_calls = population * txns_per_customer_per_month

    events_per_second = (bench or {}).get("measured", {}).get("events_per_second", 0)
    monthly_events = population * txns_per_customer_per_month
    deterministic_core_seconds = (
        monthly_events / events_per_second if events_per_second else 0.0
    )

    return {
        "assumptions": {
            "population": population,
            "daily_app_open_rate": config.DAILY_APP_OPEN_RATE,
            "monthly_twin_change_rate": config.MONTHLY_TWIN_CHANGE_RATE,
            "tokens_per_call_in": tokens_in,
            "tokens_per_call_out": tokens_out,
            "price_input_per_mtok_usd": config.LLM_PRICE_INPUT_PER_MTOK,
            "price_output_per_mtok_usd": config.LLM_PRICE_OUTPUT_PER_MTOK,
            "transactions_per_customer_per_month": txns_per_customer_per_month,
            "price_source": config.PRICE_SOURCE_NOTE,
        },
        "llm": {
            "daily_calls": round(daily_calls),
            "monthly_calls": round(monthly_calls),
            "cost_per_call_usd": round(cost_per_call, 6),
            "daily_cost_usd": round(daily_calls * cost_per_call, 2),
            "monthly_cost_usd": round(monthly_calls * cost_per_call, 2),
        },
        "naive_per_transaction": {
            "monthly_calls": naive_monthly_calls,
            "monthly_cost_usd": round(naive_monthly_calls * cost_per_call, 2),
            "multiple_of_selective": (
                round(naive_monthly_calls / monthly_calls, 1) if monthly_calls else 0
            ),
        },
        "deterministic_core": {
            "monthly_events": monthly_events,
            "measured_events_per_second": events_per_second,
            "single_worker_hours_per_month": round(deterministic_core_seconds / 3600, 2),
            "note": ("Rules and streaming absorb every transaction. This is CPU "
                     "time on commodity workers, not model inference."),
        },
        "storage": {
            "note": ("One Twin document per customer plus an append-only version "
                     "history. Kilobytes per customer, so storage is not the "
                     "constraint - the transaction history already dwarfs it."),
        },
    }
