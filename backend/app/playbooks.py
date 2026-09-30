"""LIFE-MOMENT PLAYBOOKS.

A playbook is the reusable unit of personalisation. It binds a Tier 2 signal
to: the goals that matter at that moment, what the customer could do next,
what changes on their timeline, and what an advisor should know.

Two rules held throughout:

1. Actions are framed around the customer's own goal, never a product.
   "Set aside EUR 150 a month to reach your buffer by March 2027" - not
   "open a savings account". Where a KBC capability is genuinely the
   mechanism, it is named as a means to the customer's end, not the end.
2. Nothing here asserts a life event as fact. `customer_explanation` always
   carries the confidence and the reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GoalTemplate:
    id: str
    title: str
    # Target is a function of the customer's own numbers, not a fixed product.
    target_rule: str                 # human description of the target maths
    target_months_of_spend: float = 0.0
    target_fixed: float = 0.0
    target_multiple_of_income: float = 0.0
    priority: int = 5
    explanation: str = ""
    # Goals in the same group are alternatives, not additions. Several
    # playbooks each want "a buffer"; the customer has one. The engine keeps
    # the strongest and drops the rest, so no euro is counted twice.
    group: str = ""


@dataclass
class ActionTemplate:
    id: str
    title: str
    why: str
    goal_id: str | None = None
    effort: str = "low"
    customer_benefit: str = ""


@dataclass
class Playbook:
    id: str
    name: str
    signal_id: str                   # Tier 2 model that triggers it
    required_signals: list[str] = field(default_factory=list)
    min_confidence: float = 0.55
    customer_explanation: str = ""   # {confidence_pct} available
    advisor_context: str = ""
    conversation_topics: list[str] = field(default_factory=list)
    goals: list[GoalTemplate] = field(default_factory=list)
    actions: list[ActionTemplate] = field(default_factory=list)
    timeline_effects: list[str] = field(default_factory=list)
    suppressed_by: str = ""          # correction field that switches it off


PLAYBOOKS: list[Playbook] = [
    # 1 ---------------------------------------------------------------------
    Playbook(
        id="first_job",
        name="First job",
        signal_id="first_job",
        min_confidence=0.55,
        customer_explanation=(
            "It looks like you have started working - we are {confidence_pct}% "
            "confident. A first stable income is the moment a buffer becomes "
            "realistic, so we have put that first."
        ),
        advisor_context=(
            "Income has just become predictable. The useful conversation is "
            "about structure - buffer first, then whether renting independently "
            "or a longer-term purchase is the actual ambition. Not a product fit."
        ),
        conversation_topics=[
            "How much of the new income feels safe to commit each month",
            "Whether an independent rental is planned in the next 2 years",
            "What the customer actually wants the money to do by age 30",
        ],
        goals=[
            GoalTemplate(
                id="emergency_fund", group="buffer",
                title="Emergency fund",
                target_rule="3 months of your average spending",
                target_months_of_spend=3.0,
                priority=1,
                explanation="Three months of your own spending, not a round number.",
            ),
        ],
        actions=[
            ActionTemplate(
                id="automate_buffer",
                title="Move a fixed amount to savings on payday",
                why="Your salary arrives on a predictable date, so the transfer can be automatic.",
                goal_id="emergency_fund",
                customer_benefit="Reaches your buffer without you deciding each month.",
            ),
            ActionTemplate(
                id="confirm_phase",
                title="Confirm we have your situation right",
                why="We inferred this from your transactions. One tap tells us if we are wrong.",
                customer_benefit="Keeps every KBC channel working from the correct picture.",
            ),
        ],
        timeline_effects=["Adds the emergency-fund completion date",
                          "Brings an independent rental into view"],
    ),
    # 2 ---------------------------------------------------------------------
    Playbook(
        id="moving_out",
        name="Moving out",
        signal_id="moving_out",
        customer_explanation=(
            "Your own rent and utility payments are visible, so we think you "
            "are living independently ({confidence_pct}% confident)."
        ),
        advisor_context=(
            "Fixed costs have stepped up. Check whether the buffer target "
            "still matches the new cost base before discussing anything else."
        ),
        conversation_topics=["Whether the buffer target should rise with the new rent",
                             "Home contents cover - is anything uninsured"],
        goals=[
            GoalTemplate(
                id="emergency_fund", group="buffer", title="Emergency fund",
                target_rule="3 months of your average spending",
                target_months_of_spend=3.0, priority=1,
            ),
        ],
        actions=[
            ActionTemplate(
                id="recalc_buffer", title="Raise your buffer to match your new rent",
                why="Your fixed costs went up, so three months of spending is a bigger number now.",
                goal_id="emergency_fund",
                customer_benefit="Your buffer keeps covering the same length of time.",
            ),
        ],
        timeline_effects=["Marks independent living as achieved"],
    ),
    # 3 ---------------------------------------------------------------------
    Playbook(
        id="first_home",
        name="First home",
        signal_id="first_home_intent",
        suppressed_by="plans_to_buy_house",
        customer_explanation=(
            "Your savings pattern looks like someone working towards a home "
            "({confidence_pct}% confident). If that is not your plan, switch "
            "it off and we will stop suggesting it."
        ),
        advisor_context=(
            "Savings trajectory is consistent with a deposit ambition, but this "
            "is inferred, not declared. Ask before assuming. If the customer "
            "has switched it off, do not reopen it."
        ),
        conversation_topics=["Is buying actually the plan, or is this just saving",
                             "What deposit and registration costs look like in their region"],
        goals=[
            GoalTemplate(
                id="house_deposit", title="Home deposit",
                target_rule="a EUR 50,000 deposit and costs",
                target_fixed=50000.0, priority=2,
                explanation="A working figure for deposit plus registration costs.",
            ),
        ],
        actions=[
            ActionTemplate(
                id="deposit_pace", title="See what monthly amount reaches your deposit on time",
                why="Your projected date moves with your contribution - worth seeing the trade-off.",
                goal_id="house_deposit",
                customer_benefit="Turns a vague ambition into a date you can plan around.",
            ),
        ],
        timeline_effects=["Adds a projected deposit-ready year"],
    ),
    # 4 ---------------------------------------------------------------------
    Playbook(
        id="expecting_baby",
        name="Expecting or welcoming a baby",
        signal_id="possible_family_expansion",
        min_confidence=0.50,
        suppressed_by="family_expansion",
        customer_explanation=(
            "Some recent spending looks like preparing for a baby - we are "
            "{confidence_pct}% confident, which means we are not sure. We have "
            "not told anyone anything, and you can correct this."
        ),
        advisor_context=(
            "PROBABILISTIC, {confidence_pct}%. Do not congratulate and do not "
            "raise it unprompted - it may be a gift or a relative. If the "
            "customer brings it up, the useful content is the cost timeline: "
            "childcare, one income possibly dropping, cover."
        ),
        conversation_topics=[
            "Only if the customer raises it: how a household budget shifts with a child",
            "Whether current income protection matches the household's needs",
        ],
        goals=[
            GoalTemplate(
                id="family_buffer", group="buffer", title="Family buffer",
                target_rule="4 months of your household spending",
                target_months_of_spend=4.0, priority=1,
                explanation="A larger buffer, because a household with a child has less flexibility.",
            ),
        ],
        actions=[
            ActionTemplate(
                id="childcare_forecast", title="See childcare costs in your projection",
                why="Belgian childcare is a real monthly line - better in the plan than a surprise.",
                goal_id="family_buffer",
                customer_benefit="Your savings projection stops being optimistic.",
            ),
            ActionTemplate(
                id="correct_baby", title="Tell us if we have this wrong",
                why="This is a guess from spending patterns. Your correction overrides it permanently.",
                customer_benefit="Stops every KBC channel from acting on a wrong assumption.",
            ),
        ],
        timeline_effects=["Introduces projected childcare costs",
                          "Lowers the savings trajectory accordingly"],
    ),
    # 5 ---------------------------------------------------------------------
    Playbook(
        id="household_merge",
        name="Marriage or household merge",
        signal_id="household_merge",
        min_confidence=0.60,
        customer_explanation=(
            "Your costs look like a shared household ({confidence_pct}% "
            "confident). Shared goals work better than two separate plans."
        ),
        advisor_context=(
            "Two financial pictures are becoming one. Worth checking that "
            "goals and cover are not duplicated or contradicting each other."
        ),
        conversation_topics=["Which goals are genuinely shared and which stay individual",
                             "Duplicate insurance cover across the two histories"],
        goals=[
            GoalTemplate(
                id="shared_buffer", group="buffer", title="Shared household buffer",
                target_rule="3 months of combined household spending",
                target_months_of_spend=3.0, priority=1,
            ),
        ],
        actions=[
            ActionTemplate(
                id="link_goals", title="Turn your buffer into a shared goal",
                why="Both of you contributing to one target is faster than two half-targets.",
                goal_id="shared_buffer",
                customer_benefit="One number both of you can see.",
            ),
        ],
        timeline_effects=["Switches goals to a household view"],
    ),
    # 6 ---------------------------------------------------------------------
    Playbook(
        id="income_increase",
        name="Career income increase",
        signal_id="career_income_increase",
        customer_explanation=(
            "Your income has gone up and stayed up ({confidence_pct}% "
            "confident). Nothing needs to change - but the extra is currently "
            "unallocated."
        ),
        advisor_context=(
            "Income rose and spending has not followed yet. This is the window "
            "where a raise gets absorbed silently. Purely a goal conversation."
        ),
        conversation_topics=["Where the increase should go before it disappears",
                             "Whether existing goal dates can be pulled forward"],
        goals=[],
        actions=[
            ActionTemplate(
                id="allocate_raise", title="Decide where the increase goes",
                why="Unallocated increases are absorbed by everyday spending within a few months.",
                customer_benefit="Your goal dates move earlier instead of standing still.",
            ),
        ],
        timeline_effects=["Pulls existing goal dates earlier"],
    ),
    # 7 ---------------------------------------------------------------------
    Playbook(
        id="financial_stress",
        name="Financial pressure",
        signal_id="financial_stress",
        min_confidence=0.50,
        customer_explanation=(
            "Money is tighter than usual at the moment ({confidence_pct}% "
            "confident). We have paused the longer-term suggestions."
        ),
        advisor_context=(
            "PRIORITY. Buffer is thin or cash flow is negative. Long-term "
            "goal talk is not useful here; stabilising the month is. Treat as "
            "a support conversation, not an opportunity."
        ),
        conversation_topics=["Which fixed costs are genuinely fixed",
                             "Whether this is temporary or structural"],
        goals=[
            GoalTemplate(
                id="stabilise", group="buffer", title="Get back to a positive month",
                target_rule="one month of spending as a minimum buffer",
                target_months_of_spend=1.0, priority=1,
                explanation="A smaller, nearer target - the six-month guideline is not useful right now.",
            ),
        ],
        actions=[
            ActionTemplate(
                id="review_fixed", title="Review your recurring payments",
                why="Recurring costs are the largest controllable block in your month.",
                goal_id="stabilise",
                customer_benefit="Frees up room without changing daily habits.",
            ),
        ],
        timeline_effects=["Pauses long-term milestones",
                          "Adds a near-term stabilisation goal"],
    ),
    # 8 ---------------------------------------------------------------------
    Playbook(
        id="emergency_savings",
        name="Building emergency savings",
        signal_id="building_emergency_savings",
        customer_explanation=(
            "You are putting money aside consistently ({confidence_pct}% "
            "confident). At this pace we can tell you when you will get there."
        ),
        advisor_context=(
            "On track and self-managing. The valuable input is confirming the "
            "target is right for their cost base - not selling anything."
        ),
        conversation_topics=["Whether the buffer target still fits their fixed costs",
                             "What happens to the surplus once the buffer is full"],
        goals=[
            GoalTemplate(
                id="emergency_fund", group="buffer", title="Emergency fund",
                target_rule="3 months of your average spending",
                target_months_of_spend=3.0, priority=1,
            ),
        ],
        actions=[
            ActionTemplate(
                id="see_date", title="See your projected completion date",
                why="A date is easier to hold onto than a percentage.",
                goal_id="emergency_fund",
                customer_benefit="You know when you are done.",
            ),
        ],
        timeline_effects=["Adds the buffer completion year"],
    ),
    # 9 ---------------------------------------------------------------------
    Playbook(
        id="nearing_retirement",
        name="Nearing retirement",
        signal_id="nearing_retirement",
        customer_explanation=(
            "You are close enough to retirement that the projection is now "
            "meaningful ({confidence_pct}% confident). Here is the gap as it "
            "stands, and what closes it."
        ),
        advisor_context=(
            "Projection is live and the gap is quantified. The customer can "
            "act on the monthly contribution lever. Show the projection, let "
            "them choose the trade-off - do not lead with a product."
        ),
        conversation_topics=["Target retirement age - is our assumption right",
                             "The trade-off between retiring earlier and the monthly amount",
                             "What a one-off expense does to the projection"],
        goals=[
            GoalTemplate(
                id="retirement_readiness", title="Retirement readiness",
                target_rule="capital for the gap between pension income and desired income",
                # Priority 1 close to retirement: at this distance the gap
                # matters more than topping up an already-full buffer, and the
                # progress score should say so.
                target_multiple_of_income=1.0, priority=1,
                explanation="Based on your own spending, your assumed retirement age, and a statutory pension estimate.",
            ),
        ],
        actions=[
            ActionTemplate(
                id="test_contribution", title="Test a higher monthly amount",
                why="Your projected gap responds directly to the monthly contribution.",
                goal_id="retirement_readiness",
                customer_benefit="You see the effect before committing to it.",
            ),
            ActionTemplate(
                id="set_retirement_age", title="Set your target retirement age",
                why="We assumed 65. If you are aiming at 62 or 67 the whole projection changes.",
                customer_benefit="The projection reflects your plan, not a default.",
            ),
        ],
        timeline_effects=["Adds the retirement year and the projected gap"],
    ),
    # 10 --------------------------------------------------------------------
    Playbook(
        id="retirement",
        name="Retirement",
        signal_id="retirement",
        min_confidence=0.60,
        customer_explanation=(
            "You are receiving pension income ({confidence_pct}% confident). "
            "The question changes from building capital to making it last."
        ),
        advisor_context=(
            "Decumulation phase. Sustainable withdrawal rate and cost base, "
            "not accumulation products."
        ),
        conversation_topics=["Whether current income covers the current cost base",
                             "How long capital lasts at the present rate"],
        goals=[
            GoalTemplate(
                id="income_sustainability", group="buffer", title="Make your capital last",
                target_rule="12 months of spending held as accessible capital",
                target_months_of_spend=12.0, priority=1,
            ),
        ],
        actions=[
            ActionTemplate(
                id="withdrawal_view", title="See how long your capital lasts",
                why="At your current spending, capital has a measurable horizon.",
                goal_id="income_sustainability",
                customer_benefit="Removes the biggest unknown in retirement.",
            ),
        ],
        timeline_effects=["Switches the timeline to a drawdown view"],
    ),
    # 11 --------------------------------------------------------------------
    Playbook(
        id="long_term_wealth",
        name="Long-term horizon",
        signal_id="long_term_horizon",
        min_confidence=0.50,
        customer_explanation=(
            "You are far enough from retirement that small amounts still have "
            "time to work. Here is what your current pace projects to - it is a "
            "long-range estimate, not a promise."
        ),
        advisor_context=(
            "Mid-life, long horizon. The projection is the conversation, not a "
            "product. The customer's own contribution is the only lever that "
            "matters at this distance."
        ),
        conversation_topics=["Whether the assumed retirement age is right",
                             "What the projection looks like at a slightly higher contribution"],
        goals=[
            GoalTemplate(
                id="retirement_readiness", title="Retirement readiness",
                target_rule="capital for the gap between pension income and desired income",
                target_multiple_of_income=1.0, priority=2,
                explanation="A long-range projection from your own spending and contributions.",
            ),
        ],
        actions=[
            ActionTemplate(
                id="set_retirement_age", title="Tell us when you want to stop working",
                why="We assumed 65. Your own target changes the whole projection.",
                customer_benefit="A projection built on your plan instead of a default.",
            ),
        ],
        timeline_effects=["Adds a long-range retirement projection"],
    ),
    # 12 - optional ---------------------------------------------------------
    Playbook(
        id="renovation",
        name="Renovation",
        signal_id="renovation",
        customer_explanation=(
            "Recent spending looks like work on your home ({confidence_pct}% "
            "confident). Renovations usually run longer than planned."
        ),
        advisor_context="Home improvement spending detected. Check it is not eroding the buffer.",
        conversation_topics=["Is the renovation budget separate from the buffer",
                             "Energy work and any available regional support"],
        goals=[
            GoalTemplate(
                id="renovation_budget", title="Renovation budget",
                target_rule="two months of spending held back as contingency",
                target_months_of_spend=2.0, priority=3,
            ),
        ],
        actions=[
            ActionTemplate(
                id="ringfence", title="Keep your buffer separate from the renovation",
                why="Renovation overruns are the most common reason a buffer disappears.",
                goal_id="renovation_budget",
                customer_benefit="An overrun stops being an emergency.",
            ),
        ],
        timeline_effects=["Adds a renovation completion estimate"],
    ),
    # 13 - optional ---------------------------------------------------------
    Playbook(
        id="family_life",
        name="Raising children",
        signal_id="family_with_children",
        customer_explanation=(
            "Your household includes children, so we plan around those costs "
            "({confidence_pct}% confident)."
        ),
        advisor_context="Family cost base. Education horizon and cover are the substantive topics.",
        conversation_topics=["Education costs on the 10-18 year horizon",
                             "Whether household cover matches dependants"],
        goals=[
            GoalTemplate(
                id="education_fund", title="Education fund",
                target_rule="EUR 12,000 per child by age 18",
                target_fixed=12000.0, priority=3,
            ),
            GoalTemplate(
                id="family_buffer", group="buffer", title="Family buffer",
                target_rule="4 months of household spending",
                target_months_of_spend=4.0, priority=1,
            ),
        ],
        actions=[
            ActionTemplate(
                id="education_start", title="Start the education horizon early",
                why="An 18-year horizon makes the monthly amount small.",
                goal_id="education_fund",
                customer_benefit="Small now instead of large later.",
            ),
        ],
        timeline_effects=["Adds education milestones per child"],
    ),
]

BY_ID = {p.id: p for p in PLAYBOOKS}
BY_SIGNAL: dict[str, list[Playbook]] = {}
for _p in PLAYBOOKS:
    BY_SIGNAL.setdefault(_p.signal_id, []).append(_p)


def as_dict(p: Playbook) -> dict:
    """Serialise a playbook for the /api/playbooks catalogue endpoint."""
    return {
        "id": p.id,
        "name": p.name,
        "signal_id": p.signal_id,
        "min_confidence": p.min_confidence,
        "customer_explanation": p.customer_explanation,
        "advisor_context": p.advisor_context,
        "conversation_topics": p.conversation_topics,
        "goals": [
            {"id": g.id, "title": g.title, "target_rule": g.target_rule,
             "priority": g.priority}
            for g in p.goals
        ],
        "actions": [
            {"id": a.id, "title": a.title, "why": a.why,
             "customer_benefit": a.customer_benefit}
            for a in p.actions
        ],
        "timeline_effects": p.timeline_effects,
        "suppressed_by": p.suppressed_by,
    }
