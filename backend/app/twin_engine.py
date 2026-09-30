"""THE TWIN ENGINE - deterministic source of truth.

Takes Tier 1 features + Tier 2 scores + customer corrections and produces one
`FinancialTwin`. Every number in the Twin is computed here, in plain Python.
The LLM (Tier 3) is handed the finished Twin and may only choose words.

Order of authority, highest first:
    1. customer corrections   (declared)
    2. observed transactions  (observed)
    3. derived arithmetic     (derived)
    4. Tier 2 scores          (inferred)

A correction never just hides a signal - it is recorded, shown, and explained.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

from . import config, db, features, playbooks, scoring
from .schemas import (
    ActivePlaybook, Correction, Evidence, Explanation, FinancialTwin, Goal,
    Household, Inference, Intent, Milestone, NextBestAction, PossibleChange,
    Risk, Signal,
)

# --- simplified retirement assumptions --------------------------------------
# Every one of these is surfaced in the UI as an assumption, with its value, so
# a customer or an advisor can see exactly what the projection rests on. They
# are planning conventions, not KBC figures and not regulatory advice.
TARGET_INCOME_REPLACEMENT = 0.75      # of pre-retirement income: the common
                                      # planning convention. Using today's bare
                                      # consumption instead would understate the
                                      # target for anyone whose costs will rise.
STATUTORY_REPLACEMENT_RATE = 0.40     # share of income from the state pension
STATUTORY_PENSION_CAP = 2000.0        # EUR/month, simplified ceiling
YEARS_IN_RETIREMENT = 20
DEFAULT_RETIREMENT_AGE = 65

BUFFER_TARGET_MONTHS = 3.0

DRIVING_LESSONS_AGE = 17              # Belgian learner's permit
DRIVING_EXAM_AGE = 18                 # Belgian practical driving exam


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reference_date() -> date:
    return date.fromisoformat(config.REFERENCE_DATE)


def _add_months(start: date, months: int) -> date:
    total = (start.year * 12 + start.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def _ev(items: list[dict]) -> list[Evidence]:
    return [Evidence(**e) for e in items]


# --------------------------------------------------------------------------
# Corrections
# --------------------------------------------------------------------------
def load_corrections(customer_id: str) -> tuple[dict, list[Correction]]:
    """Latest value per field, plus the full list for display."""
    rows = db.query(
        "SELECT field, value_json, note, created_at FROM corrections "
        "WHERE customer_id = ? ORDER BY created_at ASC, id ASC",
        (customer_id,),
    )
    latest: dict = {}
    listed: list[Correction] = []
    for row in rows:
        value = db.loads(row["value_json"])
        latest[row["field"]] = value
        listed.append(
            Correction(field=row["field"], value=value, note=row["note"],
                       created_at=row["created_at"])
        )
    # Most recent first for the UI.
    listed.reverse()
    deduped: list[Correction] = []
    seen: set[str] = set()
    for c in listed:
        if c.field not in seen:
            seen.add(c.field)
            deduped.append(c)
    return latest, deduped


# --------------------------------------------------------------------------
# Goals
# --------------------------------------------------------------------------
# Goals that go into the plan automatically for a stage of life, without the
# customer having to ask. They can remove any of them, and add their own.
STAGE_GOALS: list[tuple] = [
    # In Belgium you can start learning to drive at 17 and take the practical
    # exam at 18, so the money for lessons is needed by 17.
    (lambda c: c["age"] < 18,
     playbooks.GoalTemplate(
         id="driving_licence", title="Driving licence",
         target_rule="lessons and exams, about EUR 1,500",
         target_fixed=1500.0, priority=1, deadline_age=DRIVING_LESSONS_AGE,
         explanation=(f"Lessons start at {DRIVING_LESSONS_AGE}, the practical exam is at "
                      f"{DRIVING_EXAM_AGE}. Together they usually cost around EUR 1,500."),
     )),
    (lambda c: (20 <= c["age"] <= 45
                and c["housing"] in ("renting", "living_with_parents")
                and c.get("mortgage_monthly", 0) == 0),
     playbooks.GoalTemplate(
         id="house_deposit", title="Home deposit",
         target_rule="a EUR 50,000 deposit and costs",
         target_fixed=50000.0, priority=2,
         explanation="A working figure for deposit plus registration costs.",
     )),
]

# Presets the app offers under "Add a goal". The customer can also type their own.
CUSTOM_GOAL_PRIORITY = 3


def _is_removed(gid: str, corrections: dict) -> bool:
    if corrections.get(f"goal_removed:{gid}") is True:
        return True
    return gid == "house_deposit" and corrections.get("plans_to_buy_house") is False


def _goal_target(template: playbooks.GoalTemplate, ctx: dict) -> float:
    if template.target_fixed:
        return float(template.target_fixed)
    if template.target_months_of_spend:
        # A buffer has to cover the cost base you will actually carry. Someone
        # who just started earning still has an artificially low spend, so we
        # floor the basis at half their current income.
        basis = max(
            ctx.get("monthly_spend_core", ctx.get("monthly_spend", 0.0)),
            0.5 * ctx.get("income_basis", ctx.get("monthly_income", 0.0)),
            600.0,
        )
        return round(template.target_months_of_spend * basis, -1)
    if template.target_multiple_of_income:
        return round(template.target_multiple_of_income * ctx.get("monthly_income", 0.0), -1)
    return 0.0


def _retirement_projection(ctx: dict, corrections: dict) -> dict:
    """Simplified, fully explainable pension projection."""
    age = ctx["age"]
    target_age = int(corrections.get("target_retirement_age") or DEFAULT_RETIREMENT_AGE)
    years_left = max(0, target_age - age)
    # Basis: the income the customer is on now, not a trailing average that a
    # recent job change still drags down.
    income_basis = max(ctx.get("income_basis", 0.0), ctx.get("monthly_income", 0.0))
    # Target income: the planning convention, floored at what they actually
    # spend today - whichever is higher.
    desired_monthly = max(
        TARGET_INCOME_REPLACEMENT * income_basis,
        ctx.get("monthly_spend_core", ctx.get("monthly_spend", 0.0)),
        800.0,
    )
    statutory = min(STATUTORY_PENSION_CAP, STATUTORY_REPLACEMENT_RATE * income_basis)
    monthly_gap = max(0.0, desired_monthly - statutory)
    capital_needed = monthly_gap * 12 * YEARS_IN_RETIREMENT
    monthly_saving = ctx.get("monthly_savings_contribution", 0.0)
    projected_capital = ctx.get("savings_balance", 0.0) + monthly_saving * 12 * years_left
    readiness = min(1.0, projected_capital / capital_needed) if capital_needed > 0 else 1.0
    return {
        "target_retirement_age": target_age,
        "retirement_age_source": "declared" if corrections.get("target_retirement_age") else "assumed",
        "years_to_retirement": years_left,
        "desired_monthly_income": round(desired_monthly, 2),
        "estimated_statutory_pension": round(statutory, 2),
        "monthly_income_gap": round(monthly_gap, 2),
        "capital_needed": round(capital_needed, 2),
        "projected_capital": round(projected_capital, 2),
        "projected_shortfall": round(max(0.0, capital_needed - projected_capital), 2),
        "readiness": round(readiness, 4),
        "retirement_year": reference_date().year + years_left,
        "income_basis": round(income_basis, 2),
        "assumptions": [
            f"Target retirement income of {int(TARGET_INCOME_REPLACEMENT * 100)}% of your "
            f"current income (EUR {desired_monthly:,.0f}/month), floored at what you spend today",
            f"State pension estimated at {int(STATUTORY_REPLACEMENT_RATE * 100)}% of current "
            f"income, capped at EUR {STATUTORY_PENSION_CAP:,.0f}/month",
            f"{YEARS_IN_RETIREMENT} years of retirement",
            "No investment return assumed - your contributions only, so the "
            "projection is deliberately conservative",
        ],
    }


def _build_goals(active: list[tuple[playbooks.Playbook, float]], ctx: dict,
                 corrections: dict, retirement: dict) -> list[Goal]:
    """Collect goal templates from active playbooks, dedupe, then allocate the
    customer's actual savings and monthly contribution across them."""
    templates: dict[str, tuple[playbooks.GoalTemplate, str]] = {}
    sources: dict[str, str] = {}
    for pb, _conf in active:
        for tpl in pb.goals:
            if tpl.id not in templates or tpl.priority < templates[tpl.id][0].priority:
                templates[tpl.id] = (tpl, pb.name)
                sources[tpl.id] = "detected"

    for applies, tpl in STAGE_GOALS:
        if tpl.id not in templates and applies(ctx):
            templates[tpl.id] = (tpl, "Usual at your stage of life")
            sources[tpl.id] = "stage"

    # Goals the customer added themselves: custom_goal:<id> = {title, target_amount}.
    for field_name, value in corrections.items():
        if field_name.startswith("custom_goal:") and isinstance(value, dict):
            gid = field_name.split(":", 1)[1]
            templates[gid] = (playbooks.GoalTemplate(
                id=gid, title=str(value.get("title") or "My goal"),
                target_rule="set by you",
                target_fixed=float(value.get("target_amount") or 0),
                priority=CUSTOM_GOAL_PRIORITY,
                explanation="You added this goal yourself.",
            ), "You added this")
            sources[gid] = "custom"

    templates = {gid: v for gid, v in templates.items() if not _is_removed(gid, corrections)}
    # A teenager's pocket money should go to their own goals, not to an adult
    # emergency buffer.
    if ctx["age"] < 18:
        templates = {gid: v for gid, v in templates.items() if v[0].group != "buffer"}

    # Collapse alternatives. Three playbooks each asking for "a buffer" must
    # not become three goals splitting one pot of savings between them.
    by_group: dict[str, str] = {}
    for gid, (tpl, _origin) in templates.items():
        if not tpl.group:
            continue
        held = by_group.get(tpl.group)
        if held is None or tpl.priority < templates[held][0].priority:
            by_group[tpl.group] = gid
    keep = {gid for gid, (tpl, _) in templates.items()
            if not tpl.group or by_group.get(tpl.group) == gid}
    templates = {gid: v for gid, v in templates.items() if gid in keep}

    goals: list[Goal] = []
    for gid, (tpl, origin) in templates.items():
        if gid == "retirement_readiness":
            target = retirement["capital_needed"]
        else:
            target = _goal_target(tpl, ctx)
        override = corrections.get(f"goal_target:{gid}")
        source = sources.get(gid, "detected")
        provenance = {"stage": "inferred", "custom": "declared"}.get(source, "derived")
        explanation = tpl.explanation or tpl.target_rule
        if override:
            target = float(override)
            provenance = "declared"
            explanation = "You set this target yourself."
        if target <= 0:
            continue
        deadline = deadline_months = None
        if tpl.deadline_age and ctx["age"] < tpl.deadline_age:
            deadline_months = (tpl.deadline_age - ctx["age"]) * 12
            deadline = _add_months(reference_date(), deadline_months).strftime("%B %Y")
        goals.append(
            Goal(
                id=gid, title=tpl.title, target_amount=round(target, 2),
                current_amount=0.0, monthly_contribution=0.0,
                priority=tpl.priority, provenance=provenance, origin=origin,
                explanation=explanation, source=source,
                deadline=deadline, deadline_months=deadline_months,
            )
        )

    # Stable order: priority, then the group-less long-horizon goals last, then
    # id, so the savings waterfall is deterministic run to run.
    goals.sort(key=lambda g: (g.priority, g.id))

    # Waterfall the real savings balance into goals by priority. One pot of
    # money, so we never show the same euro as progress on two goals.
    remaining = ctx.get("savings_balance", 0.0)
    for goal in goals:
        allocated = min(remaining, goal.target_amount)
        goal.current_amount = round(allocated, 2)
        remaining -= allocated

    # Split the monthly contribution across incomplete goals by inverse priority.
    monthly_pot = ctx.get("monthly_savings_contribution", 0.0)
    incomplete = [g for g in goals
                  if g.current_amount < g.target_amount and g.id != "retirement_readiness"]
    weight_total = sum(1.0 / g.priority for g in incomplete) or 1.0
    today = reference_date()
    for goal in goals:
        # Retirement capital is not "done when the contributions arrive" - it
        # is needed by a fixed date. Projecting a completion month past the
        # retirement year would be nonsense, so we report the gap instead.
        if goal.id == "retirement_readiness":
            months = max(1, retirement["years_to_retirement"] * 12)
            share_pot = ctx.get("monthly_savings_contribution", 0.0)
            goal.monthly_contribution = round(share_pot, 2)
            goal.months_remaining = months
            goal.projected_completion = str(retirement["retirement_year"])
            goal.on_track = retirement["projected_shortfall"] <= 0
            goal.explanation = (
                f"Needed by {retirement['retirement_year']}. On your current "
                f"contribution the projection reaches EUR "
                f"{retirement['projected_capital']:,.0f} of EUR "
                f"{retirement['capital_needed']:,.0f}."
            )
            continue
        if goal.current_amount >= goal.target_amount:
            goal.monthly_contribution = 0.0
            goal.months_remaining = 0
            goal.projected_completion = "reached"
            goal.on_track = True
            continue
        if goal.id == "retirement_readiness":
            continue
        share = (1.0 / goal.priority) / weight_total
        goal.monthly_contribution = round(monthly_pot * share, 2)
        gap = goal.target_amount - goal.current_amount
        if goal.monthly_contribution > 0:
            months = math.ceil(gap / goal.monthly_contribution)
            months = min(months, 600)
            goal.months_remaining = months
            eta = _add_months(today, months)
            goal.projected_completion = eta.strftime("%B %Y")
            goal.on_track = months <= (goal.deadline_months or 120)
        else:
            goal.months_remaining = None
            goal.projected_completion = None
            goal.on_track = False
    return goals


