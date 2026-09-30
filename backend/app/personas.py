"""The four hero personas.

Their transaction histories are hand-built, not random, because the demo
depends on precise "before" states:

  A  Lotte    - one salary month only, so the Twin still reads 'Studying'.
                Injecting a second salary makes it two consecutive months,
                which is what flips the life phase.
  B  An       - baby-shop + prenatal spending puts family expansion at 45%,
                deliberately BELOW the 50% trigger. Buying baby things is not
                evidence of a baby. The crib purchase is what crosses it, to
                exactly 78% - still an assumption, and correctable.
  C  Marc     - a full pension picture, so a single large expense or an extra
                monthly contribution visibly moves the projection.
  D  Noah     - 15, saving pocket money for driving lessons at 17 and the
                exam at 18 (the Belgian ages). Birthday money or the "what if"
                slider visibly pulls the date in.

Every amount is synthetic.
"""
from __future__ import annotations

from datetime import date

# Demo injections. The API exposes these by key; the frontend renders a button
# per entry. Adding a demo action means adding a dict here, nothing else.
DEMO_ACTIONS: dict[str, dict] = {
    "first-salary": {
        "label": "Inject first salary",
        "merchant": "Barco NV",
        "category": "salary",
        "amount": 2450.00,
        "description": "Salaris september - Barco NV",
        "channel": "core_banking",
        "hint": "A second consecutive employer payment. Watch the life phase.",
    },
    "crib-purchase": {
        "label": "Inject crib purchase",
        "merchant": "Dreambaby Kinderkamers",
        "category": "nursery_furniture",
        "amount": -620.00,
        "description": "Babybed + matras + commode",
        "channel": "core_banking",
        "hint": "Nursery furniture. Watch the confidence, and that it stays an assumption.",
    },
    "large-expense": {
        "label": "Inject EUR 3,000 expense",
        "merchant": "Keukens Dovy",
        "category": "home_improvement",
        "amount": -3000.00,
        "description": "Aanbetaling keuken",
        "channel": "core_banking",
        "hint": "A one-off expense funded from savings. Watch the pension projection.",
    },
    "savings-contribution": {
        "label": "Inject EUR 500 to savings",
        "merchant": "KBC Spaarrekening",
        "category": "savings_transfer",
        "amount": -500.00,
        "description": "Overschrijving naar spaarrekening",
        "channel": "kbc_mobile",
        "hint": "An extra monthly contribution. Watch the projected dates move earlier.",
    },
    "birthday-money": {
        "label": "Inject EUR 150 birthday money to savings",
        "merchant": "KBC Spaarrekening",
        "category": "savings_transfer",
        "amount": -150.00,
        "description": "Verjaardagsgeld naar spaarrekening",
        "channel": "kbc_mobile",
        "hint": "Birthday money goes to savings. Watch the driving licence date.",
    },
}


def _m(ref: date, months_ago: int) -> str:
    """Month key N months before the reference month."""
    total = ref.year * 12 + ref.month - 1 - months_ago
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _txn(month: str, day: int, merchant: str, category: str, amount: float,
         description: str) -> dict:
    return {
        "timestamp": f"{month}-{day:02d}T09:15:00",
        "merchant": merchant,
        "category": category,
        "amount": amount,
        "description": description,
    }


