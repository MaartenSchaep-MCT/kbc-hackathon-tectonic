"""The Financial Twin data model.

Design rule that runs through the whole file: nothing is allowed to look like
a fact unless it *is* one. Every inference carries `provenance`, `confidence`
and `evidence`, so the UI can never accidentally render a guess as truth.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# How a value came to exist. This is the single most important field in the
# model - it is what keeps the Twin honest.
Provenance = Literal[
    "observed",   # it happened; a transaction, a balance. Verifiable.
    "derived",    # arithmetic on observed data. Reproducible, not a judgement.
    "inferred",   # a probabilistic conclusion from Tier 2. May be wrong.
    "declared",   # the customer told us. Outranks everything above.
]

PROVENANCE_LABELS: dict[str, str] = {
    "observed": "Observed fact",
    "derived": "Calculated from your data",
    "inferred": "Our assumption",
    "declared": "You told us",
}


class Evidence(BaseModel):
    """One human-readable reason, with the number that backs it up."""
    text: str
    weight: float = 0.0
    provenance: Provenance = "observed"


class Inference(BaseModel):
    """A single conclusion the Twin holds about the customer."""
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
    evidence: list[Evidence] = Field(default_factory=list)
    source: str = "twin_engine.tier2"
    timestamp: str = ""
    label: str = ""

    @property
    def is_fact(self) -> bool:
        return self.provenance in ("observed", "declared")


class PossibleChange(BaseModel):
    """An uncertain household change. Never stated as fact."""
    key: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    expected_financial_impact: str = ""
    provenance: Provenance = "inferred"


class Household(BaseModel):
    type: str
    type_provenance: Provenance = "declared"
    children: int = 0
    partner_name: str | None = None
    housing: str = "unknown"
    possible_changes: list[PossibleChange] = Field(default_factory=list)


class Goal(BaseModel):
    id: str
    title: str
    target_amount: float
    current_amount: float
    monthly_contribution: float
    projected_completion: str | None = None
    months_remaining: int | None = None
    on_track: bool = True
    priority: int = 5
    provenance: Provenance = "derived"
    origin: str = ""             # which playbook or correction created it
    explanation: str = ""

    @property
    def progress(self) -> float:
        if self.target_amount <= 0:
            return 0.0
        return min(1.0, self.current_amount / self.target_amount)


class Risk(BaseModel):
    id: str
    label: str
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance = "derived"
    evidence: list[Evidence] = Field(default_factory=list)
    mitigation: str = ""


class Intent(BaseModel):
    id: str
    label: str
    horizon: Literal["short_term", "long_term"]
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance = "inferred"
    evidence: list[Evidence] = Field(default_factory=list)


class Signal(BaseModel):
    """Tier 2 output: a scored, explainable behavioural signal."""
    id: str
    label: str
    score: float = Field(ge=0.0, le=1.0)
    threshold: float
    triggered: bool
    evidence: list[Evidence] = Field(default_factory=list)
    provenance: Provenance = "inferred"
    suppressed_by_customer: bool = False


class Milestone(BaseModel):
    """One dot on the Future Me timeline."""
    year: int
    date_label: str
    title: str
    detail: str = ""
    kind: Literal["achieved", "in_progress", "projected", "life_event"] = "projected"
    confidence: float = 1.0
    provenance: Provenance = "derived"
    goal_id: str | None = None


class NextBestAction(BaseModel):
    """Help the customer progress. Explicitly NOT a product pitch."""
    id: str
    title: str
    why: str
    goal_id: str | None = None
    effort: Literal["low", "medium", "high"] = "low"
    customer_benefit: str = ""


class ActivePlaybook(BaseModel):
    id: str
    name: str
    confidence: float
    customer_explanation: str
    advisor_context: str
    conversation_topics: list[str] = Field(default_factory=list)
    actions: list[NextBestAction] = Field(default_factory=list)


class Explanation(BaseModel):
    """'Why we think this' - rendered verbatim in the UI."""
    field: str
    headline: str
    reasons: list[str] = Field(default_factory=list)
    provenance: Provenance = "inferred"
    confidence: float = 1.0
    correctable: bool = True


class Correction(BaseModel):
    field: str
    value: Any
    note: str = ""
    created_at: str = ""


class Narrative(BaseModel):
    """Tier 3 output. Wording only - every number in here was computed by
    Tier 1/2 before the text was generated."""
    headline: str
    body: str
    generator: Literal["claude", "template"] = "template"
    model: str | None = None
    generated_at: str = ""
    degraded: bool = False       # true when a Claude call was attempted and failed


class FinancialTwin(BaseModel):
    customer_id: str
    version: int
    life_phase: Inference
    household: Household
    goals: list[Goal] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    intent: list[Intent] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    future_timeline: list[Milestone] = Field(default_factory=list)
    playbooks: list[ActivePlaybook] = Field(default_factory=list)
    progress_score: float = 0.0
    progress_breakdown: dict[str, float] = Field(default_factory=dict)
    explanations: list[Explanation] = Field(default_factory=list)
    corrections: list[Correction] = Field(default_factory=list)
    observed_facts: dict[str, Any] = Field(default_factory=dict)
    derived_features: dict[str, Any] = Field(default_factory=dict)
    narrative: Narrative | None = None
    last_updated: str = ""
    change_summary: str = ""
    changed_fields: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# API request/response bodies
# --------------------------------------------------------------------------
class TransactionIn(BaseModel):
    customer_id: str
    merchant: str
    category: str
    amount: float
    description: str = ""
    timestamp: str | None = None
    channel: str = "core_banking"


class CorrectionIn(BaseModel):
    field: str
    value: Any
    note: str = ""


class EventAccepted(BaseModel):
    event_id: str
    customer_id: str
    status: str = "queued"
    queue_depth: int = 0
    message: str = ""
