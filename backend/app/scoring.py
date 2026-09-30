"""TIER 2 - lightweight interpretable inference.

These are *interpretable scoring models*, not machine learning. Each model is
a list of weighted rules; a rule that fires contributes its weight and a
human-readable piece of evidence. The score is the clamped sum.

Why rules and not a classifier, for a hackathon:
  * every output is explainable by construction - the evidence list IS the
    model, so "why we think this" needs no post-hoc interpretation layer;
  * thresholds are visible and tunable (see THRESHOLDS below);
  * behaviour is deterministic, so the demo and the tests agree.

The interface (`score_all` -> id, score, evidence) is what a real model would
also expose, so replacing any single model with a trained one is local work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# Every number a reviewer might argue about lives here.
THRESHOLDS: dict[str, float] = {
    "salary_large": 1200.0,          # EUR, a "real" first salary
    "salary_consecutive_months": 2,
    "income_jump_pct": 100.0,        # first-job income doubling
    "income_raise_pct": 15.0,        # career income increase
    "baby_retail_spend": 60.0,
    "nursery_spend": 250.0,
    "prenatal_spend": 40.0,
    "emergency_fund_target_months": 6.0,
    "emergency_fund_thin_months": 1.5,
    "house_deposit_savings": 15000.0,
    "healthy_savings_rate": 0.10,
    "pre_retirement_age": 55,
    "retirement_age_default": 65,
    "renovation_spend": 1500.0,
    "signal_trigger": 0.55,          # default trigger threshold for a signal
}

# An inferred conclusion is never allowed to reach 1.0. Behavioural evidence
# can be overwhelming, but it is still evidence about someone's life - so the
# engine structurally cannot claim certainty. Only a customer correction
# (provenance "declared") gets confidence 1.0.
MAX_INFERRED_CONFIDENCE = 0.97


@dataclass
class Rule:
    weight: float
    evidence: str                    # format string over the context dict
    test: Callable[[dict], bool]
    provenance: str = "derived"


@dataclass
class ScoringModel:
    id: str
    label: str
    rules: list[Rule]
    threshold: float = 0.55
    kind: str = "signal"             # "signal" | "life_phase"
    # An applicability gate. If it returns False the model does not apply at
    # all and scores 0 - which is different from "applies but scored low".
    # Without this, "saving for a first home" fires for people who already
    # own one, because the savings rules are blind to the mortgage.
    gate: Callable[[dict], bool] | None = None
    gate_reason: str = ""
    # Ceiling on this model's confidence. Intent models cap lower than
    # behavioural ones: we can be nearly certain about an observed pattern,
    # never about what someone privately plans to do.
    max_confidence: float = MAX_INFERRED_CONFIDENCE
    uncertainty_note: str = ""
    field_of: str = ""               # which Twin field this model feeds
    corrigible_by: str = ""          # correction field that overrides it
    tags: list[str] = field(default_factory=list)


def _fmt(template: str, ctx: dict) -> str:
    try:
        return template.format(**ctx)
    except (KeyError, IndexError, ValueError):
        return template


def evaluate(model: ScoringModel, ctx: dict) -> dict:
    """Run one model. Returns score, whether it triggered, and the evidence."""
    if model.gate is not None:
        try:
            applies = bool(model.gate(ctx))
        except (KeyError, TypeError, ZeroDivisionError):
            applies = False
        if not applies:
            return {
                "id": model.id, "label": model.label, "score": 0.0,
                "threshold": model.threshold, "triggered": False,
                "evidence": [], "kind": model.kind,
                "uncertainty_note": model.uncertainty_note,
                "corrigible_by": model.corrigible_by,
                "suppressed_by_customer": False,
                "not_applicable": True,
                "not_applicable_reason": model.gate_reason,
            }

    score = 0.0
    evidence: list[dict] = []
    for rule in model.rules:
        try:
            fired = bool(rule.test(ctx))
        except (KeyError, TypeError, ZeroDivisionError):
            fired = False
        if fired:
            score += rule.weight
            evidence.append(
                {
                    "text": _fmt(rule.evidence, ctx),
                    "weight": round(rule.weight, 3),
                    "provenance": rule.provenance,
                }
            )
    score = max(0.0, min(model.max_confidence, round(score, 4)))
    return {
        "id": model.id,
        "label": model.label,
        "score": score,
        "threshold": model.threshold,
        "triggered": score >= model.threshold,
        "evidence": evidence,
        "kind": model.kind,
        "uncertainty_note": model.uncertainty_note,
        "corrigible_by": model.corrigible_by,
        # Set to True later by the Twin engine if the customer rejected it.
        "suppressed_by_customer": False,
        "not_applicable": False,
        "not_applicable_reason": "",
    }


# --------------------------------------------------------------------------
# Behavioural signals
# --------------------------------------------------------------------------
T = THRESHOLDS

SIGNAL_MODELS: list[ScoringModel] = [
    ScoringModel(
        id="first_job",
        label="Started first job",
        threshold=0.55,
        corrigible_by="life_phase",
        gate=lambda c: 0 < c["salary_months_total"] <= 8,
        gate_reason="Salary history is too long for this to be a first job.",
        rules=[
            Rule(0.45, "First salary payment of EUR {salary_latest_amount:,.0f} received",
                 lambda c: c["salary_latest_amount"] >= T["salary_large"]),
            Rule(0.30, "Salary from the same employer for {salary_months_consecutive} consecutive months",
                 lambda c: c["salary_months_consecutive"] >= T["salary_consecutive_months"]),
            Rule(0.15, "Previously receiving student income ({student_income_months} months on record)",
                 lambda c: c["has_student_history"]),
            Rule(0.10, "Monthly income increased by {income_change_pct:.0f}%",
                 lambda c: c["income_change_pct"] >= T["income_jump_pct"]),
        ],
    ),
    ScoringModel(
        id="possible_family_expansion",
        label="Possible family expansion",
        threshold=0.50,
        corrigible_by="family_expansion",
        max_confidence=0.85,
        uncertainty_note=(
            "This is an assumption based on spending patterns, not a confirmed "
            "fact. Spending like this has other explanations - a gift, a "
            "relative, a friend's baby shower."
        ),
        rules=[
            Rule(0.30, "Purchases at baby retailers totalling EUR {baby_retail_spend_3m:,.0f} in the last 3 months",
                 lambda c: c["baby_retail_spend_3m"] >= T["baby_retail_spend"]),
            Rule(0.33, "Nursery furniture purchase of EUR {nursery_spend_3m:,.0f}",
                 lambda c: c["nursery_spend_3m"] >= T["nursery_spend"]),
            Rule(0.15, "Prenatal care spending of EUR {prenatal_spend_3m:,.0f}",
                 lambda c: c["prenatal_spend_3m"] >= T["prenatal_spend"]),
            Rule(0.22, "Household costs shifted towards family expenses ({spend_change_pct:+.0f}%, childcare now EUR {childcare_monthly:,.0f}/month)",
                 lambda c: c["spend_change_pct"] >= 8.0 and c["childcare_monthly"] > 0),
        ],
    ),
    ScoringModel(
        id="moving_out",
        label="Moving into own place",
        threshold=0.55,
        gate=lambda c: 0 < c["rent_months"] <= 6,
        gate_reason="This rent has been running too long to be a recent move.",
        rules=[
            Rule(0.45, "Rent of EUR {rent_monthly:,.0f} per month appeared {rent_months} month(s) ago",
                 lambda c: c["rent_monthly"] > 0),
            Rule(0.20, "Utility and telecom contracts active in own name",
                 lambda c: c["recurring_expenses_monthly"] > 150),
            Rule(0.20, "Age {age} with own housing costs",
                 lambda c: c["age"] < 32 and c["rent_monthly"] > 0),
            Rule(0.15, "Furniture and home setup spending of EUR {home_improvement_spend_3m:,.0f}",
                 lambda c: c["home_improvement_spend_3m"] > 200),
        ],
    ),
    ScoringModel(
        id="first_home_intent",
        label="Saving towards a first home",
        threshold=0.60,
        corrigible_by="plans_to_buy_house",
        # An intention is never as knowable as a behaviour.
        max_confidence=0.80,
        gate=lambda c: c["mortgage_monthly"] == 0 and c["age"] <= 45,
        gate_reason="This customer already owns a home, or is past a typical first purchase.",
        uncertainty_note=(
            "This is an assumption about your plans, not something you have told "
            "us. We cap our confidence here on purpose. Switch it off if it is wrong."
        ),
        rules=[
            Rule(0.28, "Savings balance of EUR {savings_balance:,.0f} building up",
                 lambda c: c["savings_balance"] >= T["house_deposit_savings"]),
            Rule(0.22, "Putting aside {contribution_rate_pct:.0f}% of income every month",
                 lambda c: c["contribution_rate"] >= T["healthy_savings_rate"]),
            Rule(0.18, "Currently renting rather than owning",
                 lambda c: c["rent_monthly"] > 0 and c["mortgage_monthly"] == 0),
            Rule(0.12, "Age {age}, a common window for a first purchase",
                 lambda c: 25 <= c["age"] <= 40),
            Rule(0.08, "Income is {income_trend} and predictable",
                 lambda c: c["income_trend"] in ("stable", "rising") and c["salary_detected"]),
        ],
    ),
    ScoringModel(
        id="career_income_increase",
        label="Income increased",
        threshold=0.55,
        rules=[
            Rule(0.45, "Monthly income up {income_change_pct:.0f}% (EUR {monthly_income_previous:,.0f} to EUR {monthly_income:,.0f})",
                 lambda c: c["income_change_pct"] >= T["income_raise_pct"]),
            Rule(0.30, "Higher income sustained across {salary_months_consecutive} months",
                 lambda c: c["salary_months_consecutive"] >= 2 and c["income_change_pct"] > 0),
            Rule(0.25, "Salary is the dominant income source",
                 lambda c: c["salary_detected"] and c["monthly_income"] > 0),
        ],
    ),
    ScoringModel(
        id="financial_stress",
        label="Financial pressure",
        threshold=0.50,
        rules=[
            Rule(0.40, "Spending exceeds income by EUR {monthly_deficit:,.0f} per month",
                 lambda c: c["monthly_surplus"] < 0),
            Rule(0.25, "Buffer covers only {emergency_fund_months} months of spending",
                 lambda c: 0 < c["emergency_fund_months"] < T["emergency_fund_thin_months"]),
            Rule(0.20, "Spending rising ({spend_change_pct:+.0f}%) while income is {income_trend}",
                 lambda c: c["spend_change_pct"] > 10 and c["income_trend"] != "rising"),
            Rule(0.15, "Recent one-off expense of EUR {largest_recent_expense:,.0f}",
                 lambda c: c["largest_recent_expense"] >= 1500),
        ],
    ),
    ScoringModel(
        id="building_emergency_savings",
        label="Building an emergency buffer",
        threshold=0.55,
        rules=[
            Rule(0.35, "Regular savings transfers of EUR {monthly_savings_contribution:,.0f} per month",
                 lambda c: c["monthly_savings_contribution"] > 25),
            Rule(0.30, "Buffer at {emergency_fund_months} months, below the {emergency_target:.0f}-month guideline",
                 lambda c: 0 <= c["emergency_fund_months"] < T["emergency_fund_target_months"]),
            Rule(0.20, "Positive monthly surplus of EUR {monthly_surplus:,.0f}",
                 lambda c: c["monthly_surplus"] > 0),
            Rule(0.15, "Keeping {savings_rate_pct:.0f}% of income unspent, so there is room to do more",
                 lambda c: c["savings_rate"] >= T["healthy_savings_rate"]),
        ],
    ),
    ScoringModel(
        id="household_merge",
        label="Households merging",
        threshold=0.60,
        max_confidence=0.85,
        gate=lambda c: bool(c.get("has_partner")),
        gate_reason="No partner is recorded on this household.",
        rules=[
            Rule(0.35, "Housing cost changed by {housing_cost_change_pct:+.0f}% recently",
                 lambda c: c["housing_cost_change_pct"] >= 25),
            Rule(0.25, "A partner is recorded on the household",
                 lambda c: bool(c.get("has_partner")), provenance="declared"),
            Rule(0.20, "Insurance premiums changed by {insurance_change_pct:+.0f}%",
                 lambda c: abs(c["insurance_change_pct"]) >= 20),
            Rule(0.20, "Combined household spending of EUR {monthly_spend:,.0f} per month",
                 lambda c: c["monthly_spend"] > 1800),
        ],
    ),
    ScoringModel(
        id="renovation",
        label="Renovating the home",
        threshold=0.55,
        rules=[
            Rule(0.50, "Home improvement spending of EUR {home_improvement_spend_3m:,.0f} in 3 months",
                 lambda c: c["home_improvement_spend_3m"] >= T["renovation_spend"]),
            Rule(0.25, "An active mortgage on the property",
                 lambda c: c["mortgage_monthly"] > 0),
            Rule(0.25, "A large home-related expense of EUR {largest_home_expense:,.0f}",
                 lambda c: c["largest_home_expense"] >= 1000),
        ],
    ),
    ScoringModel(
        id="nearing_retirement",
        label="Approaching retirement",
        threshold=0.55,
        corrigible_by="target_retirement_age",
        gate=lambda c: c["age"] >= 50 and c["pension_income_monthly"] == 0,
        gate_reason="Too far from retirement, or already retired.",
        rules=[
            Rule(0.45, "Age {age}, within reach of the retirement horizon",
                 lambda c: c["age"] >= T["pre_retirement_age"], provenance="declared"),
            Rule(0.25, "Pension saving of EUR {pension_contribution_monthly:,.0f} per month",
                 lambda c: c["pension_contribution_monthly"] > 0),
            Rule(0.15, "Accumulated savings of EUR {savings_balance:,.0f}",
                 lambda c: c["savings_balance"] >= 40000),
            Rule(0.15, "Stable employment income ({salary_months_total} months on record)",
                 lambda c: c["salary_months_total"] >= 6 and c["income_trend"] != "falling"),
        ],
    ),
    ScoringModel(
        id="retirement",
        label="Retired",
        threshold=0.60,
        gate=lambda c: c["age"] >= 58 or c["pension_income_monthly"] > 0,
        gate_reason="Too young to be retired and no pension income observed.",
        rules=[
            Rule(0.60, "Pension income is being received",
                 lambda c: c["pension_income_monthly"] > 0),
            Rule(0.25, "Age {age}",
                 lambda c: c["age"] >= T["retirement_age_default"], provenance="declared"),
            Rule(0.15, "No employment salary on record",
                 lambda c: not c["salary_detected"]),
        ],
    ),
    ScoringModel(
        id="long_term_horizon",
        label="Long-term retirement horizon",
        threshold=0.50,
        gate=lambda c: 35 <= c["age"] < 55 and c["pension_income_monthly"] == 0,
        gate_reason="Outside the mid-life window where a long-range projection is the useful framing.",
        rules=[
            Rule(0.35, "Age {age} - far enough out that small monthly amounts still compound",
                 lambda c: c["age"] >= 35, provenance="declared"),
            Rule(0.25, "A regular income of EUR {monthly_income:,.0f} per month to plan against",
                 lambda c: c["monthly_income"] > 0),
            Rule(0.20, "Already setting money aside each month",
                 lambda c: c["monthly_savings_contribution"] > 0),
            Rule(0.20, "Employment income on record",
                 lambda c: c["salary_detected"]),
        ],
    ),
    ScoringModel(
        id="family_with_children",
        label="Raising children",
        threshold=0.55,
        gate=lambda c: c["children"] >= 1,
        gate_reason="No children recorded on this household.",
        rules=[
            Rule(0.40, "{children} child(ren) in the household",
                 lambda c: c["children"] >= 1, provenance="declared"),
            Rule(0.30, "Childcare costs of EUR {childcare_monthly:,.0f} per month",
                 lambda c: c["childcare_monthly"] > 0),
            Rule(0.15, "Child benefit received",
                 lambda c: c["child_benefit_monthly"] > 0),
            Rule(0.15, "Education spending of EUR {school_spend_12m:,.0f} over 12 months",
                 lambda c: c["school_spend_12m"] > 100),
        ],
    ),
]


# --------------------------------------------------------------------------
# Life phase. Exactly one wins; the rest stay visible as runners-up.
# --------------------------------------------------------------------------
LIFE_PHASE_MODELS: list[ScoringModel] = [
    ScoringModel(
        id="student", label="Studying", kind="life_phase", threshold=0.5,
        rules=[
            Rule(0.35, "Student income across {student_income_months} months",
                 lambda c: c["has_student_history"]),
            Rule(0.30, "No recurring employer salary yet",
                 lambda c: not c["salary_detected"]),
            Rule(0.20, "Age {age}",
                 lambda c: c["age"] < 26, provenance="declared"),
            Rule(0.15, "Monthly income of EUR {monthly_income:,.0f}",
                 lambda c: c["monthly_income"] < 1200),
        ],
    ),
    ScoringModel(
        id="first_job", label="Starting career", kind="life_phase", threshold=0.5,
        rules=[
            Rule(0.40, "Recurring salary of EUR {salary_latest_amount:,.0f} now arriving",
                 lambda c: c["salary_detected"] and c["salary_latest_amount"] >= T["salary_large"]),
            Rule(0.25, "Salary history is short ({salary_months_total} months)",
                 lambda c: 0 < c["salary_months_total"] <= 6),
            Rule(0.14, "Transitioned from student income",
                 lambda c: c["has_student_history"]),
            Rule(0.12, "Age {age}",
                 lambda c: c["age"] <= 30, provenance="declared"),
        ],
    ),
    ScoringModel(
        id="establishing", label="Building your career", kind="life_phase", threshold=0.5,
        rules=[
            Rule(0.35, "Established salary of EUR {monthly_income:,.0f} per month",
                 lambda c: c["salary_detected"] and c["salary_months_total"] > 6),
            Rule(0.25, "Age {age}",
                 lambda c: 26 <= c["age"] <= 42, provenance="declared"),
            Rule(0.25, "No children in the household",
                 lambda c: c["children"] == 0, provenance="declared"),
            Rule(0.15, "Actively saving or investing EUR {monthly_savings_contribution:,.0f} per month",
                 lambda c: c["monthly_savings_contribution"] > 0),
        ],
    ),
    ScoringModel(
        id="family_building", label="Starting a family", kind="life_phase", threshold=0.5,
        rules=[
            Rule(0.35, "Childcare costs of EUR {childcare_monthly:,.0f} per month",
                 lambda c: c["childcare_monthly"] > 0),
            Rule(0.20, "No school costs yet, so the children are young",
                 lambda c: c["childcare_monthly"] > 0 and c["school_spend_12m"] < 100),
            Rule(0.15, "Baby-related spending across {baby_categories_seen} categories",
                 lambda c: c["baby_categories_seen"] >= 2),
            Rule(0.15, "Partner in the household",
                 lambda c: bool(c.get("has_partner")), provenance="declared"),
            Rule(0.15, "Age {age}",
                 lambda c: 26 <= c["age"] <= 44, provenance="declared"),
        ],
    ),
    ScoringModel(
        id="family_established", label="Family life", kind="life_phase", threshold=0.5,
        rules=[
            Rule(0.30, "{children} child(ren) in the household",
                 lambda c: c["children"] >= 1, provenance="declared"),
            Rule(0.30, "Education spending of EUR {school_spend_12m:,.0f} over 12 months",
                 lambda c: c["school_spend_12m"] > 100),
            Rule(0.20, "Age {age}",
                 lambda c: 33 <= c["age"] <= 56, provenance="declared"),
            Rule(0.20, "Mortgage on the family home",
                 lambda c: c["mortgage_monthly"] > 0),
        ],
    ),
    ScoringModel(
        id="pre_retirement", label="Preparing for retirement", kind="life_phase", threshold=0.5,
        rules=[
            Rule(0.45, "Age {age}",
                 lambda c: c["age"] >= T["pre_retirement_age"], provenance="declared"),
            Rule(0.25, "Pension saving of EUR {pension_contribution_monthly:,.0f} per month",
                 lambda c: c["pension_contribution_monthly"] > 0),
            Rule(0.20, "Savings of EUR {savings_balance:,.0f} accumulated",
                 lambda c: c["savings_balance"] >= 25000),
            Rule(0.10, "Still receiving employment income",
                 lambda c: c["salary_detected"]),
        ],
    ),
    ScoringModel(
        id="retired", label="Retired", kind="life_phase", threshold=0.5,
        rules=[
            Rule(0.55, "Pension income of EUR {pension_income_monthly:,.0f} per month",
                 lambda c: c["pension_income_monthly"] > 0),
            Rule(0.30, "Age {age}",
                 lambda c: c["age"] >= T["retirement_age_default"], provenance="declared"),
            Rule(0.15, "No employment salary",
                 lambda c: not c["salary_detected"]),
        ],
    ),
]

LIFE_PHASE_LABELS = {m.id: m.label for m in LIFE_PHASE_MODELS}
SIGNAL_LABELS = {m.id: m.label for m in SIGNAL_MODELS}


def build_context(derived: dict, customer: dict) -> dict:
    """Merge Tier 1 output with declared customer facts into one flat dict.

    Declared facts (age, children, partner) are marked as such in the rules
    that use them, so the evidence trail stays honest about what is observed
    behaviour versus what the customer told us.
    """
    ctx = dict(derived)
    ctx["age"] = customer.get("age", 0)
    ctx["children"] = customer.get("children", 0)
    ctx["household_type"] = customer.get("household_type", "single")
    ctx["housing"] = customer.get("housing", "unknown")
    ctx["has_partner"] = bool(customer.get("partner_name"))
    ctx["employer"] = customer.get("employer") or "an employer"
    # Convenience values used only by evidence templates.
    ctx["savings_rate_pct"] = round(ctx.get("savings_rate", 0.0) * 100, 1)
    ctx["contribution_rate_pct"] = round(ctx.get("contribution_rate", 0.0) * 100, 1)
    ctx["monthly_deficit"] = abs(min(0.0, ctx.get("monthly_surplus", 0.0)))
    ctx["emergency_target"] = T["emergency_fund_target_months"]
    ctx.setdefault("pension_income_monthly", 0.0)
    ctx.setdefault("child_benefit_monthly", 0.0)
    ctx.setdefault("rent_months", 0)
    ctx.setdefault("housing_cost_change_pct", 0.0)
    ctx.setdefault("insurance_change_pct", 0.0)
    ctx.setdefault("largest_home_expense", 0.0)
    ctx.setdefault("income_basis", ctx.get("monthly_income", 0.0))
    ctx.setdefault("monthly_spend_core", ctx.get("monthly_spend", 0.0))
    ctx.setdefault("one_off_spend_3m", 0.0)
    ctx.setdefault("contribution_rate", 0.0)
    return ctx


def score_all(ctx: dict) -> tuple[list[dict], list[dict]]:
    """Run every Tier 2 model. Returns (signals, life_phase_candidates)."""
    signals = [evaluate(m, ctx) for m in SIGNAL_MODELS]
    phases = [evaluate(m, ctx) for m in LIFE_PHASE_MODELS]
    phases.sort(key=lambda p: p["score"], reverse=True)
    return signals, phases
