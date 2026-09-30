"""Synthetic data generator.

1,000 customers, 12 months of Belgian-flavoured transactions, fixed seed.
Nothing here touches real data: names come from Faker's nl_BE locale and
merchants are public retail names used as realistic labels.

The three hero personas come from personas.py with hand-built histories; the
other 997 are drawn from archetypes so the population spreads across every
life phase and every playbook has real customers behind it.
"""
from __future__ import annotations

import random
import uuid
from datetime import date

from faker import Faker

from . import catalog, config, db, features, personas, twin_engine

# --------------------------------------------------------------------------
# Archetypes. Weight = share of the synthetic population.
# --------------------------------------------------------------------------
ARCHETYPES = [
    {
        "key": "student", "weight": 0.10, "age": (18, 25),
        "household": ["single", "shared"], "children": 0,
        "housing": ["living_with_parents", "student_room"],
        "income": (450, 900), "income_category": "student_income",
        "savings": (200, 3500), "rent": (0, 420), "save_rate": (0.0, 0.10),
    },
    {
        "key": "first_job", "weight": 0.12, "age": (22, 28),
        "household": ["single"], "children": 0,
        "housing": ["renting", "living_with_parents"],
        "income": (1900, 2900), "income_category": "salary",
        "savings": (400, 9000), "rent": (0, 820), "save_rate": (0.04, 0.18),
    },
    {
        "key": "establishing", "weight": 0.18, "age": (27, 40),
        "household": ["single", "couple"], "children": 0,
        "housing": ["renting", "owner_with_mortgage"],
        "income": (2600, 4600), "income_category": "salary",
        "savings": (3000, 42000), "rent": (700, 1350), "save_rate": (0.06, 0.26),
    },
    {
        "key": "family_building", "weight": 0.14, "age": (28, 40),
        "household": ["couple"], "children": 1,
        "housing": ["renting", "owner_with_mortgage"],
        "income": (3200, 5600), "income_category": "salary",
        "savings": (2000, 30000), "rent": (800, 1450), "save_rate": (0.02, 0.16),
        "childcare": (280, 620),
    },
    {
        "key": "family_established", "weight": 0.18, "age": (36, 54),
        "household": ["couple", "single_parent"], "children": 2,
        "housing": ["owner_with_mortgage"],
        "income": (3400, 6800), "income_category": "salary",
        "savings": (4000, 70000), "rent": (0, 0), "save_rate": (0.03, 0.20),
        "mortgage": (780, 1500),
    },
    {
        "key": "pre_retirement", "weight": 0.14, "age": (55, 64),
        "household": ["couple", "single"], "children": 2,
        "housing": ["owner_outright", "owner_with_mortgage"],
        "income": (3000, 6200), "income_category": "salary",
        "savings": (18000, 180000), "rent": (0, 0), "save_rate": (0.08, 0.30),
        "mortgage": (0, 700), "pension_saving": (70, 110),
    },
    {
        "key": "retired", "weight": 0.09, "age": (65, 82),
        "household": ["couple", "single"], "children": 2,
        "housing": ["owner_outright"],
        "income": (1500, 2900), "income_category": "pension_income",
        "savings": (12000, 220000), "rent": (0, 0), "save_rate": (0.0, 0.12),
    },
    {
        "key": "financial_stress", "weight": 0.05, "age": (24, 52),
        "household": ["single", "single_parent"], "children": 1,
        "housing": ["renting"],
        "income": (1400, 2200), "income_category": "salary",
        "savings": (0, 900), "rent": (700, 1050), "save_rate": (-0.10, 0.01),
    },
]

HOUSING_LABELS = {
    "living_with_parents": "Living with parents",
    "student_room": "Student room",
    "renting": "Renting",
    "owner_with_mortgage": "Owner with mortgage",
    "owner_outright": "Owner, mortgage repaid",
}


def _month_key(ref: date, months_ago: int) -> str:
    total = ref.year * 12 + ref.month - 1 - months_ago
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _pick(rng: random.Random, pair: tuple[float, float]) -> float:
    lo, hi = pair
    return rng.uniform(lo, hi)