# --------------------------------------------------------------------------
# Persona A - Lotte Vermeulen, 23, graduating student starting her first job
# --------------------------------------------------------------------------
def persona_a(ref: date) -> tuple[dict, list[dict]]:
    customer = {
        "customer_id": "KBC-HERO-A",
        "first_name": "Lotte",
        "last_name": "Vermeulen",
        "age": 23,
        "household_type": "single",
        "partner_name": None,
        "children": 0,
        "housing": "living_with_parents",
        "city": "Leuven",
        "employer": "Barco NV",
        "is_hero": 1,
        "hero_key": "A",
        "hero_label": "First job",
        "declared": {
            "occupation": "Recently graduated - junior engineer at Barco NV",
            "notes": "Declared when opening the account as a student.",
        },
        "opening_savings": 3320.00,
    }

    txns: list[dict] = []
    # Months 11..2 ago: student life. Job income + parental support, low costs.
    for i in range(11, 1, -1):
        month = _m(ref, i)
        txns += [
            _txn(month, 5, "Randstad Student", "student_income", 640.00,
                 "Studentenjob weekendwerk"),
            _txn(month, 3, "Overschrijving ouders", "gift_transfer", 250.00,
                 "Maandelijkse steun ouders"),
            _txn(month, 8, "Colruyt", "groceries", -142.00, "Boodschappen"),
            _txn(month, 16, "Delhaize", "groceries", -78.50, "Boodschappen"),
            _txn(month, 12, "NMBS / SNCB", "transport_public", -49.00,
                 "Treinabonnement student"),
            _txn(month, 20, "Panos", "restaurants", -31.20, "Lunch campus"),
            _txn(month, 22, "Proximus", "telecom", -15.00, "Mobiel abonnement"),
            _txn(month, 25, "Basic-Fit", "sport", -24.99, "Fitness abonnement"),
            _txn(month, 27, "Spotify BE", "subscriptions", -10.99, "Spotify Premium"),
        ]
        if i in (11, 8, 5, 2):
            txns.append(_txn(month, 18, "ZARA Belgium", "retail", -64.00, "Kleding"))
        if i == 9:
            txns.append(_txn(month, 14, "KU Leuven inschrijving", "school", -1122.00,
                             "Inschrijvingsgeld academiejaar"))

    # 1 month ago: graduated. First salary lands, student income stops.
    m1 = _m(ref, 1)
    txns += [
        _txn(m1, 28, "Barco NV", "salary", 2450.00, "Salaris - Barco NV"),
        _txn(m1, 8, "Colruyt", "groceries", -168.00, "Boodschappen"),
        _txn(m1, 17, "Delhaize", "groceries", -92.00, "Boodschappen"),
        _txn(m1, 12, "NMBS / SNCB", "transport_public", -62.00, "Treinabonnement"),
        _txn(m1, 21, "Panos", "restaurants", -38.40, "Lunch"),
        _txn(m1, 22, "Proximus", "telecom", -22.00, "Mobiel abonnement"),
        _txn(m1, 25, "Basic-Fit", "sport", -24.99, "Fitness abonnement"),
        _txn(m1, 27, "Spotify BE", "subscriptions", -10.99, "Spotify Premium"),
        _txn(m1, 29, "Overschrijving spaarrekening", "savings_transfer", -200.00,
             "Sparen"),
    ]

    # Current month: everyday spending, but NO salary yet. That is the gap the
    # demo closes - the Twin should still read 'Studying' until it arrives.
    m0 = _m(ref, 0)
    txns += [
        _txn(m0, 6, "Colruyt", "groceries", -151.00, "Boodschappen"),
        _txn(m0, 14, "ALDI", "groceries", -61.30, "Boodschappen"),
        _txn(m0, 11, "NMBS / SNCB", "transport_public", -62.00, "Treinabonnement"),
        _txn(m0, 19, "EXKi", "restaurants", -29.80, "Lunch"),
        _txn(m0, 22, "Proximus", "telecom", -22.00, "Mobiel abonnement"),
        _txn(m0, 25, "Basic-Fit", "sport", -24.99, "Fitness abonnement"),
    ]
    return customer, txns


