/* ==========================================================================
   CUSTOMER APP - KBC Mobile with Future Me.

   Three tabs, like KBC Mobile keeps it simple:
     Start      - what today's app shows: accounts, recent transactions
     Future Me  - the timeline of what is coming, and "what if"
     About me   - what we think we know, and the customer's corrections

   The phone sits next to a small presenter panel with the demo events.
   ========================================================================== */

import { api, waitForEvent } from "../api.js";
import { Icon, PipelineStages, toast } from "../components.js";
import { escapeHtml as h, initials, money, pct } from "../format.js";

const NAV = [
  { id: "start",  label: "Start",     icon: "wallet" },
  { id: "future", label: "Future Me", icon: "route" },
  { id: "about",  label: "About me",  icon: "user" },
];

const WHAT_IF_DEFAULT = { extra: 0, sabbatical: false };
const SABBATICAL_MONTHS = 6;
const YEARS_IN_RETIREMENT = 20;

export const customerState = {
  customerId: null,
  tab: "future",
  busy: false,
  whatIf: { ...WHAT_IF_DEFAULT },
  moves: {},            // goal id -> months moved, "retirement" -> EUR/month, after the last change
  newTitles: [],        // timeline milestones that appeared with the last change
  lastEvent: null,      // { label, ms, version, stages }
  whyOpen: false,
  stagesOpen: false,
};

export function resetCustomerState() {
  customerState.whatIf = { ...WHAT_IF_DEFAULT };
  customerState.moves = {};
  customerState.newTitles = [];
  customerState.lastEvent = null;
  customerState.whyOpen = false;
}

/* ==========================================================================
   Future maths - mirrors twin_engine._build_goals and _retirement_projection
   so a "what if" preview gives the same dates the engine would.
   ========================================================================== */
function project(twin, whatIf = WHAT_IF_DEFAULT) {
  const d = twin.derived_features;
  const r = d.retirement || {};
  const pause = whatIf.sabbatical ? SABBATICAL_MONTHS : 0;
  const pot = (d.monthly_savings_contribution || 0) + whatIf.extra;

  const open = twin.goals.filter((g) =>
    g.id !== "retirement_readiness" && g.current_amount < g.target_amount);
  const weightTotal = open.reduce((sum, g) => sum + 1 / g.priority, 0) || 1;

  const goals = {};
  for (const g of twin.goals) {
    if (g.id === "retirement_readiness") continue;
    if (g.current_amount >= g.target_amount) {
      goals[g.id] = { reached: true, months: 0 };
      continue;
    }
    const monthly = pot * ((1 / g.priority) / weightTotal);
    goals[g.id] = monthly > 0
      ? { months: Math.min(600, Math.ceil((g.target_amount - g.current_amount) / monthly)) + pause, monthly }
      : { months: null, monthly: 0 };
  }

  const years = r.years_to_retirement || 0;
  const baseMonthly = d.monthly_savings_contribution || 0;
  const capital = (r.projected_capital || 0)
    + whatIf.extra * 12 * years
    - (whatIf.sabbatical ? baseMonthly * SABBATICAL_MONTHS : 0);
  const income = r.income_basis || 1;
  const monthlyIncome = (r.estimated_statutory_pension || 0) + Math.max(0, capital) / (12 * YEARS_IN_RETIREMENT);
  const retirement = {
    year: r.retirement_year,
    age: r.target_retirement_age,
    ageSource: r.retirement_age_source,
    yearsLeft: years,
    monthlyIncome,
    incomeShare: monthlyIncome / income,
    targetShare: (r.desired_monthly_income || 0) / income,
  };
  return { goals, retirement };
}

