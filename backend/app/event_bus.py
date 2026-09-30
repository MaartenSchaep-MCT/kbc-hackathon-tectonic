"""EVENT INGESTION - the in-process stand-in for Kafka.

    channel  ->  asyncio.Queue  ->  worker  ->  Tier 1  ->  Tier 2  ->  Twin

One `asyncio.Queue` and one worker coroutine. Producers (`publish`) return as
soon as the event is accepted, exactly as a Kafka producer does, so the API
never blocks on Twin recomputation. The worker records per-stage timings,
which is what the UI animates.

HOW THIS MAPS TO PRODUCTION
---------------------------
    asyncio.Queue           ->  Kafka topic, partitioned by customer_id
    this single worker       ->  Flink / Kafka Streams operators, one per
                                partition, scaled horizontally
    features table          ->  online feature store (low-latency K/V)
    twins table             ->  operational store + Twin change topic
    pipeline_trace table    ->  the platform's own tracing/metrics

The important property is already true here: events are partitioned by
customer, so all processing for one customer is ordered and single-writer.
That is what makes the real version horizontally scalable without locks.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from . import catalog, db, features, twin_engine
from .schemas import TransactionIn

QUEUE_MAXSIZE = 10_000

_queue: asyncio.Queue | None = None
_worker: asyncio.Task | None = None
_stats = {"published": 0, "processed": 0, "failed": 0, "last_latency_ms": 0.0}


def get_queue() -> asyncio.Queue:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    return _queue


def stats() -> dict:
    q = get_queue()
    return {**_stats, "queue_depth": q.qsize(), "queue_maxsize": QUEUE_MAXSIZE,
            "worker_running": bool(_worker and not _worker.done())}


async def publish(txn: TransactionIn, label: str = "") -> dict:
    """Accept an event. Returns immediately - processing is asynchronous."""
    event_id = f"EV-{uuid.uuid4().hex[:12]}"
    timestamp = txn.timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "event_id": event_id,
        "label": label or f"{catalog.label_for(txn.category)} - {txn.merchant}",
        "customer_id": txn.customer_id,
        "timestamp": timestamp,
        "merchant": txn.merchant,
        "category": txn.category,
        "amount": round(txn.amount, 2),
        "description": txn.description or txn.merchant,
        "channel": txn.channel,
        "enqueued_at": time.perf_counter(),
    }
    q = get_queue()
    await q.put(payload)
    _stats["published"] += 1
    return {"event_id": event_id, "queue_depth": q.qsize()}


def process_event(event: dict) -> dict:
    """Synchronous core: one event, all the way through to a saved Twin.

    Split out from the worker loop so tests and the benchmark can call it
    directly without an event loop.
    """
    stages: list[dict] = []
    t_start = time.perf_counter()

    def stage(name: str, detail: str, started: float) -> float:
        now = time.perf_counter()
        stages.append({"name": name, "detail": detail,
                       "ms": round((now - started) * 1000, 3)})
        return now

    mark = t_start
    if "enqueued_at" in event:
        stages.append({
            "name": "Event ingestion",
            "detail": f"Accepted from {catalog.CHANNEL_LABELS.get(event['channel'], event['channel'])}",
            "ms": round((t_start - event["enqueued_at"]) * 1000, 3),
        })

    customer = twin_engine.load_customer(event["customer_id"])
    if not customer:
        raise ValueError(f"unknown customer {event['customer_id']}")

    # --- persist the raw fact ------------------------------------------
    db.execute(
        "INSERT INTO transactions(transaction_id, customer_id, timestamp, merchant, "
        "category, amount, description, channel, injected) VALUES(?,?,?,?,?,?,?,?,1)",
        (f"TX-{uuid.uuid4().hex[:16]}", event["customer_id"], event["timestamp"],
         event["merchant"], event["category"], event["amount"], event["description"],
         event["channel"]),
    )
    mark = stage("Transaction stored", "Observed fact recorded, append-only", mark)

    # --- TIER 1 -------------------------------------------------------
    state = twin_engine.load_features(event["customer_id"]) or features.new_state()
    features.apply_transaction(state, event)
    derived = features.recompute_derived(state)
    twin_engine.save_features(event["customer_id"], state)
    mark = stage(
        "Tier 1 - feature update",
        f"{len(derived)} features recomputed (income EUR {derived['monthly_income']:,.0f}, "
        f"savings EUR {derived['savings_balance']:,.0f})",
        mark,
    )

    # --- TIER 2 + Twin assembly ---------------------------------------
    previous = twin_engine.load_twin(event["customer_id"])
    twin = twin_engine.build_twin(
        customer, state, previous=previous,
        narrative=(previous or {}).get("narrative"),
    )
    triggered = [s.label for s in twin.signals if s.triggered]
    mark = stage(
        "Tier 2 - life-event scoring",
        f"{len(twin.signals)} models scored, {len(triggered)} signals active",
        mark,
    )

    payload = twin_engine.save_twin(twin)
    mark = stage(
        "Financial Twin updated",
        f"Version {twin.version} - {twin.change_summary[:110]}",
        mark,
    )
    stages.append({
        "name": "Shared Twin API",
        "detail": "Same version now served to app, Kate, advisor, insurance and lending",
        "ms": 0.0,
    })

    total_ms = round((time.perf_counter() - t_start) * 1000, 3)
    trace = {
        "event_id": event["event_id"],
        "customer_id": event["customer_id"],
        "label": event["label"],
        "stages": stages,
        "total_ms": total_ms,
        "twin_version": twin.version,
        "changed": twin.changed_fields,
        "change_summary": twin.change_summary,
    }
    db.execute(
        "INSERT INTO pipeline_trace(event_id, customer_id, label, stages_json, "
        "total_ms, twin_version, changed_json, created_at) "
        "VALUES(?,?,?,?,?,?,?,datetime('now'))",
        (event["event_id"], event["customer_id"], event["label"], db.dumps(stages),
         total_ms, twin.version, db.dumps(twin.changed_fields)),
    )
    _stats["last_latency_ms"] = total_ms
    return {"trace": trace, "twin": payload}


async def _worker_loop() -> None:
    q = get_queue()
    while True:
        event = await q.get()
        try:
            # SQLite work is synchronous; a thread keeps the loop responsive.
            result = await asyncio.to_thread(process_event, event)
            _stats["processed"] += 1
            # Tier 3 runs only when the Twin actually changed state.
            from . import llm
            if result["trace"]["changed"]:
                await llm.refresh_narrative(event["customer_id"],
                                            reason=result["trace"]["change_summary"])
        except Exception as exc:                        # keep the worker alive
            _stats["failed"] += 1
            print(f"[event_bus] failed to process {event.get('event_id')}: {exc!r}")
        finally:
            q.task_done()


async def start_worker() -> None:
    global _worker
    if _worker is None or _worker.done():
        _worker = asyncio.create_task(_worker_loop(), name="twin-event-worker")


async def stop_worker() -> None:
    global _worker
    if _worker and not _worker.done():
        _worker.cancel()
        try:
            await _worker
        except asyncio.CancelledError:
            pass
    _worker = None


async def drain(timeout: float = 15.0) -> bool:
    """Wait until the queue is empty. Used by tests and the demo endpoints."""
    q = get_queue()
    try:
        await asyncio.wait_for(q.join(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


def recent_traces(limit: int = 12) -> list[dict]:
    rows = db.query(
        "SELECT event_id, customer_id, label, stages_json, total_ms, twin_version, "
        "changed_json, created_at FROM pipeline_trace ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [
        {
            "event_id": r["event_id"], "customer_id": r["customer_id"],
            "label": r["label"], "stages": db.loads(r["stages_json"], []),
            "total_ms": r["total_ms"], "twin_version": r["twin_version"],
            "changed": db.loads(r["changed_json"], []), "created_at": r["created_at"],
        }
        for r in rows
    ]
