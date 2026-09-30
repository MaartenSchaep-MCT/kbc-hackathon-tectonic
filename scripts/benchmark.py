#!/usr/bin/env python3
"""Standalone scale benchmark.

Runs the same code the API runs, without needing the API up:

    python scripts/benchmark.py
    python scripts/benchmark.py --customers 250000 --events 12 --json

Numbers printed here are measured on the machine you run it on. The
extrapolation to 2.3M customers is arithmetic on that measurement and is
labelled as an estimate, because that is all it is.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("TWIN_DB_PATH", str(ROOT / "data" / "benchmark.db"))

from app import benchmark, config, db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=config.BENCHMARK_CUSTOMERS)
    parser.add_argument("--events", type=int, default=config.BENCHMARK_EVENTS_PER_CUSTOMER,
                        help="events per customer")
    parser.add_argument("--population", type=int, default=config.TARGET_POPULATION,
                        help="population to extrapolate to")
    parser.add_argument("--json", action="store_true", help="print raw JSON")
    parser.add_argument("--no-persist", action="store_true",
                        help="do not write the result to the database")
    args = parser.parse_args()

    if not args.no_persist:
        db.init_db()

    print(f"Running: {args.customers:,} customers x {args.events} events ...",
          file=sys.stderr)
    result = benchmark.run(
        customers=args.customers,
        events_per_customer=args.events,
        target_population=args.population,
        persist=not args.no_persist,
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    m, e, env = result["measured"], result["extrapolation"], result["environment"]
    cost = benchmark.cost_model(result)

    def line(label: str, value: str) -> None:
        print(f"  {label:<34} {value}")

    print("\n" + "=" * 68)
    print("  MEASURED")
    print("=" * 68)
    line("Customers", f"{m['customers']:,}")
    line("Events processed", f"{m['events_processed']:,}")
    line("Wall time", f"{m['wall_seconds']:.3f} s")
    line("Throughput", f"{m['events_per_second']:,.0f} events/sec")
    line("Average per event", f"{m['avg_event_latency_us']:.2f} us")
    line("Per customer p50 / p95 / p99",
         f"{m['per_customer_latency_ms']['p50']:.3f} / "
         f"{m['per_customer_latency_ms']['p95']:.3f} / "
         f"{m['per_customer_latency_ms']['p99']:.3f} ms")
    line("Peak RSS", f"{m['peak_rss_mb']} MB")
    print(f"\n  Timed:     {', '.join(result['scope']['included'])}")
    print(f"  Not timed: {', '.join(result['scope']['excluded'])}")

    print("\n" + "=" * 68)
    print("  EXTRAPOLATION  (estimate - arithmetic on the rate above)")
    print("=" * 68)
    line("Target population", f"{e['target_population']:,}")
    line("Equivalent events", f"{e['equivalent_events']:,}")
    line("One worker, one core", f"{e['single_worker_minutes']:.1f} min")
    line(f"{e['parallel_workers']} parallel workers", f"{e['parallel_seconds']:.1f} s")
    for caveat in e["caveats"]:
        print(f"    - {caveat}")

    print("\n" + "=" * 68)
    print("  COST SHAPE  (all inputs configurable - see .env.example)")
    print("=" * 68)
    line("LLM calls / month (selective)", f"{cost['llm']['monthly_calls']:,}")
    line("LLM calls / month (per txn)", f"{cost['naive_per_transaction']['monthly_calls']:,}")
    line("Multiple avoided", f"{cost['naive_per_transaction']['multiple_of_selective']}x")
    line("Cost / month (selective)", f"${cost['llm']['monthly_cost_usd']:,.2f}")
    line("Cost / month (per txn)", f"${cost['naive_per_transaction']['monthly_cost_usd']:,.2f}")
    print(f"\n  {cost['assumptions']['price_source']}")

    print(f"\n  {env['platform']} / Python {env['python']} / {env['cpu_count']} cores\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
