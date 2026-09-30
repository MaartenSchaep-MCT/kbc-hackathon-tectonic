"""TIER 3 - narrative generation.

The LLM's entire job is wording. It receives a small, already-computed summary
of the Twin and turns it into two or three sentences of plain language.

Hard boundaries, enforced by the shape of this module:

  * `_summarise()` is the ONLY thing the model ever sees. It contains numbers
    that Tier 1/2 already computed; the model is never asked to calculate,
    project, or decide anything.
  * If the call fails, times out, or no API key exists, the deterministic
    template runs instead. The demo has no dependency on an external service.
  * It is called on Twin state change or on app open - never per transaction.
    That is the difference between thousands of calls a day and millions.

The template path is not a stub. It is the fallback a bank would actually
ship, and it is good enough that the UI reads correctly without a key.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from . import config, db, twin_engine
from .schemas import Narrative

SYSTEM_PROMPT = (
    "You write short, calm financial summaries for a Belgian retail bank's "
    "mobile app. You are given a customer's already-computed financial state. "
    "Rules, without exception:\n"
    "1. Use only the numbers given. Never calculate, estimate or invent a figure.\n"
    "2. Where a value is marked as an assumption, write it as an assumption "
    "(\"it looks like\", \"we think\") and include the confidence.\n"
    "3. Never congratulate a customer on a life event we only inferred.\n"
    "4. No product names, no selling, no pressure. Talk about their goal.\n"
    "5. Two or three sentences. Plain language. Second person. No emoji, no "
    "headings, no markdown.\n"
    "Return only the sentences."
)


def _summarise(twin: dict) -> dict:
    """The minimal payload handed to the model. Small on purpose: it keeps the
    prompt cheap and makes it obvious the model cannot see anything else."""
    d = twin.get("derived_features", {})
    goals = [
        {
            "goal": g["title"],
            "target_eur": g["target_amount"],
            "current_eur": g["current_amount"],
            "monthly_eur": g["monthly_contribution"],
            "projected": g["projected_completion"],
        }
        for g in twin.get("goals", [])[:3]
    ]
    assumptions = [
        {
            "assumption": s["label"],
            "confidence_pct": round(s["score"] * 100),
            "why": [e["text"] for e in s["evidence"][:3]],
        }
        for s in twin.get("signals", [])
        if s["triggered"] and not s.get("suppressed_by_customer")
    ][:3]
    return {
        "life_phase": twin["life_phase"].get("label") or twin["life_phase"]["value"],
        "life_phase_is_assumption": twin["life_phase"]["provenance"] == "inferred",
        "life_phase_confidence_pct": round(twin["life_phase"]["confidence"] * 100),
        "monthly_income_eur": d.get("monthly_income"),
        "monthly_surplus_eur": d.get("monthly_surplus"),
        "income_trend": d.get("income_trend"),
        "buffer_months": d.get("emergency_fund_months"),
        "goals": goals,
        "assumptions_we_are_making": assumptions,
        "progress_score_pct": round(twin.get("progress_score", 0) * 100),
        "customer_corrections_in_force": [c["field"] for c in twin.get("corrections", [])],
        "what_just_changed": twin.get("change_summary", ""),
    }


# --------------------------------------------------------------------------
# Deterministic fallback. Used whenever there is no API key.
# --------------------------------------------------------------------------
def _template(twin: dict) -> Narrative:
    s = _summarise(twin)
    phase = s["life_phase"]
    parts: list[str] = []

    if s["life_phase_is_assumption"]:
        parts.append(
            f"Your transactions look like '{phase.lower()}' - we are "
            f"{s['life_phase_confidence_pct']}% confident, so treat it as our "
            f"reading rather than a fact."
        )
    else:
        parts.append(f"You told us you are {phase.lower()}, so we plan around that.")

    trend = s["income_trend"]
    surplus = s["monthly_surplus_eur"] or 0
    if trend == "rising":
        parts.append(
            f"Your income has been rising and you currently keep about "
            f"EUR {surplus:,.0f} a month."
        )
    elif surplus < 0:
        parts.append(
            f"Right now you are spending about EUR {abs(surplus):,.0f} a month "
            f"more than comes in, so the nearer target matters more than the long one."
        )
    else:
        parts.append(
            f"Your income is {trend} and about EUR {surplus:,.0f} a month is left over."
        )

    if s["goals"]:
        g = s["goals"][0]
        if g["projected"] == "reached":
            parts.append(f"Your {g['goal'].lower()} of EUR {g['target_eur']:,.0f} is in place.")
        elif g["projected"]:
            parts.append(
                f"At EUR {g['monthly_eur']:,.0f} a month you reach your "
                f"{g['goal'].lower()} of EUR {g['target_eur']:,.0f} around "
                f"{g['projected']} - you are at EUR {g['current_eur']:,.0f} today."
            )
        else:
            parts.append(
                f"Your {g['goal'].lower()} needs EUR {g['target_eur']:,.0f} and has "
                f"no monthly amount behind it yet."
            )

    if s["customer_corrections_in_force"]:
        parts.append("Your own corrections are being applied on top of all of this.")

    headline = {
        "student": "Building the habit early",
        "first_job": "Your income just became predictable",
        "establishing": "Steady ground to build on",
        "family_building": "Planning around a growing household",
        "family_established": "Family life, planned for",
        "pre_retirement": "The retirement picture is now concrete",
        "retired": "Making your capital last",
    }.get(twin["life_phase"]["value"], "Where you stand")

    return Narrative(
        headline=headline, body=" ".join(parts), generator="template",
        model=None, generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# --------------------------------------------------------------------------
# Claude path
# --------------------------------------------------------------------------
def _claude(twin: dict) -> Narrative | None:
    """Returns None on any failure - the caller then uses the template."""
    try:
        import anthropic
    except ImportError:
        return None

    import json

    summary = _summarise(twin)
    try:
        client = anthropic.Anthropic(
            api_key=config.ANTHROPIC_API_KEY, timeout=config.LLM_TIMEOUT_SECONDS,
            max_retries=1,
        )
        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=2000,
            # Short wording task: the cheapest effort level is the right one.
            output_config={"effort": "low"},
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    "Write the summary for this customer.\n\n"
                    + json.dumps(summary, ensure_ascii=False, indent=2)
                ),
            }],
        )
        if getattr(response, "stop_reason", None) == "refusal":
            return None
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()
        if not text:
            return None
        fallback = _template(twin)
        return Narrative(
            headline=fallback.headline, body=text, generator="claude",
            model=config.LLM_MODEL,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    except Exception as exc:                         # never break the demo
        print(f"[llm] Claude call failed, using template: {exc!r}")
        return None


def generate(twin: dict) -> Narrative:
    """Synchronous narrative generation with a guaranteed result."""
    if config.LLM_ENABLED:
        narrative = _claude(twin)
        if narrative is not None:
            return narrative
        degraded = _template(twin)
        degraded.degraded = True          # UI shows "template (Claude unavailable)"
        return degraded
    return _template(twin)


async def refresh_narrative(customer_id: str, reason: str = "") -> dict | None:
    """Regenerate and persist the narrative for one customer.

    Called on Twin state change (from the event worker) and on app open.
    Never per transaction - see the module docstring.
    """
    twin = twin_engine.load_twin(customer_id)
    if not twin:
        return None
    narrative = await asyncio.to_thread(generate, twin)
    twin["narrative"] = narrative.model_dump()
    twin["narrative"]["trigger"] = reason or "state_change"
    db.execute(
        "UPDATE twins SET twin_json = ? WHERE customer_id = ?",
        (db.dumps(twin), customer_id),
    )
    return twin["narrative"]


def status() -> dict:
    return {
        "tier3_enabled": config.LLM_ENABLED,
        "generator": "claude" if config.LLM_ENABLED else "template",
        "model": config.LLM_MODEL if config.LLM_ENABLED else None,
        "note": (
            "ANTHROPIC_API_KEY is set: narratives are written by Claude, with the "
            "deterministic template as the automatic fallback on any failure."
            if config.LLM_ENABLED else
            "No ANTHROPIC_API_KEY set: narratives come from the deterministic "
            "template. Every number in the app is computed by Tier 1/2 either "
            "way, so nothing else changes."
        ),
        "called_when": ["Twin changes state", "Customer opens the experience"],
        "never_called_for": ["Individual transactions", "Any financial calculation"],
    }
