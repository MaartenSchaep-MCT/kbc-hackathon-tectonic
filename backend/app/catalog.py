"""Belgian-flavoured synthetic world: categories and merchants.

All merchants are real-world Belgian retail names used purely as realistic
labels on synthetic transactions. No real customer or account data is involved.
"""
from __future__ import annotations

# Money-in categories. Sign convention: amount > 0 means money in.
INCOME_CATEGORIES = {
    "salary",
    "student_income",
    "child_benefit",
    "pension_income",
    "benefits",
    "gift_transfer",
    "investment_income",
}

# Categories that represent building wealth rather than consuming it.
SAVINGS_CATEGORIES = {"savings_transfer", "investment_contribution", "pension_savings"}

# Signal-bearing family categories, kept separate so Tier 2 can score them.
BABY_CATEGORIES = {"baby_retail", "nursery_furniture", "prenatal_health"}

MERCHANTS: dict[str, list[str]] = {
    # --- income ---------------------------------------------------------
    "salary": [
        "Colruyt Group NV", "Barco NV", "Umicore NV", "Proximus NV",
        "KU Leuven", "AZ Groeninge", "Bekaert NV", "Agfa-Gevaert NV",
        "Van Hool NV", "Materialise NV", "Stad Gent", "Telenet Group NV",
    ],
    "student_income": ["Randstad Student", "Studentjob BE", "Accent Jobs", "Tempo-Team"],
    "child_benefit": ["Groeipakket Vlaanderen", "FAMIRIS", "Kindergeld Kas"],
    "pension_income": ["Federale Pensioendienst", "Sigedis Pensioen"],
    "benefits": ["RVA / ONEM", "Mutualiteit CM", "Ziekenfonds Solidaris"],
    "gift_transfer": ["Overschrijving familie", "Overschrijving ouders"],
    "investment_income": ["KBC Asset Management dividend", "Coupon obligatie"],
    # --- housing --------------------------------------------------------
    "rent": ["Huur appartement", "Immo Verhuur BVBA", "Huur studio", "Huur woning"],
    "mortgage": ["Woonkrediet aflossing", "Hypothecair krediet"],
    "utilities": ["Engie Electrabel", "Luminus", "Eneco Belgie", "De Watergroep",
                  "Fluvius", "Farys"],
    "telecom": ["Proximus", "Telenet", "Orange Belgium", "BASE", "Scarlet"],
    # --- daily life -----------------------------------------------------
    "groceries": ["Colruyt", "Delhaize", "Carrefour Market", "Albert Heijn",
                  "Lidl", "ALDI", "OKay", "Spar", "Proxy Delhaize", "Cru"],
    "transport_public": ["NMBS / SNCB", "De Lijn", "MIVB / STIB", "TEC"],
    "fuel": ["Q8", "TotalEnergies", "Lukoil", "Esso Express", "DATS 24"],
    "restaurants": ["Panos", "EXKi", "Le Pain Quotidien", "Quick", "Pizza Hut BE",
                    "Bakkerij Van Hecke", "Brasserie De Markt"],
    "retail": ["ZARA Belgium", "H&M", "JBC", "e5 mode", "MediaMarkt",
               "Krefel", "Bol.com", "Coolblue", "Action", "HEMA"],
    "entertainment": ["Kinepolis", "Spotify BE", "Netflix BE", "Standaard Boekhandel"],
    "subscriptions": ["Spotify BE", "Netflix BE", "Disney+ BE", "Strava"],
    "sport": ["Basic-Fit", "Decathlon", "Sportoase", "JIMS"],
    # --- health ---------------------------------------------------------
    "pharmacy": ["Apotheek Ceulemans", "Multipharma", "Apotheek De Brug", "Pharma.be"],
    "healthcare": ["Huisartsenpraktijk Leuven", "AZ Sint-Jan", "Tandarts Peeters",
                   "UZ Gasthuisberg"],
    "insurance": ["KBC Verzekeringen", "AG Insurance", "Ethias", "Baloise Belgium"],
    # --- family ---------------------------------------------------------
    "childcare": ["Kinderdagverblijf 't Vlindertje", "Stad Leuven Kinderopvang",
                  "Onthaalmoeder Landelijke Kinderopvang", "Creche De Zonnebloem"],
    "baby_retail": ["Dreambaby", "Prenatal", "Baby-Dump", "Orchestra Premaman",
                    "Zeeman Babyhoek"],
    "nursery_furniture": ["IKEA Zaventem", "Dreambaby Kinderkamers", "JYSK",
                          "Babykamer Specialist"],
    "prenatal_health": ["Materniteit UZ Leuven", "Vroedvrouwenpraktijk Bloom",
                        "Apotheek prenatale vitamines", "Echografie Centrum"],
    "school": ["Standaard Boekhandel schoolboeken", "KU Leuven inschrijving",
               "Schoolfactuur GO!"],
    # --- wealth & projects ---------------------------------------------
    "savings_transfer": ["Overschrijving spaarrekening", "KBC Spaarrekening"],
    "investment_contribution": ["KBC Beleggingsplan", "Bolero order", "Pricos fonds"],
    "pension_savings": ["KBC Pensioensparen", "Pensioenspaarfonds"],
    "home_improvement": ["Brico", "GAMMA", "HUBO", "Mr. Bricolage", "IKEA Zaventem",
                         "Keukens Dovy"],
    "travel": ["TUI Belgium", "Brussels Airlines", "Booking.com", "Corendon BE"],
    "other": ["Bancontact betaling", "Domiciliering", "Overschrijving"],
}

# Human labels used in the UI and in advisor context.
CATEGORY_LABELS: dict[str, str] = {
    "salary": "Salary",
    "student_income": "Student income",
    "child_benefit": "Child benefit",
    "pension_income": "Pension income",
    "benefits": "Social benefits",
    "gift_transfer": "Family transfer",
    "investment_income": "Investment income",
    "rent": "Rent",
    "mortgage": "Mortgage",
    "utilities": "Utilities",
    "telecom": "Telecom",
    "groceries": "Groceries",
    "transport_public": "Public transport",
    "fuel": "Fuel",
    "restaurants": "Eating out",
    "retail": "Shopping",
    "entertainment": "Entertainment",
    "subscriptions": "Subscriptions",
    "sport": "Sport",
    "pharmacy": "Pharmacy",
    "healthcare": "Healthcare",
    "insurance": "Insurance",
    "childcare": "Childcare",
    "baby_retail": "Baby shop",
    "nursery_furniture": "Nursery furniture",
    "prenatal_health": "Prenatal care",
    "school": "Education",
    "savings_transfer": "Savings",
    "investment_contribution": "Investing",
    "pension_savings": "Pension saving",
    "home_improvement": "Home improvement",
    "travel": "Travel",
    "other": "Other",
}

# Channels that write into the Twin. In production these are Kafka producers.
CHANNELS = ["core_banking", "kbc_mobile", "kate", "advisor", "insurance", "lending"]

CHANNEL_LABELS = {
    "core_banking": "Core banking",
    "kbc_mobile": "KBC Mobile",
    "kate": "Kate",
    "advisor": "Advisor",
    "insurance": "Insurance",
    "lending": "Lending",
}


def label_for(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def is_income(category: str) -> bool:
    return category in INCOME_CATEGORIES