# --------------------------------------------------------------------------
# Timeline
# --------------------------------------------------------------------------
def _build_timeline(ctx: dict, customer: dict, goals: list[Goal],
                    active: list[tuple[playbooks.Playbook, float]],
                    signals_by_id: dict[str, dict], corrections: dict,
                    retirement: dict) -> list[Milestone]:
    today = reference_date()
    out: list[Milestone] = []
    active_ids = {pb.id for pb, _ in active}

    # Only call it a *first* salary when the history is genuinely short. For a
    # long career this date is just the edge of our data window, and printing
    # it as a life milestone would be a plain falsehood.
    first_salary = ctx.get("first_salary_month") or ""
    if first_salary and ctx.get("salary_detected") and ctx.get("salary_months_total", 0) <= 8:
        out.append(Milestone(
            year=int(first_salary[:4]), date_label=first_salary,
            title="First recurring salary",
            detail=(f"EUR {ctx.get('salary_latest_amount', 0):,.0f} per month, "
                    f"{ctx.get('salary_months_consecutive', 0)} consecutive months observed"),
            kind="achieved", confidence=1.0, provenance="observed",
        ))

    if ctx.get("rent_monthly", 0) > 0:
        out.append(Milestone(
            year=today.year, date_label=str(today.year),
            title="Living independently",
            detail=f"Rent of EUR {ctx['rent_monthly']:,.0f} per month",
            kind="achieved", confidence=1.0, provenance="observed",
        ))

    if ctx.get("mortgage_monthly", 0) > 0:
        out.append(Milestone(
            year=today.year, date_label=str(today.year),
            title="Home owner",
            detail=f"Mortgage of EUR {ctx['mortgage_monthly']:,.0f} per month",
            kind="achieved", confidence=1.0, provenance="observed",
        ))

    for goal in goals:
        if goal.id == "retirement_readiness":
            continue                      # covered by the retirement milestone
        if goal.projected_completion in (None, "reached"):
            if goal.projected_completion == "reached":
                out.append(Milestone(
                    year=today.year, date_label=str(today.year),
                    title=f"{goal.title} reached",
                    detail=f"EUR {goal.target_amount:,.0f} in place",
                    kind="achieved", confidence=1.0, provenance="derived",
                    goal_id=goal.id,
                ))
            continue
        eta = _add_months(today, goal.months_remaining or 0)
        out.append(Milestone(
            year=eta.year, date_label=goal.projected_completion,
            title=f"{goal.title}: EUR {goal.target_amount:,.0f}",
            detail=(f"At EUR {goal.monthly_contribution:,.0f} per month "
                    f"from EUR {goal.current_amount:,.0f} today"),
            kind="in_progress" if goal.on_track else "projected",
            confidence=0.85 if goal.on_track else 0.5,
            provenance="derived", goal_id=goal.id,
        ))

    # Uncertain life events are drawn as such - confidence carried onto the dot.
    baby = signals_by_id.get("possible_family_expansion")
    if baby and baby["triggered"] and not baby.get("suppressed_by_customer"):
        out.append(Milestone(
            year=today.year + 1, date_label=f"~{today.year + 1}",
            title="Possible family expansion",
            detail=f"{round(baby['score'] * 100)}% confidence - an assumption, not a fact",
            kind="life_event", confidence=baby["score"], provenance="inferred",
        ))
        out.append(Milestone(
            year=today.year + 1, date_label=f"~{today.year + 1}",
            title="Childcare costs begin",
            detail="Around EUR 450 per month enters the projection",
            kind="projected", confidence=baby["score"], provenance="inferred",
        ))

    if "first_home" in active_ids:
        deposit = next((g for g in goals if g.id == "house_deposit"), None)
        if deposit and deposit.months_remaining:
            eta = _add_months(today, deposit.months_remaining)
            out.append(Milestone(
                year=eta.year, date_label=str(eta.year),
                title="Deposit ready for a first home",
                detail="An assumption about your plans - you can switch this off",
                kind="projected", confidence=0.6, provenance="inferred",
                goal_id="house_deposit",
            ))

    if any(g.id == "driving_licence" for g in goals) and ctx["age"] < DRIVING_EXAM_AGE:
        exam = _add_months(today, (DRIVING_EXAM_AGE - ctx["age"]) * 12)
        out.append(Milestone(
            year=exam.year, date_label=exam.strftime("%B %Y"),
            title=f"Driving exam at {DRIVING_EXAM_AGE}",
            detail=(f"Learn to drive from {DRIVING_LESSONS_AGE}, "
                    f"take the practical exam at {DRIVING_EXAM_AGE}"),
            kind="projected", confidence=1.0, provenance="derived",
        ))

    # Retirement is not a useful line on a teenager's timeline.
    if ctx["age"] < 18:
        out.sort(key=lambda m: (m.year, 0 if m.kind == "achieved" else 1))
        return out

    out.append(Milestone(
        year=retirement["retirement_year"], date_label=str(retirement["retirement_year"]),
        title=f"Retirement at {retirement['target_retirement_age']}",
        detail=(
            f"Projected shortfall EUR {retirement['projected_shortfall']:,.0f}"
            if retirement["projected_shortfall"] > 0
            else "Projection currently covers your target income"
        ),
        kind="projected",
        confidence=1.0 if retirement["retirement_age_source"] == "declared" else 0.7,
        provenance="declared" if retirement["retirement_age_source"] == "declared" else "derived",
    ))

    out.sort(key=lambda m: (m.year, 0 if m.kind == "achieved" else 1))
    return out


