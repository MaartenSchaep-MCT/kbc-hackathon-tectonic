"""TIER 1 - streaming feature computation.

One function, `apply_transaction`, is the only place a transaction changes
feature state. It is used by:

  * seed.py        - replaying 12 months of history
  * event_bus.py   - the live asyncio.Queue worker
  * benchmark.py   - the 100k-customer throughput test

Using the same code path for all three is deliberate: batch and streaming
cannot drift apart, which is the single most common failure mode of real
feature pipelines. In production this function is the body of a Flink
operator; the dict below becomes a row in an online feature store.

Kept allocation-light on purpose - the benchmark calls it ~1.2M times.
"""
from __future__ import annotations

from .catalog import INCOME_CATEGORIES, SAVINGS_CATEGORIES

# Rolling window. 13 months so a 12-month comparison always has a baseline.
WINDOW_MONTHS = 13

# A single outflow at or above this is treated as funded from savings rather
# than from the month's cash flow. Derived rule, not an observed fact.
LARGE_EXPENSE_THRESHOLD = 1000.0

RECURRING_CATEGORIES = ("rent", "mortgage", "utilities", "telecom", "insurance")
BABY_CATEGORIES = ("baby_retail", "nursery_furniture", "prenatal_health")


def new_state(savings_balance: float = 0.0) -> dict:
    """Empty Tier 1 feature state for one customer."""
    return {
        "months": {},              # "YYYY-MM" -> {"in":f, "out":f, "cat":{cat:f}}
        "savings_balance": float(savings_balance),
        "opening_savings": float(savings_balance),
        "txn_count": 0,
        "salary_by_month": {},     # "YYYY-MM" -> total salary credited
        "student_income_months": {},
        "first_salary_month": None,
        "large_expenses": [],      # [{"month","amount","category","merchant"}]
        "last_event_ts": "",
        "derived": {},
    }


def apply_transaction(state: dict, txn: dict) -> dict:
    """Fold one transaction into the feature state. Mutates and returns state.

    `txn` needs: timestamp (ISO), category, amount (>0 in, <0 out).
    """
    ts = txn["timestamp"]
    month = ts[:7]
    category = txn["category"]
    amount = txn["amount"]

    months = state["months"]
    bucket = months.get(month)
    if bucket is None:
        bucket = {"in": 0.0, "out": 0.0, "save": 0.0, "cat": {}}
        months[month] = bucket
        if len(months) > WINDOW_MONTHS:
            for stale in sorted(months)[:-WINDOW_MONTHS]:
                del months[stale]

    cat = bucket["cat"]
    cat[category] = cat.get(category, 0.0) + amount

    if amount >= 0:
        bucket["in"] += amount
        if category == "salary":
            sbm = state["salary_by_month"]
            sbm[month] = sbm.get(month, 0.0) + amount
            if state["first_salary_month"] is None or month < state["first_salary_month"]:
                state["first_salary_month"] = month
        elif category == "student_income":
            sim = state["student_income_months"]
            sim[month] = sim.get(month, 0.0) + amount
    else:
        outflow = -amount
        if category in SAVINGS_CATEGORIES:
            # Money leaving the current account into a savings vehicle. This is
            # NOT spending - it is the customer keeping their own money. Counting
            # it as spend would inflate every target derived from spending and
            # would make a bigger savings transfer look like a worse month.
            bucket["save"] += outflow
            state["savings_balance"] += outflow
        elif outflow >= LARGE_EXPENSE_THRESHOLD and category not in ("rent", "mortgage"):
            bucket["out"] += outflow
            # Derived rule: a one-off expense this size is funded from savings.
            state["savings_balance"] = max(0.0, state["savings_balance"] - outflow)
            state["large_expenses"].append(
                {"month": month, "amount": round(outflow, 2),
                 "category": category, "merchant": txn.get("merchant", "")}
            )
            del state["large_expenses"][:-5]
        else:
            bucket["out"] += outflow

    state["txn_count"] += 1
    if ts > state["last_event_ts"]:
        state["last_event_ts"] = ts
    return state


# --------------------------------------------------------------------------
# Derived features. Pure arithmetic over the rolling window - provenance
# "derived", never "inferred". Tier 2 reads only this dict.
# --------------------------------------------------------------------------
def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _window_sum(state: dict, ordered: list[str], n: int, categories) -> float:
    total = 0.0
    for month in ordered[-n:]:
        cat = state["months"][month]["cat"]
        for c in categories:
            v = cat.get(c)
            if v:
                total += -v if v < 0 else v
    return total