# --------------------------------------------------------------------------
# Persona B - An De Smet, 31, couple, possible family expansion
# --------------------------------------------------------------------------
def persona_b(ref: date) -> tuple[dict, list[dict]]:
    customer = {
        "customer_id": "KBC-HERO-B",
        "first_name": "An",
        "last_name": "De Smet",
        "age": 31,
        "household_type": "couple",
        "partner_name": "Jeroen Willems",
        "children": 0,
        "housing": "renting",
        "city": "Gent",
        "employer": "Umicore NV",
        "is_hero": 1,
        "hero_key": "B",
        "hero_label": "Expecting a baby",
        "declared": {
            "occupation": "Process engineer at Umicore NV",
            "household": "Living with partner Jeroen since 2023",
            "notes": "Household type and partner were declared by the customer.",
        },
        "opening_savings": 14200.00,
    }

    txns: list[dict] = []
    for i in range(11, -1, -1):
        month = _m(ref, i)
        txns += [
            _txn(month, 27, "Umicore NV", "salary", 3180.00, "Salaris - Umicore NV"),
            _txn(month, 25, "Materialise NV", "salary", 2740.00,
                 "Salaris partner - Materialise NV"),
            _txn(month, 1, "Immo Verhuur BVBA", "rent", -1150.00, "Huur appartement"),
            _txn(month, 3, "Engie Electrabel", "utilities", -132.00, "Energie"),
            _txn(month, 3, "De Watergroep", "utilities", -28.00, "Water"),
            _txn(month, 4, "Telenet", "telecom", -64.00, "Internet + TV"),
            _txn(month, 5, "KBC Verzekeringen", "insurance", -78.00,
                 "Woning- en familiale verzekering"),
            _txn(month, 7, "Colruyt", "groceries", -288.00, "Boodschappen"),
            _txn(month, 15, "Delhaize", "groceries", -196.00, "Boodschappen"),
            _txn(month, 21, "OKay", "groceries", -74.00, "Boodschappen"),
            _txn(month, 9, "Q8", "fuel", -78.00, "Brandstof"),
            _txn(month, 18, "De Lijn", "transport_public", -32.00, "Abonnement"),
            _txn(month, 13, "Brasserie De Markt", "restaurants", -68.00, "Uit eten"),
            _txn(month, 24, "Netflix BE", "subscriptions", -13.99, "Netflix"),
            _txn(month, 28, "Overschrijving spaarrekening", "savings_transfer", -400.00,
                 "Sparen"),
            _txn(month, 28, "KBC Beleggingsplan", "investment_contribution", -150.00,
                 "Maandelijks beleggen"),
        ]
        if i in (10, 7, 4):
            txns.append(_txn(month, 20, "TUI Belgium", "travel", -640.00, "Vakantie"))
        if i in (9, 6, 2):
            txns.append(_txn(month, 16, "MediaMarkt", "retail", -189.00, "Elektronica"))

    # Last 3 months: the early, ambiguous signals. Baby-shop and prenatal
    # spending only - deliberately NOT enough to conclude anything.
    m2, m1, m0 = _m(ref, 2), _m(ref, 1), _m(ref, 0)
    txns += [
        _txn(m2, 19, "Dreambaby", "baby_retail", -34.50, "Babykleding"),
        _txn(m1, 11, "Apotheek Ceulemans", "prenatal_health", -28.40,
             "Prenatale vitaminen"),
        _txn(m1, 23, "Prenatal", "baby_retail", -43.90, "Babyartikelen"),
        _txn(m0, 9, "Vroedvrouwenpraktijk Bloom", "prenatal_health", -24.00,
             "Consultatie"),
        _txn(m0, 17, "Apotheek Ceulemans", "pharmacy", -19.80, "Apotheek"),
    ]
    return customer, txns


# --------------------------------------------------------------------------
# Persona C - Marc Peeters, 58, nearing retirement
# --------------------------------------------------------------------------
def persona_c(ref: date) -> tuple[dict, list[dict]]:
    customer = {
        "customer_id": "KBC-HERO-C",
        "first_name": "Marc",
        "last_name": "Peeters",
        "age": 58,
        "household_type": "couple",
        "partner_name": "Katrien Maes",
        "children": 2,
        "housing": "owner_with_mortgage",
        "city": "Mechelen",
        "employer": "Bekaert NV",
        "is_hero": 1,
        "hero_key": "C",
        "hero_label": "Nearing pension",
        "declared": {
            "occupation": "Team lead at Bekaert NV, 31 years of service",
            "household": "Married, two adult children no longer at home",
            "notes": "Retirement age has NOT been declared - 65 is our assumption.",
        },
        "opening_savings": 68000.00,
    }

    txns: list[dict] = []
    for i in range(11, -1, -1):
        month = _m(ref, i)
        txns += [
            _txn(month, 26, "Bekaert NV", "salary", 4100.00, "Salaris - Bekaert NV"),
            _txn(month, 2, "Woonkrediet aflossing", "mortgage", -780.00,
                 "Hypothecair krediet"),
            _txn(month, 3, "Luminus", "utilities", -168.00, "Energie"),
            _txn(month, 3, "Farys", "utilities", -34.00, "Water"),
            _txn(month, 4, "Proximus", "telecom", -72.00, "Internet + mobiel"),
            _txn(month, 5, "KBC Verzekeringen", "insurance", -164.00,
                 "Woning, auto en hospitalisatie"),
            _txn(month, 7, "Colruyt", "groceries", -342.00, "Boodschappen"),
            _txn(month, 16, "Carrefour Market", "groceries", -188.00, "Boodschappen"),
            _txn(month, 10, "TotalEnergies", "fuel", -124.00, "Brandstof"),
            _txn(month, 13, "Huisartsenpraktijk Leuven", "healthcare", -42.00,
                 "Consultatie"),
            _txn(month, 14, "Multipharma", "pharmacy", -38.00, "Apotheek"),
            _txn(month, 20, "Brasserie De Markt", "restaurants", -96.00, "Uit eten"),
            _txn(month, 23, "Standaard Boekhandel", "entertainment", -28.00, "Boeken"),
            _txn(month, 28, "Overschrijving spaarrekening", "savings_transfer", -300.00,
                 "Sparen"),
            _txn(month, 28, "KBC Pensioensparen", "pension_savings", -85.00,
                 "Pensioensparen fiscaal"),
            _txn(month, 28, "KBC Beleggingsplan", "investment_contribution", -200.00,
                 "Maandelijks beleggen"),
        ]
        if i in (11, 5):
            txns.append(_txn(month, 21, "TUI Belgium", "travel", -1240.00, "Reis"))
        if i in (8, 3):
            txns.append(_txn(month, 15, "Brico", "home_improvement", -186.00,
                             "Tuin en onderhoud"))
        if i == 6:
            txns.append(_txn(month, 12, "KBC Asset Management dividend",
                             "investment_income", 412.00, "Dividend"))
    return customer, txns