# --------------------------------------------------------------------------
# Progress score - the success metric. Deliberately not about product sales.
# --------------------------------------------------------------------------
def _progress_score(ctx: dict, goals: list[Goal]) -> tuple[float, dict[str, float]]:
    if goals:
        weights = [1.0 / g.priority for g in goals]
        goal_progress = sum(g.progress * w for g, w in zip(goals, weights)) / sum(weights)
    else:
        goal_progress = 0.0
    # Measure the buffer against the same basis the goal uses, so the headline
    # number and the goal card can never disagree.
    basis = max(ctx.get("monthly_spend_core", ctx.get("monthly_spend", 0.0)),
                0.5 * ctx.get("income_basis", ctx.get("monthly_income", 0.0)), 600.0)
    buffer_health = min(1.0, ctx.get("savings_balance", 0.0)
                        / (BUFFER_TARGET_MONTHS * basis)) if basis else 0.0
    contribution_rate = (ctx.get("monthly_savings_contribution", 0.0)
                         / max(ctx.get("monthly_income", 0.0), 1.0))
    savings_health = min(1.0, max(0.0, contribution_rate) / 0.20)
    trajectory = 0.0
    income = max(ctx.get("monthly_income", 0.0), 1.0)
    if ctx.get("monthly_surplus", 0.0) >= 0.10 * income:
        trajectory += 0.5
    elif ctx.get("monthly_surplus", 0.0) > 0:
        trajectory += 0.25
    if ctx.get("income_trend") in ("stable", "rising"):
        trajectory += 0.25
    if ctx.get("spend_trend") in ("stable", "falling"):
        trajectory += 0.25
    breakdown = {
        "goal_progress": round(goal_progress, 4),
        "buffer_health": round(buffer_health, 4),
        "savings_health": round(savings_health, 4),
        "trajectory": round(trajectory, 4),
    }
    score = (0.60 * goal_progress + 0.15 * buffer_health
             + 0.10 * savings_health + 0.15 * trajectory)
    return round(min(1.0, score), 4), breakdown


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------
def build_twin(customer: dict, feature_state: dict, previous: dict | None = None,
               narrative: dict | None = None) -> FinancialTwin:
    derived = feature_state.get("derived") or features.recompute_derived(feature_state)
    corrections_map, corrections_list = load_corrections(customer["customer_id"])
    ctx = scoring.build_context(derived, customer)

    signal_results, phase_results = scoring.score_all(ctx)
    signals_by_id = {s["id"]: s for s in signal_results}

    # --- corrections: suppress inferences the customer has rejected --------
    suppression_notes: list[str] = []
    for sig in signal_results:
        field = sig.get("corrigible_by")
        if field and corrections_map.get(field) is False:
            sig["suppressed_by_customer"] = True
            sig["triggered"] = False
            suppression_notes.append(
                f"'{sig['label']}' is switched off because you told us it is wrong."
            )

    # --- life phase --------------------------------------------------------
    best = phase_results[0]
    phase_value, phase_conf = best["id"], best["score"]
    phase_evidence = _ev(best["evidence"])
    phase_provenance = "inferred"
    phase_source = "twin_engine.tier2"

    declared_phase = corrections_map.get("life_phase")
    if declared_phase:
        phase_value = declared_phase
        phase_conf = 1.0
        phase_provenance = "declared"
        phase_source = "customer_correction"
        phase_evidence = [Evidence(
            text="You told us this is your situation. This overrides our inference.",
            weight=1.0, provenance="declared",
        )]

    life_phase = Inference(
        value=phase_value,
        confidence=round(phase_conf, 4),
        provenance=phase_provenance,
        evidence=phase_evidence,
        source=phase_source,
        timestamp=_now(),
        label=scoring.LIFE_PHASE_LABELS.get(phase_value, phase_value.replace("_", " ").title()),
    )

    # --- household --------------------------------------------------------
    possible_changes: list[PossibleChange] = []
    baby = signals_by_id.get("possible_family_expansion")
    if baby and baby["score"] >= 0.35 and not baby["suppressed_by_customer"]:
        possible_changes.append(PossibleChange(
            key="family_expansion",
            label="Possible family expansion",
            confidence=baby["score"],
            evidence=_ev(baby["evidence"]),
            expected_financial_impact=(
                "Childcare of roughly EUR 450 per month, and a household that "
                "may temporarily run on less income"
            ),
        ))
    merge = signals_by_id.get("household_merge")
    if merge and merge["triggered"]:
        possible_changes.append(PossibleChange(
            key="household_merge", label="Household finances merging",
            confidence=merge["score"], evidence=_ev(merge["evidence"]),
            expected_financial_impact="Shared goals rather than two separate plans",
        ))

    household = Household(
        type=corrections_map.get("household_type") or customer.get("household_type", "single"),
        type_provenance="declared",
        children=int(corrections_map.get("children", customer.get("children", 0))),
        partner_name=customer.get("partner_name"),
        housing=customer.get("housing", "unknown"),
        possible_changes=possible_changes,
    )

    # --- playbooks --------------------------------------------------------
    active: list[tuple[playbooks.Playbook, float]] = []
    for sig in signal_results:
        for pb in playbooks.BY_SIGNAL.get(sig["id"], []):
            removed_all_goals = pb.goals and all(
                _is_removed(g.id, corrections_map) for g in pb.goals)
            if (pb.suppressed_by and corrections_map.get(pb.suppressed_by) is False) or removed_all_goals:
                suppression_notes.append(
                    f"The '{pb.name}' guidance is switched off at your request."
                )
                continue
            if sig["score"] >= pb.min_confidence and not sig["suppressed_by_customer"]:
                active.append((pb, sig["score"]))
    active.sort(key=lambda t: -t[1])

    retirement = _retirement_projection(ctx, corrections_map)
    goals = _build_goals(active, ctx, corrections_map, retirement)
    goal_ids = {g.id for g in goals}

    active_playbooks: list[ActivePlaybook] = []
    for pb, conf in active:
        pct = round(conf * 100)
        active_playbooks.append(ActivePlaybook(
            id=pb.id, name=pb.name, confidence=round(conf, 4),
            customer_explanation=pb.customer_explanation.format(confidence_pct=pct),
            advisor_context=pb.advisor_context.format(confidence_pct=pct),
            conversation_topics=list(pb.conversation_topics),
            actions=[
                NextBestAction(
                    id=a.id, title=a.title, why=a.why,
                    goal_id=a.goal_id if a.goal_id in goal_ids else None,
                    effort=a.effort, customer_benefit=a.customer_benefit,
                )
                for a in pb.actions
            ],
        ))

    # --- risks ------------------------------------------------------------
    risks: list[Risk] = []
    buffer_months = ctx.get("emergency_fund_months", 0.0)
    if buffer_months < scoring.THRESHOLDS["emergency_fund_thin_months"]:
        risks.append(Risk(
            id="thin_buffer", label="Emergency buffer is thin",
            severity="high" if buffer_months < 1 else "medium",
            confidence=1.0, provenance="derived",
            evidence=[Evidence(
                text=f"Savings cover {buffer_months} months of spending "
                     f"(guideline: {BUFFER_TARGET_MONTHS:.0f})",
                provenance="derived")],
            mitigation="A small automatic monthly transfer closes this fastest.",
        ))
    if ctx.get("monthly_surplus", 0.0) < 0:
        risks.append(Risk(
            id="negative_cashflow", label="Spending exceeds income",
            severity="high", confidence=1.0, provenance="derived",
            evidence=[Evidence(
                text=f"Average monthly shortfall of EUR {abs(ctx['monthly_surplus']):,.0f}",
                provenance="derived")],
            mitigation="Recurring payments are the largest controllable block.",
        ))
    if retirement["projected_shortfall"] > 0 and ctx["age"] >= 45:
        risks.append(Risk(
            id="pension_gap", label="Projected retirement income gap",
            severity="medium", confidence=0.7, provenance="derived",
            evidence=[Evidence(
                text=(f"Projected shortfall of EUR {retirement['projected_shortfall']:,.0f} "
                      f"by age {retirement['target_retirement_age']}"),
                provenance="derived")],
            mitigation="The monthly contribution is the most direct lever.",
        ))
    if ctx.get("housing_cost_monthly", 0) > 0.40 * max(ctx.get("monthly_income", 1), 1):
        risks.append(Risk(
            id="housing_heavy", label="Housing takes a large share of income",
            severity="medium", confidence=1.0, provenance="derived",
            evidence=[Evidence(
                text=(f"Housing is EUR {ctx['housing_cost_monthly']:,.0f} of "
                      f"EUR {ctx['monthly_income']:,.0f} monthly income"),
                provenance="derived")],
            mitigation="Worth keeping the buffer target aligned to the fixed costs.",
        ))

    # --- intent ----------------------------------------------------------
    intent: list[Intent] = []
    for sig_id, horizon in (("first_home_intent", "long_term"),
                            ("building_emergency_savings", "short_term"),
                            ("renovation", "short_term"),
                            ("nearing_retirement", "long_term"),
                            ("moving_out", "short_term")):
        sig = signals_by_id.get(sig_id)
        if sig and sig["triggered"] and not sig["suppressed_by_customer"]:
            intent.append(Intent(
                id=sig_id, label=sig["label"], horizon=horizon,
                confidence=sig["score"], evidence=_ev(sig["evidence"]),
            ))

    timeline = _build_timeline(ctx, customer, goals, active, signals_by_id,
                               corrections_map, retirement)
    progress_score, breakdown = _progress_score(ctx, goals)

    # --- explanations ("Why we think this") -------------------------------
    explanations: list[Explanation] = [
        Explanation(
            field="life_phase",
            headline=f"Why we think you are '{life_phase.label}'",
            reasons=[e.text for e in life_phase.evidence],
            provenance=life_phase.provenance,
            confidence=life_phase.confidence,
            correctable=True,
        )
    ]
    runner_up = phase_results[1] if len(phase_results) > 1 else None
    if runner_up and runner_up["score"] > 0.2 and not declared_phase:
        explanations[0].reasons.append(
            f"Next most likely: {runner_up['label']} "
            f"({round(runner_up['score'] * 100)}%) - so this is a judgement, not a certainty."
        )
    for sig in signal_results:
        if sig["triggered"] or sig["suppressed_by_customer"]:
            explanations.append(Explanation(
                field=f"signal:{sig['id']}",
                headline=f"Why we flagged '{sig['label']}'",
                reasons=([e["text"] for e in sig["evidence"]]
                         + ([sig["uncertainty_note"]] if sig["uncertainty_note"] else [])),
                provenance="declared" if sig["suppressed_by_customer"] else "inferred",
                confidence=sig["score"],
                correctable=bool(sig.get("corrigible_by")),
            ))
    for note in suppression_notes:
        explanations.append(Explanation(
            field="corrections", headline="Your correction is being applied",
            reasons=[note], provenance="declared", confidence=1.0, correctable=False,
        ))

    observed_facts = {
        "age": customer.get("age"),
        "household_type": customer.get("household_type"),
        "children_declared": customer.get("children"),
        "partner_name": customer.get("partner_name"),
        "housing": customer.get("housing"),
        "employer": customer.get("employer"),
        "city": customer.get("city"),
        "transactions_observed": derived.get("txn_count", 0),
        "months_observed": derived.get("months_observed", 0),
        "savings_balance": derived.get("savings_balance", 0.0),
        "monthly_income": derived.get("monthly_income", 0.0),
        "monthly_spend": derived.get("monthly_spend", 0.0),
    }

    twin = FinancialTwin(
        customer_id=customer["customer_id"],
        version=(previous or {}).get("version", 0) + 1,
        life_phase=life_phase,
        household=household,
        goals=goals,
        risks=risks,
        intent=intent,
        signals=[Signal(
            id=s["id"], label=s["label"], score=s["score"], threshold=s["threshold"],
            triggered=s["triggered"], evidence=_ev(s["evidence"]),
            suppressed_by_customer=s["suppressed_by_customer"],
        ) for s in signal_results],
        future_timeline=timeline,
        playbooks=active_playbooks,
        progress_score=progress_score,
        progress_breakdown=breakdown,
        explanations=explanations,
        corrections=corrections_list,
        observed_facts=observed_facts,
        derived_features={**derived, "retirement": retirement},
        last_updated=_now(),
    )

    summary, changed = diff_twin(previous, twin)
    twin.change_summary = summary
    twin.changed_fields = changed
    if narrative:
        from .schemas import Narrative
        twin.narrative = Narrative(**narrative)
    return twin


