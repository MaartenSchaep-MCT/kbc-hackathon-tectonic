"""ONE SHARED TWIN API.

Every channel - the customer app, Kate, the advisor desktop, insurance,
lending - reads and writes the same Twin through this one service. There is
no advisor-specific personalisation logic anywhere in this file: the advisor
endpoint reprojects the identical Twin document for a different audience.

That is the whole architectural claim, and it is verifiable: test 4 asserts
the customer endpoint and the advisor endpoint return the same version.
"""
from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from . import (benchmark, catalog, config, db, event_bus, features, llm,
               personas, playbooks, scoring, seed, twin_engine)
from .schemas import CorrectionIn, TransactionIn

_benchmark_state = {"status": "not_started", "error": None}


def _run_benchmark_background(delay: float = 4.0) -> None:
    """Runs once at startup in a thread, off the request path, so
    /api/benchmark serves measured numbers rather than placeholders.

    The delay matters: this loop is pure Python and holds the GIL, so starting
    it the instant the server boots would add latency to the first clicks of a
    live demo. Four seconds is enough for the UI to finish loading.
    """
    import time as _time
    _time.sleep(delay)
    _benchmark_state["status"] = "running"
    try:
        benchmark.run()
        _benchmark_state["status"] = "complete"
    except Exception as exc:
        _benchmark_state["status"] = "failed"
        _benchmark_state["error"] = repr(exc)
        print(f"[benchmark] failed: {exc!r}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    result = await asyncio.to_thread(seed.seed)
    print(f"[startup] seed: {result}")
    await event_bus.start_worker()
    if config.BENCHMARK_ON_STARTUP:
        threading.Thread(target=_run_benchmark_background, daemon=True,
                         name="benchmark").start()
    else:
        _benchmark_state["status"] = "disabled"
    yield
    await event_bus.stop_worker()


app = FastAPI(
    title="KBC Financial Twin API",
    description=(
        "One shared, explainable, customer-correctable financial model. "
        "Hackathon prototype on fully synthetic data."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _twin_or_404(customer_id: str) -> dict:
    twin = twin_engine.load_twin(customer_id)
    if not twin:
        raise HTTPException(404, f"No Twin for customer {customer_id}")
    return twin


def _rebuild_now(customer_id: str) -> dict:
    """Synchronous rebuild. Used for corrections, where the customer expects
    to see the effect of their own action immediately."""
    customer = twin_engine.load_customer(customer_id)
    if not customer:
        raise HTTPException(404, f"Unknown customer {customer_id}")
    state = twin_engine.load_features(customer_id) or features.new_state()
    features.recompute_derived(state)
    previous = twin_engine.load_twin(customer_id)
    twin = twin_engine.build_twin(customer, state, previous=previous,
                                  narrative=(previous or {}).get("narrative"))
    return twin_engine.save_twin(twin)


# --------------------------------------------------------------------------
# Health & metadata
# --------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    counts = db.query_one(
        "SELECT (SELECT COUNT(*) FROM customers) AS customers, "
        "(SELECT COUNT(*) FROM transactions) AS transactions, "
        "(SELECT COUNT(*) FROM twins) AS twins"
    )
    return {
        "status": "ok",
        "seeded": seed.is_seeded(),
        "customers": counts["customers"],
        "transactions": counts["transactions"],
        "twins": counts["twins"],
        "event_bus": event_bus.stats(),
        "tier3": llm.status(),
        "benchmark": _benchmark_state["status"],
        "reference_date": config.REFERENCE_DATE,
    }


@app.get("/api/meta")
def meta() -> dict:
    """Everything the frontend needs to render itself without hardcoding."""
    return {
        "reference_date": config.REFERENCE_DATE,
        "tier3": llm.status(),
        "channels": [{"id": c, "label": catalog.CHANNEL_LABELS[c]} for c in catalog.CHANNELS],
        "demo_actions": [{"key": k, **v} for k, v in personas.DEMO_ACTIONS.items()],
        "life_phases": scoring.LIFE_PHASE_LABELS,
        "provenance_labels": {
            "observed": "Observed fact",
            "derived": "Calculated from your data",
            "inferred": "Our assumption",
            "declared": "You told us",
        },
        "thresholds": scoring.THRESHOLDS,
        "max_inferred_confidence": scoring.MAX_INFERRED_CONFIDENCE,
        "synthetic_data_notice": (
            "All customers, transactions and merchants in this prototype are "
            "synthetic. No real KBC customer data is present."
        ),
    }


@app.get("/api/playbooks")
def list_playbooks() -> dict:
    return {
        "count": len(playbooks.PLAYBOOKS),
        "playbooks": [playbooks.as_dict(p) for p in playbooks.PLAYBOOKS],
    }


@app.get("/api/personas")
def list_personas() -> dict:
    out = []
    for cid in personas.HERO_ORDER:
        row = db.query_one("SELECT * FROM customers WHERE customer_id = ?", (cid,))
        if not row:
            continue
        twin = twin_engine.load_twin(cid) or {}
        out.append({
            "customer_id": cid,
            "hero_key": row["hero_key"],
            "hero_label": row["hero_label"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "age": row["age"],
            "city": row["city"],
            "household_type": row["household_type"],
            "story": personas.HERO_STORIES.get(cid, {}),
            "life_phase": twin.get("life_phase", {}),
            "progress_score": twin.get("progress_score"),
            "twin_version": twin.get("version"),
        })
    return {"personas": out}


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------
@app.get("/api/customers")
def list_customers(search: str = "", limit: int = Query(50, ge=1, le=500),
                   offset: int = Query(0, ge=0)) -> dict:
    where, params = "", []
    if search:
        where = ("WHERE c.first_name LIKE ? OR c.last_name LIKE ? "
                 "OR c.customer_id LIKE ? OR c.city LIKE ?")
        like = f"%{search}%"
        params = [like, like, like, like]
    total = db.query_one(f"SELECT COUNT(*) AS n FROM customers c {where}", params)["n"]
    rows = db.query(
        f"SELECT c.customer_id, c.first_name, c.last_name, c.age, c.household_type, "
        f"c.children, c.city, c.is_hero, c.hero_key, c.hero_label, t.version, t.twin_json "
        f"FROM customers c LEFT JOIN twins t ON t.customer_id = c.customer_id {where} "
        f"ORDER BY c.is_hero DESC, c.customer_id LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    items = []
    for r in rows:
        twin = db.loads(r["twin_json"], {}) or {}
        items.append({
            "customer_id": r["customer_id"],
            "name": f"{r['first_name']} {r['last_name']}",
            "age": r["age"],
            "household_type": r["household_type"],
            "children": r["children"],
            "city": r["city"],
            "is_hero": bool(r["is_hero"]),
            "hero_key": r["hero_key"],
            "hero_label": r["hero_label"],
            "twin_version": r["version"],
            "life_phase": (twin.get("life_phase") or {}).get("value"),
            "life_phase_label": (twin.get("life_phase") or {}).get("label"),
            "confidence": (twin.get("life_phase") or {}).get("confidence"),
            "progress_score": twin.get("progress_score"),
        })
    return {"total": total, "limit": limit, "offset": offset, "customers": items}


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str, transactions: int = Query(40, ge=0, le=500)) -> dict:
    customer = twin_engine.load_customer(customer_id)
    if not customer:
        raise HTTPException(404, f"Unknown customer {customer_id}")
    rows = db.query(
        "SELECT transaction_id, timestamp, merchant, category, amount, description, "
        "channel, injected FROM transactions WHERE customer_id = ? "
        "ORDER BY timestamp DESC, rowid DESC LIMIT ?",
        (customer_id, transactions),
    )
    return {
        "customer": customer,
        "housing_label": customer.get("housing", "").replace("_", " ").capitalize(),
        "transactions": [
            {**dict(r), "category_label": catalog.label_for(r["category"]),
             "injected": bool(r["injected"])}
            for r in rows
        ],
    }


# --------------------------------------------------------------------------
# The Twin
# --------------------------------------------------------------------------
@app.get("/api/twins/{customer_id}")
async def get_twin(customer_id: str,
                   refresh_narrative: bool = Query(False, alias="open")) -> dict:
    twin = _twin_or_404(customer_id)
    # "Customer opens the experience" is one of exactly two Tier 3 triggers.
    if refresh_narrative or not twin.get("narrative"):
        narrative = await llm.refresh_narrative(customer_id, reason="app_open")
        if narrative:
            twin["narrative"] = narrative
    return twin


@app.get("/api/twins/{customer_id}/timeline")
def get_timeline(customer_id: str) -> dict:
    twin = _twin_or_404(customer_id)
    return {
        "customer_id": customer_id,
        "version": twin["version"],
        "timeline": twin["future_timeline"],
        "retirement": twin["derived_features"].get("retirement", {}),
    }


@app.get("/api/twins/{customer_id}/history")
def get_history(customer_id: str, limit: int = Query(15, ge=1, le=100)) -> dict:
    rows = db.query(
        "SELECT version, change_summary, created_at FROM twin_history "
        "WHERE customer_id = ? ORDER BY version DESC LIMIT ?",
        (customer_id, limit),
    )
    return {"customer_id": customer_id, "history": [dict(r) for r in rows]}


@app.get("/api/twins/{customer_id}/explanations")
def get_explanations(customer_id: str) -> dict:
    twin = _twin_or_404(customer_id)
    return {"customer_id": customer_id, "version": twin["version"],
            "explanations": twin["explanations"], "signals": twin["signals"]}


# --------------------------------------------------------------------------
# Corrections - the customer overrides the machine
# --------------------------------------------------------------------------
CORRECTABLE_FIELDS = {
    "life_phase": "Your life phase",
    "plans_to_buy_house": "Whether you plan to buy a home",
    "family_expansion": "Whether your family is growing",
    "target_retirement_age": "Your target retirement age",
    "household_type": "Your household type",
    "children": "Number of children",
}
# goal_target:<id> changes an amount, goal_removed:<id> takes a goal out of the
# plan (false puts it back), custom_goal:<id> = {title, target_amount} adds one
# (null deletes it).
GOAL_FIELD_PREFIXES = ("goal_target:", "goal_removed:", "custom_goal:")


def _describe_correction(c: dict) -> dict:
    """Label and value for a correction, readable by an advisor."""
    field, value = c["field"], c["value"]
    kind, _, goal_id = field.partition(":")
    name = goal_id.replace("_", " ")
    if kind == "goal_removed":
        return {"label": f"Goal '{name}'", "value": "Removed" if value else "Put back"}
    if kind == "custom_goal":
        if not value:
            return {"label": f"Own goal '{name}'", "value": "Deleted"}
        return {"label": f"Own goal '{value.get('title', name)}'",
                "value": f"EUR {float(value.get('target_amount', 0)):,.0f}"}
    if kind == "goal_target":
        return {"label": f"Target for '{name}'", "value": f"EUR {float(value):,.0f}"}
    return {"label": CORRECTABLE_FIELDS.get(field, field), "value": value}


@app.get("/api/twins/{customer_id}/corrections")
def list_corrections(customer_id: str) -> dict:
    twin = _twin_or_404(customer_id)
    goal_fields = {
        f"goal_target:{g['id']}": f"Target amount for '{g['title']}'"
        for g in twin["goals"]
    }
    return {
        "customer_id": customer_id,
        "corrections": twin["corrections"],
        "correctable_fields": {**CORRECTABLE_FIELDS, **goal_fields},
        "life_phase_options": scoring.LIFE_PHASE_LABELS,
        "notice": "Your corrections override automated assumptions.",
    }


@app.post("/api/twins/{customer_id}/corrections")
async def add_correction(customer_id: str, body: CorrectionIn) -> dict:
    if not twin_engine.load_customer(customer_id):
        raise HTTPException(404, f"Unknown customer {customer_id}")
    field = body.field
    if field not in CORRECTABLE_FIELDS and not field.startswith(GOAL_FIELD_PREFIXES):
        raise HTTPException(
            400,
            f"'{field}' is not a correctable field. Allowed: {sorted(CORRECTABLE_FIELDS)}, "
            f"goal_target:<goal_id>, goal_removed:<goal_id> or custom_goal:<goal_id>",
        )
    if field == "life_phase" and body.value not in scoring.LIFE_PHASE_LABELS:
        raise HTTPException(400, f"Unknown life phase '{body.value}'")
    if field.startswith("custom_goal:") and body.value is not None:
        value = body.value if isinstance(body.value, dict) else {}
        try:
            amount = float(value.get("target_amount", 0))
        except (TypeError, ValueError):
            amount = 0
        if not str(value.get("title", "")).strip() or amount <= 0:
            raise HTTPException(400, "A custom goal needs a title and a target_amount above 0")

    db.execute(
        "INSERT INTO corrections(customer_id, field, value_json, note, created_at) "
        "VALUES(?,?,?,?,datetime('now'))",
        (customer_id, field, db.dumps(body.value), body.note),
    )
    twin = _rebuild_now(customer_id)
    narrative = await llm.refresh_narrative(customer_id, reason="customer_correction")
    if narrative:
        twin["narrative"] = narrative
    return {
        "stored": {"field": field, "value": body.value, "note": body.note},
        "notice": "Your correction overrides automated assumptions.",
        "twin": twin,
    }


@app.delete("/api/twins/{customer_id}/corrections")
def clear_corrections(customer_id: str) -> dict:
    db.execute("DELETE FROM corrections WHERE customer_id = ?", (customer_id,))
    return {"cleared": True, "twin": _rebuild_now(customer_id)}


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------
@app.post("/api/events/transaction")
async def post_transaction(body: TransactionIn) -> dict:
    if not twin_engine.load_customer(body.customer_id):
        raise HTTPException(404, f"Unknown customer {body.customer_id}")
    accepted = await event_bus.publish(body)
    return {
        **accepted,
        "customer_id": body.customer_id,
        "status": "queued",
        "message": ("Accepted onto the event queue. Processing is asynchronous - "
                    "poll /api/events/{event_id} or the Twin version."),
    }


@app.get("/api/events/{event_id}")
def get_event(event_id: str) -> dict:
    row = db.query_one(
        "SELECT event_id, customer_id, label, stages_json, total_ms, twin_version, "
        "changed_json, created_at FROM pipeline_trace WHERE event_id = ?",
        (event_id,),
    )
    if not row:
        return {"event_id": event_id, "status": "processing"}
    return {
        "event_id": event_id, "status": "processed",
        "customer_id": row["customer_id"], "label": row["label"],
        "stages": db.loads(row["stages_json"], []), "total_ms": row["total_ms"],
        "twin_version": row["twin_version"], "changed": db.loads(row["changed_json"], []),
        "created_at": row["created_at"],
    }


@app.get("/api/pipeline")
def get_pipeline(limit: int = Query(12, ge=1, le=50)) -> dict:
    return {"queue": event_bus.stats(), "recent": event_bus.recent_traces(limit)}


# --------------------------------------------------------------------------
# Demo actions
# --------------------------------------------------------------------------
async def _inject(customer_id: str, action_key: str, wait: bool) -> dict:
    action = personas.DEMO_ACTIONS.get(action_key)
    if not action:
        raise HTTPException(404, f"Unknown demo action '{action_key}'")
    if not twin_engine.load_customer(customer_id):
        raise HTTPException(404, f"Unknown customer {customer_id}")
    before = twin_engine.load_twin(customer_id) or {}
    txn = TransactionIn(
        customer_id=customer_id, merchant=action["merchant"],
        category=action["category"], amount=action["amount"],
        description=action["description"], channel=action["channel"],
    )
    accepted = await event_bus.publish(txn, label=action["label"])
    response = {
        **accepted,
        "customer_id": customer_id,
        "action": action_key,
        "action_label": action["label"],
        "hint": action["hint"],
        "version_before": before.get("version"),
        "status": "queued",
    }
    if wait:
        await event_bus.drain(timeout=20.0)
        trace = get_event(accepted["event_id"])
        response.update({"status": "processed", "trace": trace,
                         "twin": twin_engine.load_twin(customer_id)})
    return response


@app.post("/api/demo/{customer_id}/first-salary")
async def demo_first_salary(customer_id: str, wait: bool = False) -> dict:
    return await _inject(customer_id, "first-salary", wait)


@app.post("/api/demo/{customer_id}/crib-purchase")
async def demo_crib(customer_id: str, wait: bool = False) -> dict:
    return await _inject(customer_id, "crib-purchase", wait)


@app.post("/api/demo/{customer_id}/large-expense")
async def demo_large_expense(customer_id: str, wait: bool = False) -> dict:
    return await _inject(customer_id, "large-expense", wait)


@app.post("/api/demo/{customer_id}/savings-contribution")
async def demo_savings(customer_id: str, wait: bool = False) -> dict:
    return await _inject(customer_id, "savings-contribution", wait)


@app.post("/api/demo/reset")
async def demo_reset() -> dict:
    """Put the world back to its seeded state, for a second demo run."""
    # Order matters: corrections have to go BEFORE the reseed, because the
    # reseed rebuilds every Twin and would otherwise bake the old corrections
    # straight back into the fresh documents.
    with db.connect() as conn:
        conn.execute("DELETE FROM corrections")
        conn.execute("DELETE FROM pipeline_trace")
    result = await asyncio.to_thread(seed.seed, True)
    return {"reset": True, "seed": result}


# --------------------------------------------------------------------------
# Advisor - the SAME Twin, reprojected. No separate intelligence.
# --------------------------------------------------------------------------
@app.get("/api/advisor/{customer_id}")
def advisor_view(customer_id: str) -> dict:
    twin = _twin_or_404(customer_id)
    customer = twin_engine.load_customer(customer_id)
    history = db.query(
        "SELECT version, change_summary, created_at FROM twin_history "
        "WHERE customer_id = ? ORDER BY version DESC LIMIT 6",
        (customer_id,),
    )

    # Grouped strictly by provenance, so an advisor can never mistake an
    # assumption for something the customer said.
    observed = [
        {"label": "Transactions observed", "value": twin["observed_facts"]["transactions_observed"]},
        {"label": "Months of history", "value": twin["observed_facts"]["months_observed"]},
        {"label": "Monthly income", "value": f"EUR {twin['derived_features']['monthly_income']:,.0f}"},
        {"label": "Monthly spending", "value": f"EUR {twin['derived_features']['monthly_spend']:,.0f}"},
        {"label": "Savings balance", "value": f"EUR {twin['derived_features']['savings_balance']:,.0f}"},
    ]
    declared = [
        {"label": "Age", "value": customer["age"]},
        {"label": "Household", "value": customer["household_type"]},
        {"label": "Children", "value": customer["children"]},
        {"label": "Housing", "value": customer["housing"].replace("_", " ")},
    ] + [
        {**_describe_correction(c), "is_correction": True, "note": c["note"]}
        for c in twin["corrections"]
    ]
    inferred = [
        {"label": s["label"], "confidence": s["score"], "triggered": s["triggered"],
         "suppressed": s["suppressed_by_customer"],
         "evidence": [e["text"] for e in s["evidence"]]}
        for s in twin["signals"] if s["score"] > 0 or s["suppressed_by_customer"]
    ]

    topics: list[dict] = []
    for pb in twin["playbooks"]:
        for topic in pb["conversation_topics"]:
            topics.append({"topic": topic, "from_playbook": pb["name"],
                           "confidence": pb["confidence"]})

    return {
        "customer_id": customer_id,
        # Same document, same version number as /api/twins/{id}. This is the
        # assertion in test 4.
        "twin_version": twin["version"],
        "twin": twin,
        "customer": customer,
        "summary": {
            "name": f"{customer['first_name']} {customer['last_name']}",
            "age": customer["age"],
            "city": customer["city"],
            "life_phase": twin["life_phase"],
            "progress_score": twin["progress_score"],
            "progress_breakdown": twin["progress_breakdown"],
        },
        "observed_facts": observed,
        "customer_declared": declared,
        "inferred_signals": inferred,
        "recent_changes": [dict(r) for r in history],
        "risks": twin["risks"],
        "goals": twin["goals"],
        "timeline": twin["future_timeline"],
        "corrections": twin["corrections"],
        "conversation_topics": topics,
        "advisor_context": [
            {"playbook": pb["name"], "confidence": pb["confidence"],
             "context": pb["advisor_context"]}
            for pb in twin["playbooks"]
        ],
        "guardrail": (
            "This view contains the customer's goals and the confidence behind "
            "every assumption. It deliberately contains no product targets and "
            "no sales prompts. Success here is the customer's progress score, "
            "not what was sold."
        ),
    }


# --------------------------------------------------------------------------
# Scale & cost
# --------------------------------------------------------------------------
@app.get("/api/benchmark")
def get_benchmark() -> dict:
    result = benchmark.latest()
    if not result:
        return JSONResponse(
            status_code=202,
            content={"status": _benchmark_state["status"],
                     "error": _benchmark_state["error"],
                     "message": "Benchmark has not finished yet. Retry shortly."},
        )
    return {"status": "complete", **result}


@app.post("/api/benchmark/run")
async def run_benchmark(customers: int = Query(None, ge=1000, le=1_000_000),
                        events_per_customer: int = Query(None, ge=1, le=60)) -> dict:
    result = await asyncio.to_thread(benchmark.run, customers, events_per_customer)
    _benchmark_state["status"] = "complete"
    return {"status": "complete", **result}


@app.get("/api/cost")
def get_cost() -> dict:
    return benchmark.cost_model()


@app.get("/api/architecture")
def architecture() -> dict:
    """The mapping the Architecture page renders. Kept server-side so the
    story and the running code cannot drift apart."""
    return {
        "tiers": [
            {
                "tier": 1, "name": "Streaming feature updates",
                "hackathon": "asyncio.Queue + one worker coroutine",
                "production": "Kafka topics partitioned by customer_id, Flink operators",
                "what_it_does": ("Folds every transaction into a per-customer feature "
                                 "state. No judgements, only arithmetic."),
                "module": "app/features.py",
            },
            {
                "tier": 2, "name": "Life-event scoring",
                "hackathon": "Weighted interpretable rules with evidence",
                "production": "Same interface; individual models can become trained "
                              "classifiers without changing anything downstream",
                "what_it_does": ("Scores life-moment signals and the life phase, with "
                                 "the evidence and the confidence attached."),
                "module": "app/scoring.py",
            },
            {
                "tier": 3, "name": "Narrative generation",
                "hackathon": "Claude if ANTHROPIC_API_KEY is set, deterministic "
                             "template otherwise",
                "production": "Same, with prompt caching and a template fallback",
                "what_it_does": ("Turns the finished Twin into two or three sentences. "
                                 "Never calculates anything."),
                "module": "app/llm.py",
            },
        ],
        "production_mapping": [
            {"hackathon": "asyncio.Queue", "production": "Kafka"},
            {"hackathon": "Single Python worker", "production": "Flink / Kafka Streams, scaled per partition"},
            {"hackathon": "SQLite features table", "production": "Online feature store"},
            {"hackathon": "SQLite twins table", "production": "Operational store + Twin change topic"},
            {"hackathon": "Single FastAPI process", "production": "Horizontally scaled Twin Service"},
            {"hackathon": "pipeline_trace table", "production": "Platform tracing, metrics and audit log"},
        ],
        "channels": [{"id": c, "label": catalog.CHANNEL_LABELS[c]} for c in catalog.CHANNELS],
        "invariant": ("Events are partitioned by customer, so the per-customer path "
                      "is single-writer and ordered. That is what makes the "
                      "production version scale horizontally without locks."),
    }