def _generate_customer(rng: random.Random, fake: Faker, index: int,
                       ref: date, months: int) -> tuple[dict, list[dict]]:
    arch = rng.choices(ARCHETYPES, weights=[a["weight"] for a in ARCHETYPES])[0]
    age = rng.randint(*arch["age"])
    household = rng.choice(arch["household"])
    children = arch["children"] if household != "single" or arch["key"] == "financial_stress" else 0
    if household == "couple" and arch["key"] in ("family_building", "family_established"):
        children = max(1, arch["children"])
    housing = rng.choice(arch["housing"])
    income = round(_pick(rng, arch["income"]), 2)
    savings = round(_pick(rng, arch["savings"]), 2)
    rent = round(_pick(rng, arch.get("rent", (0, 0))), 2)
    mortgage = round(_pick(rng, arch.get("mortgage", (0, 0))), 2)
    if housing == "owner_with_mortgage" and mortgage == 0:
        mortgage = round(_pick(rng, (700, 1400)), 2)
    if housing in ("owner_with_mortgage", "owner_outright"):
        rent = 0.0
    save_rate = _pick(rng, arch["save_rate"])

    first_name = fake.first_name()
    last_name = fake.last_name()
    employer = (rng.choice(catalog.MERCHANTS["salary"])
                if arch["income_category"] == "salary" else None)

    customer = {
        "customer_id": f"KBC-{index:06d}",
        "first_name": first_name,
        "last_name": last_name,
        "age": age,
        "household_type": household,
        "partner_name": fake.name() if household == "couple" else None,
        "children": children,
        "housing": housing,
        "city": fake.city(),
        "employer": employer,
        "is_hero": 0,
        "hero_key": None,
        "hero_label": None,
        "declared": {
            "archetype": arch["key"],
            "notes": "Synthetic customer. Household facts treated as declared.",
        },
        "opening_savings": savings,
    }

    # Transitions. A life *change* only shows up if the history actually
    # changes partway through, so these customers get a switch-over month.
    salary_starts_at = 0          # months-ago index where salary begins
    if arch["key"] == "first_job":
        salary_starts_at = rng.randint(2, 5)
    rent_starts_at = months       # months-ago index where rent begins
    if rent > 0:
        rent_starts_at = rng.randint(1, 4) if rng.random() < 0.18 else months
    expecting = (arch["key"] in ("establishing", "family_building")
                 and rng.random() < 0.06)

    txns: list[dict] = []
    for i in range(months - 1, -1, -1):
        month = _month_key(ref, i)

        # --- income -------------------------------------------------------
        variation = rng.uniform(0.97, 1.04)
        if arch["key"] == "first_job" and i > salary_starts_at:
            # Before the job: student income at a fraction of the later salary.
            txns.append({
                "timestamp": f"{month}-{rng.randint(4, 9):02d}T08:00:00",
                "merchant": rng.choice(catalog.MERCHANTS["student_income"]),
                "category": "student_income",
                "amount": round(income * rng.uniform(0.22, 0.34), 2),
                "description": "Studentenjob",
            })
        else:
            txns.append({
                "timestamp": f"{month}-{rng.randint(24, 28):02d}T08:00:00",
                "merchant": employer or rng.choice(catalog.MERCHANTS[arch["income_category"]]),
                "category": arch["income_category"],
                "amount": round(income * variation, 2),
                "description": f"Inkomen {month}",
            })
        if household == "couple" and rng.random() < 0.7:
            txns.append({
                "timestamp": f"{month}-{rng.randint(24, 28):02d}T08:05:00",
                "merchant": rng.choice(catalog.MERCHANTS["salary"]),
                "category": "salary",
                "amount": round(income * rng.uniform(0.6, 1.05), 2),
                "description": "Salaris partner",
            })
        if children > 0:
            txns.append({
                "timestamp": f"{month}-05T08:00:00",
                "merchant": "Groeipakket Vlaanderen",
                "category": "child_benefit",
                "amount": round(children * rng.uniform(165, 190), 2),
                "description": "Groeipakket",
            })

        # --- fixed costs --------------------------------------------------
        if rent > 0 and i < rent_starts_at:
            txns.append({
                "timestamp": f"{month}-01T07:00:00",
                "merchant": rng.choice(catalog.MERCHANTS["rent"]),
                "category": "rent", "amount": -rent, "description": "Huur",
            })
        if mortgage > 0:
            txns.append({
                "timestamp": f"{month}-02T07:00:00",
                "merchant": "Woonkrediet aflossing",
                "category": "mortgage", "amount": -mortgage,
                "description": "Hypothecair krediet",
            })
        for cat, lo, hi in (("utilities", 55, 210), ("telecom", 22, 85),
                            ("insurance", 28, 175)):
            txns.append({
                "timestamp": f"{month}-{rng.randint(3, 6):02d}T07:30:00",
                "merchant": rng.choice(catalog.MERCHANTS[cat]),
                "category": cat,
                "amount": -round(rng.uniform(lo, hi), 2),
                "description": catalog.label_for(cat),
            })
        if "childcare" in arch and children > 0:
            txns.append({
                "timestamp": f"{month}-06T07:30:00",
                "merchant": rng.choice(catalog.MERCHANTS["childcare"]),
                "category": "childcare",
                "amount": -round(_pick(rng, arch["childcare"]), 2),
                "description": "Kinderopvang",
            })

        # --- daily life ---------------------------------------------------
        grocery_base = 120 + 95 * max(1, 1 + children) + (90 if household == "couple" else 0)
        for _ in range(rng.randint(2, 4)):
            txns.append({
                "timestamp": f"{month}-{rng.randint(1, 28):02d}T17:20:00",
                "merchant": rng.choice(catalog.MERCHANTS["groceries"]),
                "category": "groceries",
                "amount": -round(grocery_base / 3 * rng.uniform(0.7, 1.4), 2),
                "description": "Boodschappen",
            })
        for cat, lo, hi, chance in (
            ("transport_public", 22, 68, 0.55), ("fuel", 55, 145, 0.6),
            ("restaurants", 22, 110, 0.75), ("retail", 28, 210, 0.6),
            ("pharmacy", 12, 48, 0.4), ("healthcare", 24, 95, 0.3),
            ("subscriptions", 9, 35, 0.7), ("sport", 20, 45, 0.35),
            ("entertainment", 12, 60, 0.4),
        ):
            if rng.random() < chance:
                txns.append({
                    "timestamp": f"{month}-{rng.randint(1, 28):02d}T12:00:00",
                    "merchant": rng.choice(catalog.MERCHANTS[cat]),
                    "category": cat,
                    "amount": -round(rng.uniform(lo, hi), 2),
                    "description": catalog.label_for(cat),
                })
        if children >= 1 and i in (11, 8) and rng.random() < 0.6:
            txns.append({
                "timestamp": f"{month}-14T12:00:00",
                "merchant": rng.choice(catalog.MERCHANTS["school"]),
                "category": "school",
                "amount": -round(rng.uniform(90, 420), 2),
                "description": "Schoolkosten",
            })

        # --- wealth building ----------------------------------------------
        if save_rate > 0:
            monthly_save = round(income * save_rate, 2)
            if monthly_save >= 10:
                txns.append({
                    "timestamp": f"{month}-28T20:00:00",
                    "merchant": "Overschrijving spaarrekening",
                    "category": "savings_transfer",
                    "amount": -monthly_save,
                    "description": "Sparen",
                })
            if arch["key"] in ("establishing", "family_established", "pre_retirement") \
                    and rng.random() < 0.5:
                txns.append({
                    "timestamp": f"{month}-28T20:05:00",
                    "merchant": rng.choice(catalog.MERCHANTS["investment_contribution"]),
                    "category": "investment_contribution",
                    "amount": -round(rng.uniform(50, 420), 2),
                    "description": "Beleggen",
                })
        if "pension_saving" in arch:
            txns.append({
                "timestamp": f"{month}-28T20:10:00",
                "merchant": "KBC Pensioensparen",
                "category": "pension_savings",
                "amount": -round(_pick(rng, arch["pension_saving"]), 2),
                "description": "Pensioensparen",
            })

        # --- occasional life events --------------------------------------
        if rng.random() < 0.07:
            txns.append({
                "timestamp": f"{month}-{rng.randint(5, 25):02d}T15:00:00",
                "merchant": rng.choice(catalog.MERCHANTS["travel"]),
                "category": "travel",
                "amount": -round(rng.uniform(380, 2400), 2),
                "description": "Reis",
            })
        if rng.random() < 0.06 and housing.startswith("owner"):
            txns.append({
                "timestamp": f"{month}-{rng.randint(5, 25):02d}T15:00:00",
                "merchant": rng.choice(catalog.MERCHANTS["home_improvement"]),
                "category": "home_improvement",
                "amount": -round(rng.uniform(180, 3200), 2),
                "description": "Verbouwing",
            })
        # A slice of the population shows a coherent family-expansion pattern,
        # so the playbook is exercised by more than the hero persona. Single
        # scattered purchases would never cross the threshold - and should not.
        if expecting and i <= 2:
            for cat, lo, hi in (("baby_retail", 28, 95), ("prenatal_health", 22, 70)):
                if rng.random() < 0.75:
                    txns.append({
                        "timestamp": f"{month}-{rng.randint(5, 25):02d}T15:00:00",
                        "merchant": rng.choice(catalog.MERCHANTS[cat]),
                        "category": cat,
                        "amount": -round(rng.uniform(lo, hi), 2),
                        "description": catalog.label_for(cat),
                    })
            if i == 0 and rng.random() < 0.6:
                txns.append({
                    "timestamp": f"{month}-14T15:00:00",
                    "merchant": rng.choice(catalog.MERCHANTS["nursery_furniture"]),
                    "category": "nursery_furniture",
                    "amount": -round(rng.uniform(320, 880), 2),
                    "description": "Babykamer",
                })

    txns.sort(key=lambda t: t["timestamp"])
    return customer, txns


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------
def _insert_customer(conn, customer: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO customers(customer_id, first_name, last_name, age, "
        "household_type, partner_name, children, housing, city, employer, "
        "declared_json, is_hero, hero_key, hero_label, created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
        (
            customer["customer_id"], customer["first_name"], customer["last_name"],
            customer["age"], customer["household_type"], customer["partner_name"],
            customer["children"], customer["housing"], customer["city"],
            customer["employer"], db.dumps(customer.get("declared", {})),
            customer["is_hero"], customer["hero_key"], customer["hero_label"],
        ),
    )


def _insert_transactions(conn, customer_id: str, txns: list[dict]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO transactions(transaction_id, customer_id, timestamp, "
        "merchant, category, amount, description, channel, injected) "
        "VALUES(?,?,?,?,?,?,?,?,0)",
        [
            (f"TX-{uuid.uuid4().hex[:16]}", customer_id, t["timestamp"], t["merchant"],
             t["category"], round(t["amount"], 2), t["description"],
             t.get("channel", "core_banking"))
            for t in txns
        ],
    )


def is_seeded() -> bool:
    return db.get_meta("seeded_version") == f"{config.SEED}:{config.N_CUSTOMERS}:{config.N_MONTHS}"


def seed(force: bool = False) -> dict:
    """Generate the world. Idempotent unless `force`."""
    db.init_db()
    if is_seeded() and not force:
        row = db.query_one("SELECT COUNT(*) AS n FROM customers")
        return {"status": "already_seeded", "customers": row["n"]}

    rng = random.Random(config.SEED)
    fake = Faker("nl_BE")
    Faker.seed(config.SEED)
    ref = date.fromisoformat(config.REFERENCE_DATE)

    built: list[tuple[dict, list[dict]]] = []
    for cid in personas.HERO_ORDER:
        built.append(personas.HERO_BUILDERS[cid](ref))
    for index in range(1, max(0, config.N_CUSTOMERS - len(personas.HERO_ORDER)) + 1):
        built.append(_generate_customer(rng, fake, index, ref, config.N_MONTHS))

    total_txns = 0
    with db.connect() as conn:
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM customers")
        conn.execute("DELETE FROM features")
        conn.execute("DELETE FROM twins")
        conn.execute("DELETE FROM twin_history")
        conn.execute("DELETE FROM pipeline_trace")
        for customer, txns in built:
            _insert_customer(conn, customer)
            _insert_transactions(conn, customer["customer_id"], txns)
            total_txns += len(txns)

    # Replay every history through the SAME Tier 1 updater the live queue uses.
    for customer, txns in built:
        state = features.rebuild(txns, customer.get("opening_savings", 0.0))
        twin_engine.save_features(customer["customer_id"], state)
        record = {k: v for k, v in customer.items()
                  if k not in ("declared", "opening_savings")}
        twin = twin_engine.build_twin(record, state, previous=None)
        twin_engine.save_twin(twin)

    db.set_meta("seeded_version", f"{config.SEED}:{config.N_CUSTOMERS}:{config.N_MONTHS}")
    db.set_meta("reference_date", config.REFERENCE_DATE)
    return {
        "status": "seeded",
        "customers": len(built),
        "transactions": total_txns,
        "months": config.N_MONTHS,
        "seed": config.SEED,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(seed(force=True), indent=2))