# --------------------------------------------------------------------------
# Change detection - drives the "what just changed" UI and the LLM trigger
# --------------------------------------------------------------------------
def diff_twin(previous: dict | None, current: FinancialTwin) -> tuple[str, list[str]]:
    if not previous:
        return "Financial Twin created", ["created"]

    changed: list[str] = []
    notes: list[str] = []

    prev_phase = (previous.get("life_phase") or {}).get("value")
    if prev_phase != current.life_phase.value:
        changed.append("life_phase")
        notes.append(
            f"Life phase changed from "
            f"{scoring.LIFE_PHASE_LABELS.get(prev_phase, prev_phase)} to "
            f"{current.life_phase.label}"
        )
    else:
        prev_conf = (previous.get("life_phase") or {}).get("confidence", 0)
        if abs(prev_conf - current.life_phase.confidence) >= 0.05:
            changed.append("life_phase_confidence")
            notes.append(
                f"Confidence in '{current.life_phase.label}' moved from "
                f"{round(prev_conf * 100)}% to {round(current.life_phase.confidence * 100)}%"
            )

    prev_signals = {s["id"]: s for s in previous.get("signals", [])}
    for sig in current.signals:
        was = prev_signals.get(sig.id, {})
        if bool(was.get("triggered")) != sig.triggered:
            changed.append(f"signal:{sig.id}")
            notes.append(
                f"Signal '{sig.label}' "
                f"{'detected' if sig.triggered else 'no longer active'} "
                f"({round(sig.score * 100)}%)"
            )
        elif abs(was.get("score", 0) - sig.score) >= 0.10:
            changed.append(f"signal:{sig.id}")
            notes.append(
                f"'{sig.label}' moved to {round(sig.score * 100)}% confidence"
            )

    prev_goals = {g["id"]: g for g in previous.get("goals", [])}
    for goal in current.goals:
        if goal.id not in prev_goals:
            changed.append(f"goal:{goal.id}")
            notes.append(f"New goal: {goal.title} (EUR {goal.target_amount:,.0f})")
        else:
            old = prev_goals[goal.id]
            if abs(old.get("current_amount", 0) - goal.current_amount) >= 1:
                changed.append(f"goal:{goal.id}")
                notes.append(
                    f"{goal.title}: EUR {old.get('current_amount', 0):,.0f} to "
                    f"EUR {goal.current_amount:,.0f}"
                )
            elif old.get("projected_completion") != goal.projected_completion:
                changed.append(f"goal:{goal.id}")
                notes.append(
                    f"{goal.title} completion moved to {goal.projected_completion}"
                )
    for gid, old in prev_goals.items():
        if gid not in {g.id for g in current.goals}:
            changed.append(f"goal:{gid}")
            notes.append(f"Goal removed: {old.get('title', gid)}")

    prev_progress = previous.get("progress_score", 0)
    if abs(prev_progress - current.progress_score) >= 0.01:
        changed.append("progress_score")
        notes.append(
            f"Progress score {round(prev_progress * 100)}% to "
            f"{round(current.progress_score * 100)}%"
        )

    prev_timeline = len(previous.get("future_timeline", []))
    if prev_timeline != len(current.future_timeline):
        changed.append("future_timeline")
        notes.append(
            f"Timeline changed from {prev_timeline} to "
            f"{len(current.future_timeline)} milestones"
        )

    prev_corr = len(previous.get("corrections", []))
    if prev_corr != len(current.corrections):
        changed.append("corrections")
        notes.append("Your correction was applied")

    return ("; ".join(notes) if notes else "No material change"), changed


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------
def load_twin(customer_id: str) -> dict | None:
    row = db.query_one("SELECT twin_json FROM twins WHERE customer_id = ?", (customer_id,))
    return db.loads(row["twin_json"]) if row else None