function monthLabel(ref, months) {
  const date = new Date(ref);
  date.setDate(1);
  date.setMonth(date.getMonth() + months);
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

const euro = (text) => String(text || "").replace(/EUR\s?/g, "€");

function moveLabel(months) {
  if (!months) return "";
  const n = Math.abs(months);
  const unit = n === 1 ? "month" : "months";
  return months < 0 ? `${n} ${unit} sooner` : `${n} ${unit} later`;
}

/* ==========================================================================
   Render
   ========================================================================== */
export function renderCustomer(ctx) {
  if (!ctx.twin) return `<div class="page"><div class="skeleton" style="height:260px"></div></div>`;
  return `
  <div class="page">
    <div class="phone-stage">
      ${renderPhone(ctx)}
      ${renderPresenter(ctx)}
    </div>
  </div>`;
}

function renderPhone(ctx) {
  const name = ctx.customer?.customer?.first_name || "";
  return `
  <div class="phone">
    <div class="phone__statusbar"><span>09:41</span></div>
    <div class="m-top">
      <span class="m-avatar">${h(initials(`${name} ${ctx.customer?.customer?.last_name || ""}`))}</span>
      <span class="m-kate">How can I help you? <b>${Icon.kate} Kate</b></span>
      <span class="m-bell">${Icon.bell}</span>
    </div>
    <div class="phone__scroll" id="phone-scroll">
      ${renderTab(ctx)}
    </div>
    <nav class="phone__nav" role="tablist" aria-label="App sections">
      ${NAV.map((item) => `
        <button role="tab" data-tab="${item.id}" aria-selected="${item.id === customerState.tab}">
          ${Icon[item.icon]}<span>${h(item.label)}</span>
        </button>`).join("")}
    </nav>
  </div>`;
}

function renderTab(ctx) {
  switch (customerState.tab) {
    case "start": return renderStart(ctx);
    case "about": return renderAbout(ctx);
    default:      return renderFuture(ctx);
  }
}

/* ==========================================================================
   Start - today's KBC Mobile, looking backwards
   ========================================================================== */
function renderStart({ twin, customer, meta }) {
  const d = twin.derived_features;
  const txns = (customer?.transactions || []).slice(0, 4);
  return `
    <div class="m-accounts">
      <div class="m-account m-account--blue">
        <span class="m-account__icon">${Icon.wallet}</span>
        <span class="m-account__name">Savings account</span>
        <span class="m-account__amount">${money(d.savings_balance)}</span>
      </div>
      <div class="m-account">
        <span class="m-account__icon">${Icon.euro}</span>
        <span class="m-account__name">Left over this month</span>
        <span class="m-account__amount">${money(d.monthly_surplus)}</span>
      </div>
    </div>

    <ul class="m-txns">
      ${txns.map((t) => `
        <li>
          <span class="m-txns__date">${h(t.timestamp.slice(8, 10))}/${h(t.timestamp.slice(5, 7))}</span>
          <span class="m-txns__name">${h(t.merchant)}</span>
          <span class="m-txns__amount">${t.amount > 0 ? "+" : ""}${money(t.amount)}</span>
        </li>`).join("")}
    </ul>

    <h2 class="m-section">For you</h2>
    <button class="m-tip m-tip--hero" data-tab="future">
      <span class="m-tip__icon">${Icon.route}</span>
      <span>
        <span class="m-tip__kicker">New: Future Me</span>
        <span class="m-tip__text">${h(headline(twin, meta, WHAT_IF_DEFAULT))}</span>
        <span class="m-link">See your future ${Icon.chevron}</span>
      </span>
    </button>`;
}

/* ==========================================================================
   Future Me - the timeline
   ========================================================================== */
function renderFuture(ctx) {
  const { twin, customer } = ctx;
  const name = customer?.customer?.first_name || "";
  return `
    <div class="fm-hello">
      <div class="fm-hello__kicker">Future Me</div>
      <div class="fm-hello__title">Hi ${h(name)}, here's what's ahead</div>
    </div>
    ${renderNoticed(twin)}
    <div id="fm-live">${renderLive(ctx)}</div>`;
}

/** Everything that moves while the "what if" slider is dragged. */
function renderLive({ twin, meta }) {
  const whatIf = customerState.whatIf;
  const previewing = whatIf.extra > 0 || whatIf.sabbatical;
  return `
    <section class="fm-hero ${previewing ? "fm-hero--preview" : ""}">
      <div class="fm-hero__text">${h(headline(twin, meta, whatIf))}</div>
      ${previewing ? `<div class="fm-hero__note">Preview. Nothing is saved or moved.</div>` : ""}
    </section>
    ${renderWhatIf()}
    ${renderTimeline(twin, meta)}`;
}

function headline(twin, meta, whatIf) {
  const p = project(twin, whatIf);
  const ref = meta?.reference_date;
  const next = twin.goals
    .filter((g) => p.goals[g.id] && !p.goals[g.id].reached && p.goals[g.id].months)
    .sort((a, b) => p.goals[a.id].months - p.goals[b.id].months)[0];
  // Close to retirement, that is the question that matters most.
  if (next && p.retirement.yearsLeft > 10) {
    return `At this pace, your ${next.title.toLowerCase()} of ${money(next.target_amount)} is ready in ${monthLabel(ref, p.goals[next.id].months)}.`;
  }
  return `Retirement in ${p.retirement.year}: you're on track for ${money(p.retirement.monthlyIncome)} a month, ${pct(p.retirement.incomeShare)} of your current income.`;
}

/** Guesses the customer has not answered yet. */
function openGuesses(twin) {
  return (twin.household.possible_changes || [])
    .filter((c) => findCorrection(twin, c.key) === undefined);
}

function renderNoticed(twin) {
  // Below the threshold we keep quiet in the app; it stays visible under "About me".
  const change = openGuesses(twin).find((c) => c.key === "family_expansion" && c.confidence >= 0.5);
  if (!change) return "";
  return `
    <section class="fm-noticed">
      <div class="fm-noticed__head">${Icon.kate}<span>Kate noticed something</span></div>
      <div class="fm-noticed__title">Are you expecting a baby?</div>
      <p class="fm-noticed__text">
        Some recent purchases look like it. We're ${pct(change.confidence)} sure, so it's
        only a guess. We've made room for it in your plan below
        (${h(euro(change.expected_financial_impact).split(",")[0].toLowerCase())}). Is that right?
      </p>
      <div class="fm-noticed__actions">
        <button class="kbc-btn kbc-btn--primary kbc-btn--sm" data-correct="${h(change.key)}" data-value="true">Yes, that's right</button>
        <button class="kbc-btn kbc-btn--secondary kbc-btn--sm" data-correct="${h(change.key)}" data-value="false">No, remove it</button>
      </div>
    </section>`;
}

function renderWhatIf() {
  const w = customerState.whatIf;
  return `
    <section class="fm-whatif">
      <div class="fm-whatif__head">
        <span class="fm-whatif__title">What if…</span>
        ${w.extra || w.sabbatical ? `<button class="m-link" data-whatif-reset="1">Reset</button>` : ""}
      </div>
      <label class="fm-slider">
        <span class="fm-slider__label">I save more each month
          <b>${w.extra ? `+${money(w.extra)}` : "€0"}</b></span>
        <input type="range" min="0" max="500" step="25" value="${w.extra}" data-whatif-extra="1"
               style="--fill:${(w.extra / 500) * 100}%" aria-label="Extra saving per month">
      </label>
      <button class="fm-toggle" data-whatif-sabbatical="1" aria-pressed="${w.sabbatical}">
        <span class="fm-toggle__box">${w.sabbatical ? Icon.check : ""}</span>
        I take a ${SABBATICAL_MONTHS}-month sabbatical
      </button>
    </section>`;
}

function renderTimeline(twin, meta) {
  const ref = meta?.reference_date;
  const whatIf = customerState.whatIf;
  const base = project(twin);
  const now = project(twin, whatIf);
  const goalsById = Object.fromEntries(twin.goals.map((g) => [g.id, g]));

  const achieved = twin.future_timeline.filter((m) => m.kind === "achieved");
  const seen = new Set();
  const ahead = twin.future_timeline.filter((m) => {
    if (m.kind === "achieved") return false;
    if (!m.goal_id) return true;
    if (seen.has(m.goal_id)) return false;
    seen.add(m.goal_id);
    return true;
  });

  const items = ahead.map((m) => {
    const goal = goalsById[m.goal_id];
    const isRetirement = /^Retirement/.test(m.title);
    const assumption = twin.future_timeline.some((x) =>
      x.goal_id && x.goal_id === m.goal_id && x.provenance === "inferred");

    if (isRetirement) {
      const r = now.retirement;
      const moved = Math.round(r.monthlyIncome - base.retirement.monthlyIncome);
      const eventMove = customerState.moves.retirement;
      return timelineItem({
        date: String(r.year),
        icon: Icon.sun,
        title: `Retire at ${r.age}`,
        detail: `Expected income ${money(r.monthlyIncome)} a month: ${pct(r.incomeShare)} of what you earn now. The usual aim is ${pct(r.targetShare)}.`,
        progress: Math.min(1, r.incomeShare / (r.targetShare || 1)),
        warn: r.incomeShare < r.targetShare,
        badge: moved ? `${moved > 0 ? "+" : "-"}${money(Math.abs(moved))} a month` : "",
        eventBadge: eventMove ? `${eventMove > 0 ? "+" : "-"}${money(Math.abs(eventMove))} a month` : "",
        eventGood: eventMove > 0,
        tag: r.ageSource === "assumed" ? `Age ${r.age} is our guess` : "",
      });
    }

    if (goal) {
      const g = now.goals[goal.id] || {};
      const b = base.goals[goal.id] || {};
      const delta = g.months != null && b.months != null ? g.months - b.months : 0;
      const eventMove = customerState.moves[goal.id];
      return timelineItem({
        date: g.months ? monthLabel(ref, g.months) : "No date yet",
        icon: goal.id === "house_deposit" ? Icon.house : Icon.shield,
        title: `${goal.title}: ${money(goal.target_amount)}`,
        detail: g.months
          ? `${money(goal.current_amount)} saved. Putting aside ${money(g.monthly)} a month.`
          : "Nothing is being put aside for this yet.",
        progress: goal.current_amount / goal.target_amount,
        badge: moveLabel(delta),
        eventBadge: moveLabel(eventMove),
        eventGood: eventMove < 0,
        tag: assumption ? "We guessed you want this" : "",
      });
    }

    return timelineItem({
      date: m.date_label, icon: Icon.route, title: euro(m.title), detail: euro(m.detail),
      tag: m.provenance === "inferred" ? "Our guess" : "",
    });
  });

  return `
    <h2 class="m-section">Your timeline</h2>
    <ol class="fm-tl">
      <li class="fm-tl__item fm-tl__item--now">
        <span class="fm-tl__dot"></span>
        <div class="fm-tl__date">Today</div>
        ${achieved.length ? `
          <div class="fm-done">
            ${achieved.map((m) => `
              <span class="fm-done__chip ${customerState.newTitles.includes(m.title) ? "fm-done__chip--new" : ""}">
                ${Icon.check}${h(m.title)}</span>`).join("")}
          </div>` : `<div class="fm-tl__detail">Your starting point.</div>`}
      </li>
      ${items.join("")}
    </ol>`;
}

function timelineItem({ date, icon, title, detail, progress, warn, badge, eventBadge, eventGood = true, tag }) {
  return `
    <li class="fm-tl__item">
      <span class="fm-tl__dot"></span>
      <div class="fm-tl__date">${h(date)}
        ${badge ? `<span class="fm-badge fm-badge--preview">${h(badge)}</span>` : ""}
        ${!badge && eventBadge ? `<span class="fm-badge ${eventGood ? "fm-badge--good" : "fm-badge--bad"}">${h(eventBadge)}</span>` : ""}
      </div>
      <div class="fm-card">
        <span class="fm-card__icon">${icon}</span>
        <div class="fm-card__body">
          <div class="fm-card__title">${h(title)}</div>
          <div class="fm-card__detail">${h(detail)}</div>
          ${progress != null ? `
            <div class="fm-bar"><span class="${warn ? "fm-bar__warn" : ""}"
              style="width:${Math.max(2, Math.min(100, progress * 100))}%"></span></div>` : ""}
          ${tag ? `<div class="fm-card__tag">${h(tag)}</div>` : ""}
        </div>
      </div>
    </li>`;
}

/* ==========================================================================
   About me - what we think, and the customer's answers
   ========================================================================== */
function renderAbout({ twin, meta }) {
  const phase = twin.life_phase;
  const phases = meta?.life_phases || {};
  const r = twin.derived_features.retirement || {};
  const household = twin.household;
  const houseGoal = twin.goals.find((g) => g.id === "house_deposit");
  const plansHouse = findCorrection(twin, "plans_to_buy_house");
  const family = findCorrection(twin, "family_expansion");
  const guesses = openGuesses(twin);

  return `
    <div class="fm-hello">
      <div class="fm-hello__kicker">About me</div>
      <div class="fm-hello__title">Your future is built on this</div>
      <p class="fm-hello__sub">Some of it you told us, some of it is our guess. Your answers always win.</p>
    </div>

    <section class="m-list">
      <div class="m-row">
        <div class="m-row__main">
          <div class="m-row__label">Stage of life</div>
          <select class="m-select" data-field="life_phase" aria-label="Stage of life">
            ${Object.entries(phases).map(([value, label]) => `
              <option value="${h(value)}" ${value === phase.value ? "selected" : ""}>${h(label)}</option>`).join("")}
          </select>
          <div class="m-row__hint">
            ${phase.provenance === "declared" ? "You told us this." : `Our guess from your transactions (${pct(phase.confidence)} sure).`}
            ${phase.provenance !== "declared" ? `<button class="m-link" data-toggle="why">${customerState.whyOpen ? "Hide why" : "Why?"}</button>` : ""}
          </div>
          ${customerState.whyOpen ? `
            <ul class="m-why">${(phase.evidence || []).map((e) => `<li>${h(euro(e.text))}</li>`).join("")}</ul>` : ""}
        </div>
      </div>
      <div class="m-row">
        <div class="m-row__main">
          <div class="m-row__label">Household</div>
          <div class="m-row__value">${h(householdLabel(household))}</div>
        </div>
      </div>
    </section>

    <h2 class="m-section">Your plans</h2>
    <section class="m-list">
      ${yesNoRow("Buy a home", "plans_to_buy_house", plansHouse,
        plansHouse === undefined ? "We guessed this from how you save." : "You told us.")}
      ${yesNoRow("Grow our family", "family_expansion", family,
        family === undefined ? "Only you can tell us this." : "You told us.")}
      <div class="m-row">
        <div class="m-row__main">
          <div class="m-row__label">Retire at</div>
          <div class="m-row__hint">${r.retirement_age_source === "declared" ? "You told us." : "65 is our guess."}</div>
        </div>
        <div class="m-stepper">
          <button data-step="-1" aria-label="Retire a year earlier">${Icon.minus}</button>
          <span>${r.target_retirement_age}</span>
          <button data-step="1" aria-label="Retire a year later">${Icon.plus}</button>
        </div>
      </div>
      ${houseGoal ? `
        <div class="m-row">
          <div class="m-row__main">
            <div class="m-row__label">Home deposit I need</div>
            <div class="m-row__hint">${houseGoal.provenance === "declared" ? "You set this." : "Our estimate."}</div>
          </div>
          <div class="m-amount">
            <span>€</span>
            <input type="number" min="1000" step="1000" value="${Math.round(houseGoal.target_amount)}"
                   data-goal-target="${h(houseGoal.id)}" aria-label="Home deposit target">
          </div>
        </div>` : ""}
    </section>

    ${guesses.length ? `
      <h2 class="m-section">Things we're not sure about</h2>
      <section class="m-list">
        ${guesses.map((c) => `
          <div class="m-row">
            <div class="m-row__main">
              <div class="m-row__label">${h(c.label)}</div>
              <div class="m-row__hint">${pct(c.confidence)} sure. ${c.confidence < 0.5 ? "Too unsure to act on." : "Part of your plan until you say otherwise."}</div>
            </div>
            <button class="kbc-btn kbc-btn--secondary kbc-btn--sm" data-correct="${h(c.key)}" data-value="false">Not right</button>
          </div>`).join("")}
      </section>` : ""}

    ${twin.corrections.length ? `
      <button class="m-link m-link--center" data-clear-corrections="1">Undo my ${twin.corrections.length} answer${twin.corrections.length > 1 ? "s" : ""}</button>` : ""}`;
}

function yesNoRow(label, field, value, hint) {
  return `
    <div class="m-row">
      <div class="m-row__main">
        <div class="m-row__label">${h(label)}</div>
        <div class="m-row__hint">${h(hint)}</div>
      </div>
      <div class="segmented" role="group" data-segmented="${h(field)}">
        <button type="button" data-value="true" aria-pressed="${value === true}">Yes</button>
        <button type="button" data-value="false" aria-pressed="${value === false}">No</button>
      </div>
    </div>`;
}

function householdLabel(household) {
  const parts = [];
  parts.push(household.partner_name ? `With ${household.partner_name.split(" ")[0]}` : "Just me");
  if (household.children) parts.push(`${household.children} child${household.children > 1 ? "ren" : ""}`);
  parts.push(String(household.housing).replace(/_/g, " ").replace("owner with mortgage", "own home, mortgage"));
  return parts.join(" · ");
}

function findCorrection(twin, field) {
  const found = twin.corrections.find((c) => c.field === field);
  return found ? found.value : undefined;
}

/* ==========================================================================
   Presenter panel - outside the phone
   ========================================================================== */
function renderPresenter({ meta, personas }) {
  const persona = personas.find((p) => p.customer_id === customerState.customerId);
  const actions = meta?.demo_actions || [];
  const suggested = persona?.story?.demo_action;
  const ordered = [...actions].sort((a, b) => (b.key === suggested) - (a.key === suggested));
  const e = customerState.lastEvent;

  return `
  <aside class="presenter">
    ${persona ? `
      <div class="presenter__story">
        <div class="presenter__kicker">${h(persona.hero_label)}</div>
        <div class="presenter__title">${h(persona.story.headline)}</div>
        <p>${h(persona.story.watch_for)}</p>
      </div>` : ""}

    <div class="presenter__label">Something happens in real life</div>
    <div class="presenter__events">
      ${ordered.map((a) => `
        <button class="presenter__event ${a.key === suggested ? "presenter__event--suggested" : ""}"
                data-inject="${h(a.key)}" ${customerState.busy ? "disabled" : ""}>
          <span class="presenter__event-label">${h(eventLabel(a))}</span>
          <span class="presenter__event-amount">${a.amount > 0 ? "+" : ""}${money(a.amount)}</span>
        </button>`).join("")}
    </div>

    <div class="presenter__result" id="presenter-result">
      ${customerState.busy ? `<span class="kbc-dot kbc-dot--busy"></span> Updating the future…` : e ? `
        <span class="kbc-dot"></span>
        Updated in ${e.ms.toFixed(1)} ms
        <button class="m-link" data-toggle-stages="1">${customerState.stagesOpen ? "Hide steps" : "Show steps"}</button>` : `
        <span class="t-muted">Each button sends one transaction. Watch the timeline move.</span>`}
    </div>
    ${e && customerState.stagesOpen ? PipelineStages(e.stages, { complete: true }) : ""}

    <button class="m-link presenter__reset" data-reset="1">Reset the demo</button>
  </aside>`;
}

function eventLabel(action) {
  return {
    "first-salary": "Second salary arrives",
    "crib-purchase": "Buys a crib",
    "large-expense": "Pays for a new kitchen",
    "savings-contribution": "Moves money to savings",
  }[action.key] || action.label.replace(/^Inject /, "");
}

/* ==========================================================================
   Behaviour
   ========================================================================== */
export function bindCustomer(root, ctx, refresh) {
  const on = (selector, event, handler) =>
    root.querySelectorAll(selector).forEach((el) => el.addEventListener(event, handler));

  on("[data-tab]", "click", (e) => {
    customerState.tab = e.currentTarget.dataset.tab;
    refresh({ resetScroll: true });
  });

  on("[data-toggle='why']", "click", () => { customerState.whyOpen = !customerState.whyOpen; refresh(); });
  on("[data-toggle-stages]", "click", () => { customerState.stagesOpen = !customerState.stagesOpen; refresh(); });

  bindWhatIf(root, ctx);

  on("[data-inject]", "click", (e) => runInjection(e.currentTarget.dataset.inject, ctx, refresh));

  on("[data-reset]", "click", async () => {
    customerState.busy = true; refresh();
    await api.reset();
    resetCustomerState();
    customerState.busy = false;
    toast("Demo reset.");
    await refresh({ reload: true });
  });

  on("[data-correct]", "click", (e) => {
    const { correct, value } = e.currentTarget.dataset;
    saveCorrection(correct, value === "true", ctx, refresh);
  });

  on("select[data-field='life_phase']", "change", (e) =>
    saveCorrection("life_phase", e.target.value, ctx, refresh));

  on("[data-segmented] button", "click", (e) => {
    const field = e.currentTarget.closest("[data-segmented]").dataset.segmented;
    saveCorrection(field, e.currentTarget.dataset.value === "true", ctx, refresh);
  });

  on("[data-step]", "click", (e) => {
    const current = ctx.twin.derived_features.retirement?.target_retirement_age || 65;
    const next = Math.max(55, Math.min(72, current + Number(e.currentTarget.dataset.step)));
    saveCorrection("target_retirement_age", next, ctx, refresh);
  });

  on("[data-goal-target]", "change", (e) =>
    saveCorrection(`goal_target:${e.target.dataset.goalTarget}`, Number(e.target.value), ctx, refresh));

  on("[data-clear-corrections]", "click", async () => {
    snapshot(ctx);
    await api.clearCorrections(customerState.customerId);
    toast("Your answers were undone.");
    await refresh({ reload: true });
    compareWith(ctx);
    refresh();
  });
}

/** The slider re-renders only the live part, so dragging stays smooth. */
function bindWhatIf(root, ctx) {
  const live = root.querySelector("#fm-live");
  if (!live) return;
  const rerender = () => { live.innerHTML = renderLive(ctx); bindWhatIf(root, ctx); };

  live.querySelector("[data-whatif-extra]")?.addEventListener("input", (e) => {
    customerState.whatIf.extra = Number(e.target.value);
    e.target.style.setProperty("--fill", `${(customerState.whatIf.extra / 500) * 100}%`);
    const label = live.querySelector(".fm-slider__label b");
    if (label) label.textContent = customerState.whatIf.extra ? `+${money(customerState.whatIf.extra)}` : "€0";
    // Swap everything except the slider itself, which the user is holding.
    const fresh = document.createElement("div");
    fresh.innerHTML = renderLive(ctx);
    live.querySelector(".fm-hero").replaceWith(fresh.querySelector(".fm-hero"));
    live.querySelector(".fm-tl").replaceWith(fresh.querySelector(".fm-tl"));
    const head = live.querySelector(".fm-whatif__head");
    head.replaceWith(fresh.querySelector(".fm-whatif__head"));
    live.querySelector("[data-whatif-reset]")?.addEventListener("click", resetWhatIf);
  });
  live.querySelector("[data-whatif-extra]")?.addEventListener("change", rerender);
  live.querySelector("[data-whatif-sabbatical]")?.addEventListener("click", () => {
    customerState.whatIf.sabbatical = !customerState.whatIf.sabbatical;
    rerender();
  });
  live.querySelector("[data-whatif-reset]")?.addEventListener("click", resetWhatIf);

  function resetWhatIf() {
    customerState.whatIf = { ...WHAT_IF_DEFAULT };
    rerender();
  }
}

/* --- remember dates before a change, so the timeline can say what moved --- */
let before = null;

function snapshot(ctx) {
  const p = project(ctx.twin);
  before = {
    goals: Object.fromEntries(Object.entries(p.goals).map(([id, g]) => [id, g.months])),
    retirement: p.retirement.monthlyIncome,
    titles: ctx.twin.future_timeline.map((m) => m.title),
  };
}

function compareWith(ctx) {
  if (!before) return;
  const p = project(ctx.twin);
  const moves = {};
  for (const [id, g] of Object.entries(p.goals)) {
    const old = before.goals[id];
    if (old != null && g.months != null && g.months !== old) moves[id] = g.months - old;
  }
  const income = Math.round(p.retirement.monthlyIncome - before.retirement);
  if (income) moves.retirement = income;
  customerState.moves = moves;
  customerState.newTitles = ctx.twin.future_timeline
    .map((m) => m.title).filter((t) => !before.titles.includes(t));
  before = null;
}

async function saveCorrection(field, value, ctx, refresh) {
  try {
    snapshot(ctx);
    await api.correct(customerState.customerId, field, value, "Set by me");
    await refresh({ reload: true });
    compareWith(ctx);
    toast("Saved. Your future is updated.");
    refresh();
  } catch (error) {
    toast(`Could not save: ${error.message}`);
  }
}

async function runInjection(actionKey, ctx, refresh) {
  const action = (ctx.meta?.demo_actions || []).find((a) => a.key === actionKey);
  customerState.busy = true;
  customerState.whatIf = { ...WHAT_IF_DEFAULT };
  snapshot(ctx);
  await refresh();

  try {
    const accepted = await api.inject(customerState.customerId, actionKey);
    const trace = await waitForEvent(accepted.event_id);
    customerState.lastEvent = {
      label: action ? eventLabel(action) : "Event",
      ms: trace.total_ms || 0,
      version: trace.twin_version,
      stages: trace.stages,
    };
    customerState.busy = false;
    customerState.tab = "future";
    await refresh({ reload: true });
    compareWith(ctx);
    refresh();
  } catch (error) {
    customerState.busy = false;
    toast(`Event failed: ${error.message}`);
    refresh();
  }
}