# --------------------------------------------------------------------------
# Persona D - Noah Claes, 15, saving for a driving licence
# --------------------------------------------------------------------------
def persona_d(ref: date) -> tuple[dict, list[dict]]:
    customer = {
        "customer_id": "KBC-HERO-D",
        "first_name": "Noah",
        "last_name": "Claes",
        "age": 15,
        "household_type": "single",
        "partner_name": None,
        "children": 0,
        "housing": "living_with_parents",
        "city": "Hasselt",
        "employer": None,
        "is_hero": 1,
        "hero_key": "D",
        "hero_label": "Driving licence",
        "declared": {
            "occupation": "Secondary school pupil",
            "notes": "Youth account, opened by his parents.",
        },
        "opening_savings": 310.00,
    }

    txns: list[dict] = []
    for i in range(11, -1, -1):
        month = _m(ref, i)
        txns += [
            _txn(month, 1, "Overschrijving ouders", "gift_transfer", 60.00, "Zakgeld"),
            _txn(month, 2, "Overschrijving spaarrekening", "savings_transfer", -40.00,
                 "Sparen voor rijbewijs"),
            _txn(month, 9, "De Lijn", "transport_public", -6.00, "Busticket"),
            _txn(month, 14, "Carrefour Express", "groceries", -7.50, "Snacks"),
        ]
        if i in (10, 6, 3):
            txns.append(_txn(month, 20, "Game Mania", "entertainment", -24.99, "Game"))
    return customer, txns


HERO_BUILDERS = {
    "KBC-HERO-A": persona_a,
    "KBC-HERO-B": persona_b,
    "KBC-HERO-C": persona_c,
    "KBC-HERO-D": persona_d,
}

HERO_ORDER = ["KBC-HERO-D", "KBC-HERO-A", "KBC-HERO-B", "KBC-HERO-C"]

HERO_STORIES = {
    "KBC-HERO-D": {
        "headline": "Noah wants to drive at 18",
        "setup": "He saves EUR 40 of his pocket money each month for driving lessons.",
        "demo_action": "birthday-money",
        "watch_for": "Lessons start at 17. The money for them is ready sooner.",
    },
    "KBC-HERO-A": {
        "headline": "Lotte just graduated",
        "setup": "Her Twin still reads 'Studying': one salary payment is not a pattern.",
        "demo_action": "first-salary",
        "watch_for": "Life phase flips to 'Starting career' and the timeline redraws.",
    },
    "KBC-HERO-B": {
        "headline": "An's household is changing",
        "setup": "Family expansion sits at 45% - below the threshold to act on.",
        "demo_action": "crib-purchase",
        "watch_for": "Confidence rises to 78%. It stays an assumption you can correct.",
    },
    "KBC-HERO-C": {
        "headline": "Marc is seven years from retirement",
        "setup": "His projected gap is real and his contribution is the lever.",
        "demo_action": "large-expense",
        "watch_for": "The pension projection and the shortfall both move.",
    },
}