def save_twin(twin: FinancialTwin) -> dict:
    payload = twin.model_dump()
    raw = db.dumps(payload)
    now = _now()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO twins(customer_id, version, twin_json, updated_at) "
            "VALUES(?,?,?,?) ON CONFLICT(customer_id) DO UPDATE SET "
            "version=excluded.version, twin_json=excluded.twin_json, "
            "updated_at=excluded.updated_at",
            (twin.customer_id, twin.version, raw, now),
        )
        conn.execute(
            "INSERT INTO twin_history(customer_id, version, change_summary, "
            "twin_json, created_at) VALUES(?,?,?,?,?)",
            (twin.customer_id, twin.version, twin.change_summary, raw, now),
        )
    return payload


def save_features(customer_id: str, state: dict) -> None:
    db.execute(
        "INSERT INTO features(customer_id, state_json, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(customer_id) DO UPDATE SET state_json=excluded.state_json, "
        "updated_at=excluded.updated_at",
        (customer_id, db.dumps(state), _now()),
    )


def load_features(customer_id: str) -> dict | None:
    row = db.query_one("SELECT state_json FROM features WHERE customer_id = ?", (customer_id,))
    return db.loads(row["state_json"]) if row else None


def load_customer(customer_id: str) -> dict | None:
    row = db.query_one("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    if not row:
        return None
    customer = dict(row)
    customer["declared"] = db.loads(customer.pop("declared_json"), {})
    return customer