def recompute_derived(state: dict) -> dict:
    """Refresh state['derived']. Cheap: bounded by WINDOW_MONTHS."""
    months = state["months"]
    ordered = sorted(months)
    d: dict[str, float | str | bool | int] = {}

    incomes = [months[m]["in"] for m in ordered]
    spends = [months[m]["out"] for m in ordered]

    # Exclude the newest month from averages only when it is clearly partial?
    # We keep it simple and honest: last 3 completed-or-current months.
    recent_income = _avg(incomes[-3:])
    prior_income = _avg(incomes[-6:-3]) if len(incomes) >= 4 else 0.0
    recent_spend = _avg(spends[-3:])
    prior_spend = _avg(spends[-6:-3]) if len(spends) >= 4 else 0.0

    # Core (recurring) spend: the same average with one-off large expenses
    # removed. Everything forward-looking - buffer targets, the retirement
    # income assumption, the spending trend - uses THIS, not the raw figure.
    # Otherwise a single kitchen deposit permanently inflates what we think
    # the customer needs to live on.
    one_off_by_month: dict[str, float] = {}
    for e in state["large_expenses"]:
        one_off_by_month[e["month"]] = one_off_by_month.get(e["month"], 0.0) + e["amount"]

    def _core(window: list[str]) -> float:
        if not window:
            return 0.0
        total = sum(max(0.0, months[m]["out"] - one_off_by_month.get(m, 0.0))
                    for m in window)
        return total / len(window)

    recent_core = _core(ordered[-3:])
    prior_core = _core(ordered[-6:-3]) if len(ordered) >= 4 else 0.0

    d["months_observed"] = len(ordered)
    d["monthly_income"] = round(recent_income, 2)
    d["monthly_income_previous"] = round(prior_income, 2)
    d["monthly_spend"] = round(recent_spend, 2)
    d["monthly_spend_previous"] = round(prior_spend, 2)
    d["monthly_spend_core"] = round(recent_core, 2)
    d["monthly_spend_core_previous"] = round(prior_core, 2)
    d["one_off_spend_3m"] = round(sum(one_off_by_month.get(m, 0.0) for m in ordered[-3:]), 2)

    if prior_income > 0:
        change = (recent_income - prior_income) / prior_income
    else:
        change = 1.0 if recent_income > 0 else 0.0
    d["income_change_pct"] = round(change * 100, 1)
    d["income_trend"] = "rising" if change > 0.08 else "falling" if change < -0.08 else "stable"

    if prior_core > 0:
        spend_change = (recent_core - prior_core) / prior_core
    else:
        spend_change = 0.0
    d["spend_change_pct"] = round(spend_change * 100, 1)
    d["spend_trend"] = (
        "rising" if spend_change > 0.08 else "falling" if spend_change < -0.08 else "stable"
    )

    # --- salary detection --------------------------------------------------
    salary_months = sorted(state["salary_by_month"])
    consecutive = 0
    if salary_months:
        consecutive = 1
        for prev, cur in zip(salary_months, salary_months[1:]):
            py, pm = int(prev[:4]), int(prev[5:7])
            cy, cm = int(cur[:4]), int(cur[5:7])
            consecutive = consecutive + 1 if (cy - py) * 12 + (cm - pm) == 1 else 1
    d["salary_months_consecutive"] = consecutive
    d["salary_months_total"] = len(salary_months)
    d["salary_detected"] = consecutive >= 2
    d["salary_latest_amount"] = round(
        state["salary_by_month"].get(salary_months[-1], 0.0) if salary_months else 0.0, 2
    )
    d["first_salary_month"] = state["first_salary_month"] or ""
    d["student_income_months"] = len(state["student_income_months"])
    d["has_student_history"] = len(state["student_income_months"]) >= 2

    # --- fixed costs -------------------------------------------------------
    def monthly(cat: str, n: int = 3) -> float:
        return round(_window_sum(state, ordered, n, (cat,)) / max(1, min(n, len(ordered))), 2)

    d["rent_monthly"] = monthly("rent")
    d["mortgage_monthly"] = monthly("mortgage")
    d["housing_cost_monthly"] = round(d["rent_monthly"] + d["mortgage_monthly"], 2)
    d["recurring_expenses_monthly"] = round(
        _window_sum(state, ordered, 3, RECURRING_CATEGORIES) / max(1, min(3, len(ordered))), 2
    )
    d["childcare_monthly"] = monthly("childcare")
    d["insurance_monthly"] = monthly("insurance")

    # How long have we actually been seeing this housing cost? A customer who
    # has paid the same rent for a year is not "moving out".
    d["rent_months"] = sum(1 for m in ordered if months[m]["cat"].get("rent"))
    d["mortgage_months"] = sum(1 for m in ordered if months[m]["cat"].get("mortgage"))

    def _change_pct(cats: tuple[str, ...]) -> float:
        recent = _window_sum(state, ordered, 3, cats) / 3.0
        older = ordered[:-3][-3:]
        if not older:
            return 0.0
        prior = 0.0
        for m in older:
            cat = months[m]["cat"]
            for c in cats:
                v = cat.get(c)
                if v:
                    prior += -v if v < 0 else v
        prior /= len(older)
        if prior <= 0:
            return 100.0 if recent > 0 else 0.0
        return round((recent - prior) / prior * 100, 1)

    d["housing_cost_change_pct"] = _change_pct(("rent", "mortgage"))
    d["insurance_change_pct"] = _change_pct(("insurance",))

    # --- income composition (Tier 2 needs these to separate phases) --------
    d["pension_income_monthly"] = monthly("pension_income")
    d["child_benefit_monthly"] = monthly("child_benefit")
    d["student_income_monthly"] = monthly("student_income")
    d["benefits_monthly"] = monthly("benefits")

    # --- savings & investing ----------------------------------------------
    d["monthly_savings_moved"] = round(
        sum(months[m]["save"] for m in ordered[-3:]) / max(1, len(ordered[-3:])), 2
    )
    d["monthly_savings_contribution"] = round(
        _window_sum(state, ordered, 3, tuple(SAVINGS_CATEGORIES)) / max(1, min(3, len(ordered))), 2
    )
    d["investment_contribution_monthly"] = monthly("investment_contribution")
    d["pension_contribution_monthly"] = monthly("pension_savings")
    d["savings_balance"] = round(state["savings_balance"], 2)

    # The income the customer is actually on now. A trailing 3-month average
    # understates someone who just started earning, which would understate
    # every goal target derived from it.
    d["income_basis"] = round(max(recent_income, d["salary_latest_amount"]), 2)

    surplus = recent_income - recent_spend
    d["monthly_surplus"] = round(surplus, 2)
    # Two different things, kept separate on purpose:
    #   savings_rate        - share of income NOT consumed (capacity)
    #   contribution_rate   - share actually moved into savings (behaviour)
    # Someone living rent-free has a huge savings_rate and may still put
    # nothing aside. Calling that "saving 80%" would be wrong.
    d["savings_rate"] = round(surplus / recent_income, 4) if recent_income > 0 else 0.0
    d["contribution_rate"] = (
        round(d["monthly_savings_contribution"] / recent_income, 4)
        if recent_income > 0 else 0.0
    )
    d["emergency_fund_months"] = (
        round(state["savings_balance"] / recent_core, 1) if recent_core > 0 else 0.0
    )

    # --- life-event bearing signals ---------------------------------------
    d["baby_spend_3m"] = round(_window_sum(state, ordered, 3, BABY_CATEGORIES), 2)
    baby_txns = 0
    baby_cats_seen = set()
    for m in ordered[-3:]:
        cat = months[m]["cat"]
        for c in BABY_CATEGORIES:
            if cat.get(c):
                baby_txns += 1
                baby_cats_seen.add(c)
    d["baby_categories_seen"] = len(baby_cats_seen)
    d["baby_retail_spend_3m"] = round(_window_sum(state, ordered, 3, ("baby_retail",)), 2)
    d["nursery_spend_3m"] = round(_window_sum(state, ordered, 3, ("nursery_furniture",)), 2)
    d["prenatal_spend_3m"] = round(_window_sum(state, ordered, 3, ("prenatal_health",)), 2)
    d["pharmacy_spend_3m"] = round(_window_sum(state, ordered, 3, ("pharmacy",)), 2)
    d["travel_spend_12m"] = round(_window_sum(state, ordered, 12, ("travel",)), 2)
    d["home_improvement_spend_3m"] = round(
        _window_sum(state, ordered, 3, ("home_improvement",)), 2
    )
    d["school_spend_12m"] = round(_window_sum(state, ordered, 12, ("school",)), 2)

    largest = max((e["amount"] for e in state["large_expenses"]), default=0.0)
    d["largest_recent_expense"] = round(largest, 2)
    d["largest_home_expense"] = round(
        max((e["amount"] for e in state["large_expenses"]
             if e["category"] in ("home_improvement", "nursery_furniture")), default=0.0), 2
    )
    d["large_expense_count"] = len(state["large_expenses"])
    d["txn_count"] = state["txn_count"]
    d["last_event_ts"] = state["last_event_ts"]

    state["derived"] = d
    return d


def rebuild(transactions: list[dict], savings_balance: float = 0.0) -> dict:
    """Replay a transaction list into a fresh feature state (batch path)."""
    state = new_state(savings_balance)
    for txn in transactions:
        apply_transaction(state, txn)
    recompute_derived(state)
    return state
