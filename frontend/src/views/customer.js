/* ==========================================================================
   CUSTOMER APP - a mobile banking experience, not an admin dashboard.

   Rendered inside a 390x844 phone frame on desktop, full-bleed on a real
   phone. Four sections behind a bottom navigation, exactly as KBC Mobile
   organises itself: Home, Goals, Future Me, My Twin.
   ========================================================================== */

import { api, waitForEvent } from "../api.js";
import {
  ConfidenceMeter, EvidenceList, Icon, KbcBottomNavigation, KbcCard,
  KbcFormField, KbcGoalCard, KbcInfoBanner, KbcPrimaryButton, KbcProgressBar,
  KbcSecondaryButton, KbcSegmented, KbcStatusChip, KbcTimeline, KbcTwinInsight,
  PipelineStages, ProvenanceChip, toast,
} from "../components.js";
import { escapeHtml as h, money, pct } from "../format.js";

const NAV = [
  { id: "home",   label: "Home",      icon: "home" },
  { id: "goals",  label: "Goals",     icon: "target" },
  { id: "future", label: "Future Me", icon: "route" },
  { id: "twin",   label: "My Twin",   icon: "sliders" },
];

const DEMO_ICONS = {
  "first-salary": Icon.euro,
  "crib-purchase": Icon.crib,
  "large-expense": Icon.receipt,
  "savings-contribution": Icon.piggy,
};

export const customerState = {
  customerId: null,
  tab: "home",
  whyOpen: false,
  sheet: null,          // null | "twin"
  pipeline: null,       // { stages, activeIndex, complete, label }
  changed: [],          // Twin fields that changed on the last event
  busy: false,
};

/* ==========================================================================
   Render
   ========================================================================== */
export function renderCustomer(ctx) {
  const { personas, twin, customer, meta } = ctx;
  if (!twin) return `<div class="page"><div class="skeleton" style="height:260px"></div></div>`;

  return `
  <div class="page">
    <div class="page__inner">
      <div class="phone-stage">
        ${renderPhone(ctx)}
        <aside class="stack" style="flex:1;min-width:300px;max-width:440px">
          ${renderPersonaPicker(personas, customerState.customerId)}
          ${renderDemoControls(meta, twin)}
          ${renderPipelineCard()}
          ${renderTierNote(meta, twin)}
        </aside>
      </div>
    </div>
  </div>`;
}

function renderPhone(ctx) {
  const { twin, customer } = ctx;
  const name = customer ? customer.customer.first_name : "";
  return `
  <div class="phone">
    <div class="phone__statusbar">
      <span>09:41</span>
      <span>KBC Mobile &middot; prototype</span>
      <span>&#9679;&#9679;&#9679;</span>
    </div>
    <div class="phone__header">
      <div class="row row--between">
        <div>
          <div class="t-micro" style="color:var(--kbc-primary-150)">Good morning</div>
          <div class="t-h2">${h(name)}</div>
        </div>
        ${KbcStatusChip({ label: `Twin v${twin.version}`, tone: "solid" })}
      </div>
    </div>
    <div class="phone__scroll" id="phone-scroll">
      ${renderTab(ctx)}
    </div>
    ${KbcBottomNavigation({ items: NAV, active: customerState.tab })}
    ${customerState.sheet === "twin" ? renderEditSheet(ctx) : ""}
  </div>`;
}

function renderTab(ctx) {
  switch (customerState.tab) {
    case "goals":  return renderGoalsTab(ctx);
    case "future": return renderFutureTab(ctx);
    case "twin":   return renderTwinTab(ctx);
    default:       return renderHomeTab(ctx);
  }
}

/* ==========================================================================
   Home
   ========================================================================== */
function renderHomeTab({ twin, customer, meta }) {
  const d = twin.derived_features;
  const narrative = twin.narrative;
  const topGoal = twin.goals[0];
  const changedPhase = customerState.changed.includes("life_phase");

  return `
    ${KbcTwinInsight(twin, { expanded: customerState.whyOpen })}

    ${narrative ? KbcCard({
      label: "What this means",
      body: `
        <div class="t-body t-bold" style="margin-bottom:var(--space-2)">${h(narrative.headline)}</div>
        <p class="t-body">${h(narrative.body)}</p>
        <div class="row" style="margin-top:var(--space-4);gap:var(--space-2)">
          ${KbcStatusChip({
            label: narrative.generator === "claude" ? `Written by Claude` : "Written by template",
            tone: narrative.generator === "claude" ? "accent" : "outline",
          })}
          <span class="kbc-meta">Wording only &mdash; every figure was calculated before this text existed</span>
        </div>`,
    }) : ""}

    ${KbcCard({
      label: "This month",
      body: `
        <div class="grid grid--2" style="gap:var(--space-4)">
          ${miniStat("Money in", money(d.monthly_income), "derived")}
          ${miniStat("Spending", money(d.monthly_spend_core), "derived")}
          ${miniStat("Left over", money(d.monthly_surplus), "derived")}
          ${miniStat("Buffer", `${d.emergency_fund_months} mo`, "derived")}
        </div>`,
    })}

    ${topGoal ? KbcCard({
      label: "Your main goal",
      title: topGoal.title,
      body: KbcGoalCard(topGoal),
    }) : ""}

    ${renderPossibleChanges(twin)}
    ${renderActions(twin)}
    ${renderRisks(twin)}

    ${KbcInfoBanner({
      tone: "neutral",
      text: meta?.synthetic_data_notice || "Synthetic data.",
    })}`;
}

function miniStat(label, value, provenance) {
  return `<div>
    <div class="kbc-card__label">${h(label)}</div>
    <div class="t-h2 t-num" style="margin:2px 0">${h(value)}</div>
    ${ProvenanceChip(provenance, { short: true })}
  </div>`;
}

function renderPossibleChanges(twin) {
  const changes = twin.household.possible_changes || [];
  if (!changes.length) return "";
  return changes.map((change) => KbcCard({
    variant: "kbc-card--tinted",
    label: "Something we are not sure about",
    body: `
      <div class="row row--between" style="align-items:flex-start">
        <div style="min-width:0">
          <div class="t-body t-bold">${h(change.label)}</div>
          <div class="row" style="gap:var(--space-2);margin-top:var(--space-2)">
            ${ConfidenceMeter(change.confidence, { warn: true })}
            <span class="t-small t-bold">${pct(change.confidence)} confident</span>
            ${ProvenanceChip("inferred", { short: true })}
          </div>
        </div>
      </div>
      <p class="t-small t-muted" style="margin-top:var(--space-3)">
        This is an assumption from your spending. It is not a fact, and we have
        not acted on it beyond what you can see here.
      </p>
      ${EvidenceList(change.evidence)}
      ${change.expected_financial_impact ? `
        <div class="kbc-meta" style="margin-top:var(--space-3)">
          If it is right: ${h(change.expected_financial_impact)}
        </div>` : ""}
      <div class="row" style="margin-top:var(--space-4);gap:var(--space-2)">
        ${KbcSecondaryButton({ label: "That's not right", attrs: `data-correct="${h(change.key)}" data-value="false"`, small: true })}
        ${KbcStatusChip({ label: "Your answer overrides us", tone: "outline" })}
      </div>`,
  })).join("");
}

function renderActions(twin) {
  const actions = twin.playbooks.flatMap((p) =>
    p.actions.map((a) => ({ ...a, playbook: p.name, confidence: p.confidence })));
  if (!actions.length) return "";
  return KbcCard({
    label: "What would help most",
    body: `
      <div class="stack stack--sm">
        ${actions.slice(0, 4).map((a) => `
          <div style="padding:var(--space-3) 0;border-bottom:1px solid var(--kbc-divider)">
            <div class="t-small t-bold">${h(a.title)}</div>
            <div class="kbc-meta" style="margin-top:2px">${h(a.why)}</div>
            ${a.customer_benefit ? `
              <div class="t-small" style="margin-top:var(--space-2);color:var(--kbc-success)">
                ${h(a.customer_benefit)}
              </div>` : ""}
          </div>`).join("")}
      </div>
      <div class="kbc-meta" style="margin-top:var(--space-3)">
        These are about your goals. Nothing here is a product offer.
      </div>`,
  });
}

function renderRisks(twin) {
  if (!twin.risks.length) return "";
  return KbcCard({
    label: "Worth knowing",
    body: twin.risks.map((r) => `
      <div class="kbc-banner kbc-banner--${r.severity === "high" ? "danger" : "warning"}"
           style="margin-bottom:var(--space-2)">
        <div>
          <div class="t-small t-bold">${h(r.label)}</div>
          ${EvidenceList(r.evidence)}
          ${r.mitigation ? `<div class="kbc-meta" style="margin-top:var(--space-2)">${h(r.mitigation)}</div>` : ""}
        </div>
      </div>`).join(""),
  });
}

/* ==========================================================================
   Goals
   ========================================================================== */
function renderGoalsTab({ twin }) {
  const household = twin.household;
  return `
    ${KbcCard({
      label: "Progress towards your goals",
      title: pct(twin.progress_score),
      body: `
        ${KbcProgressBar({ value: twin.progress_score, large: true })}
        <div class="grid grid--2" style="margin-top:var(--space-4);gap:var(--space-3)">
          ${Object.entries(twin.progress_breakdown).map(([key, value]) => `
            <div>
              <div class="kbc-meta">${h(key.replace(/_/g, " "))}</div>
              ${KbcProgressBar({ value })}
            </div>`).join("")}
        </div>
        <div class="kbc-meta" style="margin-top:var(--space-4)">
          This is the only score that matters here. It measures your progress,
          not what has been sold to you.
        </div>`,
    })}

    ${twin.goals.length ? KbcCard({
      label: "Your goals",
      body: twin.goals.map(KbcGoalCard).join(""),
    }) : KbcInfoBanner({ text: "No goals are active yet.", tone: "neutral" })}

    ${household.type !== "single" ? KbcCard({
      label: "Household",
      title: householdLabel(household),
      body: `
        <div class="fact-list">
          <div class="fact"><span class="fact__label">Household type</span>
            <span class="fact__value">${h(household.type)}</span></div>
          ${household.partner_name ? `
            <div class="fact"><span class="fact__label">Partner</span>
              <span class="fact__value">${h(household.partner_name)}</span></div>` : ""}
          <div class="fact"><span class="fact__label">Children</span>
            <span class="fact__value">${household.children}</span></div>
          <div class="fact"><span class="fact__label">Housing</span>
            <span class="fact__value">${h(String(household.housing).replace(/_/g, " "))}</span></div>
        </div>
        <div class="row" style="margin-top:var(--space-3);gap:var(--space-2)">
          ${ProvenanceChip("declared")}
          <span class="kbc-meta">You gave us these, so we treat them as facts</span>
        </div>
        ${twin.goals.some((g) => g.id.includes("shared") || g.id.includes("family")) ? `
          <div class="kbc-banner kbc-banner--success" style="margin-top:var(--space-4)">
            <div class="t-small">Shared goals are counted once for the household,
            not twice for two people.</div>
          </div>` : ""}`,
    }) : ""}`;
}

function householdLabel(household) {
  const parts = [household.type.replace(/_/g, " ")];
  if (household.children) parts.push(`${household.children} child${household.children > 1 ? "ren" : ""}`);
  return parts.join(", ");
}

/* ==========================================================================
   Future Me
   ========================================================================== */
function renderFutureTab({ twin }) {
  const retirement = twin.derived_features.retirement || {};
  const changedYears = customerState.changed.includes("future_timeline")
    ? twin.future_timeline.map((m) => m.year) : [];
  return `
    ${KbcCard({
      label: "Future Me",
      title: "Where this is heading",
      body: `
        <p class="t-small t-muted" style="margin-bottom:var(--space-4)">
          Built from what we can see, what you have told us, and what we assume.
          Dashed markers are assumptions, not plans.
        </p>
        ${KbcTimeline(twin.future_timeline, { changedYears })}`,
    })}

    ${KbcCard({
      label: "Retirement projection",
      title: `Age ${retirement.target_retirement_age} in ${retirement.retirement_year}`,
      action: ProvenanceChip(retirement.retirement_age_source === "declared" ? "declared" : "derived"),
      body: `
        <div class="fact-list">
          ${fact("Income you would want", money(retirement.desired_monthly_income) + " / month")}
          ${fact("Estimated state pension", money(retirement.estimated_statutory_pension) + " / month")}
          ${fact("Monthly gap to close", money(retirement.monthly_income_gap) + " / month")}
          ${fact("Capital needed", money(retirement.capital_needed))}
          ${fact("Projected at your pace", money(retirement.projected_capital))}
          ${fact("Shortfall", money(retirement.projected_shortfall))}
        </div>
        <div style="margin-top:var(--space-4)">
          <div class="kbc-card__label">Readiness</div>
          ${KbcProgressBar({
            value: retirement.readiness,
            tone: retirement.readiness >= 0.9 ? "success" : retirement.readiness < 0.5 ? "warning" : "",
            large: true,
          })}
          <div class="kbc-meta" style="margin-top:var(--space-2)">${pct(retirement.readiness)} of what you would need</div>
        </div>
        ${retirement.retirement_age_source === "assumed" ? `
          <div class="kbc-banner kbc-banner--warning" style="margin-top:var(--space-4)">
            <div class="t-small">
              We assumed you retire at ${retirement.target_retirement_age}. That is
              our guess, and it changes everything above.
              <button class="kbc-btn kbc-btn--secondary kbc-btn--sm" data-open-sheet="twin"
                      style="margin-top:var(--space-2)">Set your own age</button>
            </div>
          </div>` : ""}
        <details style="margin-top:var(--space-4)">
          <summary class="t-small t-bold" style="cursor:pointer">What this projection assumes</summary>
          <ul class="evidence" style="margin-top:var(--space-2)">
            ${(retirement.assumptions || []).map((a) => `<li><span>${h(a)}</span></li>`).join("")}
          </ul>
        </details>`,
    })}`;
}

const fact = (label, value) =>
  `<div class="fact"><span class="fact__label">${h(label)}</span>
     <span class="fact__value">${h(value)}</span></div>`;

/* ==========================================================================
   My Twin - transparency + corrections
   ========================================================================== */
function renderTwinTab({ twin }) {
  return `
    ${KbcCard({
      label: "Your Twin",
      title: "Everything we think we know",
      action: KbcPrimaryButton({ label: "Edit my Twin", attrs: 'data-open-sheet="twin"', small: true }),
      body: `
        <div class="kbc-banner" style="margin-bottom:var(--space-4)">
          <div class="t-small">
            <strong>Your corrections override automated assumptions.</strong>
            Permanently, and across every KBC channel.
          </div>
        </div>
        <div class="grid grid--2" style="gap:var(--space-2)">
          ${["observed", "derived", "inferred", "declared"].map((p) => `
            <div class="row" style="gap:var(--space-2)">
              ${ProvenanceChip(p)}
            </div>`).join("")}
        </div>
        <div class="kbc-meta" style="margin-top:var(--space-3)">
          Nothing in this app is shown without one of these four labels.
        </div>`,
    })}

    ${twin.corrections.length ? KbcCard({
      label: "Your corrections",
      variant: "kbc-card--tinted",
      body: `
        <div class="stack stack--sm">
          ${twin.corrections.map((c) => `
            <div class="row row--between">
              <div>
                <div class="t-small t-bold">${h(c.field.replace(/_/g, " "))}</div>
                ${c.note ? `<div class="kbc-meta">&ldquo;${h(c.note)}&rdquo;</div>` : ""}
              </div>
              ${KbcStatusChip({ label: String(c.value), tone: "success" })}
            </div>`).join("")}
        </div>
        <div style="margin-top:var(--space-4)">
          ${KbcSecondaryButton({ label: "Undo all my corrections", attrs: 'data-clear-corrections="1"', small: true, block: true })}
        </div>`,
    }) : ""}

    ${KbcCard({
      label: "Signals we are tracking",
      body: `
        <div class="stack stack--sm">
          ${twin.signals.filter((s) => s.score > 0 || s.suppressed_by_customer).map((s) => `
            <div class="signal-row ${s.suppressed_by_customer ? "signal-row--suppressed" : ""}">
              <span class="signal-row__name">${h(s.label)}</span>
              <span class="signal-bar">${KbcProgressBar({
                value: s.score,
                tone: s.triggered ? "" : "warning",
              })}</span>
              <span class="t-micro t-num" style="flex:0 0 34px;text-align:right">${pct(s.score)}</span>
            </div>`).join("")}
        </div>
        <div class="kbc-meta" style="margin-top:var(--space-3)">
          A signal only acts on your plan once it passes its threshold. Below
          that we keep watching and do nothing.
        </div>`,
    })}

    ${KbcCard({
      label: "Why we think each thing",
      body: twin.explanations.map((e) => `
        <details style="padding:var(--space-2) 0;border-bottom:1px solid var(--kbc-divider)">
          <summary class="t-small t-bold" style="cursor:pointer">
            ${h(e.headline)} ${ProvenanceChip(e.provenance, { short: true })}
          </summary>
          <ul class="evidence" style="margin-top:var(--space-2)">
            ${e.reasons.map((r) => `<li><span>${h(r)}</span></li>`).join("")}
          </ul>
        </details>`).join(""),
    })}`;
}

/* ==========================================================================
   Edit my Twin - bottom sheet
   ========================================================================== */
function renderEditSheet({ twin, meta }) {
  const retirement = twin.derived_features.retirement || {};
  const phases = meta?.life_phases || {};
  const houseGoal = twin.goals.find((g) => g.id === "house_deposit");
  const bufferGoal = twin.goals.find((g) => g.id !== "house_deposit");
  const plansHouse = findCorrection(twin, "plans_to_buy_house");
  const family = findCorrection(twin, "family_expansion");

  return `
  <div class="sheet-backdrop" data-close-sheet="1">
    <div class="sheet" role="dialog" aria-label="Edit my Twin" data-stop="1">
      <div class="sheet__grip"></div>
      <div class="t-h2">Edit my Twin</div>
      <p class="t-small t-muted" style="margin:var(--space-2) 0 var(--space-5)">
        Your corrections override automated assumptions, everywhere, until you
        change them back.
      </p>

      <div class="stack stack--lg">
        ${KbcFormField({
          label: "My life phase",
          help: `We currently think: ${h(twin.life_phase.label)} (${pct(twin.life_phase.confidence)})`,
          control: `<select data-field="life_phase">
            ${Object.entries(phases).map(([value, label]) => `
              <option value="${h(value)}" ${value === twin.life_phase.value ? "selected" : ""}>${h(label)}</option>`).join("")}
          </select>`,
        })}

        ${KbcFormField({
          label: "I am planning to buy a home",
          help: plansHouse === false
            ? "You told us no. We have stopped suggesting it."
            : "We infer this from your saving pattern.",
          control: KbcSegmented({
            name: "plans_to_buy_house",
            value: plansHouse === undefined ? "" : String(plansHouse),
            options: [{ label: "Yes", value: "true" }, { label: "No", value: "false" }],
          }),
        })}

        ${KbcFormField({
          label: "My family is growing",
          help: family === false
            ? "You told us no. The assumption is switched off."
            : "We may infer this from spending. You decide.",
          control: KbcSegmented({
            name: "family_expansion",
            value: family === undefined ? "" : String(family),
            options: [{ label: "Yes", value: "true" }, { label: "No", value: "false" }],
          }),
        })}

        ${KbcFormField({
          label: "I want to retire at",
          help: retirement.retirement_age_source === "declared"
            ? "Your own target, not our assumption."
            : `We assumed ${retirement.target_retirement_age}.`,
          control: `<div class="row">
            <input type="number" min="55" max="72" step="1"
                   value="${retirement.target_retirement_age}" data-field="target_retirement_age">
            ${KbcPrimaryButton({ label: "Save", attrs: 'data-save-field="target_retirement_age"', small: true })}
          </div>`,
        })}

        ${bufferGoal ? KbcFormField({
          label: `Target for "${h(bufferGoal.title)}"`,
          help: `We calculated ${money(bufferGoal.target_amount)} from your own spending.`,
          control: `<div class="row">
            <input type="number" min="500" step="100" value="${Math.round(bufferGoal.target_amount)}"
                   data-field="goal_target:${h(bufferGoal.id)}">
            ${KbcPrimaryButton({ label: "Save", attrs: `data-save-field="goal_target:${h(bufferGoal.id)}"`, small: true })}
          </div>`,
        }) : ""}

        ${houseGoal ? KbcFormField({
          label: `Target for "${h(houseGoal.title)}"`,
          help: `Currently ${money(houseGoal.target_amount)}.`,
          control: `<div class="row">
            <input type="number" min="1000" step="1000" value="${Math.round(houseGoal.target_amount)}"
                   data-field="goal_target:${h(houseGoal.id)}">
            ${KbcPrimaryButton({ label: "Save", attrs: `data-save-field="goal_target:${h(houseGoal.id)}"`, small: true })}
          </div>`,
        }) : ""}
      </div>

      <div style="margin-top:var(--space-6)">
        ${KbcSecondaryButton({ label: "Close", attrs: 'data-close-sheet="1"', block: true })}
      </div>
    </div>
  </div>`;
}

function findCorrection(twin, field) {
  const found = twin.corrections.find((c) => c.field === field);
  return found ? found.value : undefined;
}

/* ==========================================================================
   Sidebar: persona picker, demo controls, pipeline
   ========================================================================== */
function renderPersonaPicker(personas, activeId) {
  return KbcCard({
    label: "Hero personas",
    title: "Pick a customer",
    body: `
      <div class="persona-list">
        ${(personas || []).map((p) => `
          <button class="persona" data-persona="${h(p.customer_id)}"
                  aria-selected="${p.customer_id === activeId}">
            <span class="persona__avatar">${h(p.hero_key)}</span>
            <span style="min-width:0;flex:1">
              <span class="persona__name">${h(p.first_name)} ${h(p.last_name)}, ${p.age}</span>
              <span class="persona__meta">${h(p.hero_label)} &middot; ${h(p.story?.setup || "")}</span>
            </span>
          </button>`).join("")}
      </div>
      <div style="margin-top:var(--space-4)">
        ${KbcSecondaryButton({ label: "Reset the demo", attrs: 'data-reset="1"', block: true, small: true })}
      </div>`,
  });
}

function renderDemoControls(meta, twin) {
  const actions = meta?.demo_actions || [];
  const story = twin ? null : null;
  return KbcCard({
    label: "Live demo",
    title: "Inject an event",
    body: `
      <p class="t-small t-muted" style="margin-bottom:var(--space-4)">
        Each button publishes one transaction onto the event queue. The API
        returns immediately &mdash; the Twin updates asynchronously, and you
        watch it happen below.
      </p>
      <div class="demo-btns">
        ${actions.map((a) => `
          <button class="demo-btn" data-inject="${h(a.key)}" ${customerState.busy ? "disabled" : ""}>
            <span class="demo-btn__icon" style="width:32px;height:32px">
              <span style="width:18px;height:18px;display:inline-flex">${DEMO_ICONS[a.key] || Icon.euro}</span>
            </span>
            <span style="min-width:0;flex:1">
              <span class="demo-btn__label">${h(a.label)}</span>
              <span class="demo-btn__hint">${h(a.hint)}</span>
            </span>
          </button>`).join("")}
      </div>`,
  });
}

function renderPipelineCard() {
  const p = customerState.pipeline;
  return KbcCard({
    id: "pipeline-card",
    label: "Event pipeline",
    title: p ? p.label : "Idle",
    body: `
      ${PipelineStages(p?.stages, {
        activeIndex: p?.activeIndex ?? -1,
        complete: p?.complete ?? false,
      })}
      ${p?.complete ? `
        <div class="kbc-banner kbc-banner--success" style="margin-top:var(--space-4)">
          <div class="t-small">
            <strong>Twin v${p.version}</strong> in ${p.totalMs?.toFixed(1)} ms.
            ${p.summary ? h(p.summary) : ""}
          </div>
        </div>` : ""}
      ${!p ? `<div class="kbc-meta" style="margin-top:var(--space-3)">
        Click a demo button to send an event through Tier 1 and Tier 2.
      </div>` : ""}`,
  });
}

function renderTierNote(meta, twin) {
  const tier3 = meta?.tier3;
  if (!tier3) return "";
  return KbcCard({
    variant: "kbc-card--flat",
    label: "Tier 3",
    title: tier3.generator === "claude" ? "Claude is writing the wording" : "Templates are writing the wording",
    body: `
      <p class="t-small t-muted">${h(tier3.note)}</p>
      <div class="fact-list" style="margin-top:var(--space-3)">
        ${fact("Called when", (tier3.called_when || []).join(", "))}
        ${fact("Never called for", (tier3.never_called_for || []).join(", "))}
      </div>`,
  });
}

/* ==========================================================================
   Behaviour
   ========================================================================== */
export function bindCustomer(root, ctx, refresh) {
  const on = (selector, event, handler) =>
    root.querySelectorAll(selector).forEach((el) => el.addEventListener(event, handler));

  on("[data-tab]", "click", (e) => {
    customerState.tab = e.currentTarget.dataset.tab;
    refresh({ keepScroll: false });
  });

  on("[data-toggle='why']", "click", () => {
    customerState.whyOpen = !customerState.whyOpen;
    refresh();
  });

  on("[data-persona]", "click", async (e) => {
    customerState.customerId = e.currentTarget.dataset.persona;
    customerState.pipeline = null;
    customerState.changed = [];
    customerState.tab = "home";
    await refresh({ reload: true });
  });

  on("[data-open-sheet]", "click", () => { customerState.sheet = "twin"; refresh(); });
  on("[data-close-sheet]", "click", (e) => {
    if (e.target.closest("[data-stop]") && !e.target.matches("[data-close-sheet]")) return;
    customerState.sheet = null; refresh();
  });

  on("[data-inject]", "click", async (e) => {
    await runInjection(e.currentTarget.dataset.inject, ctx, refresh);
  });

  on("[data-reset]", "click", async () => {
    customerState.busy = true; refresh();
    await api.reset();
    customerState.pipeline = null;
    customerState.changed = [];
    customerState.busy = false;
    toast("Demo reset to the seeded world.");
    await refresh({ reload: true });
  });

  /* --- corrections --------------------------------------------------- */
  on("[data-correct]", "click", async (e) => {
    const field = e.currentTarget.dataset.correct;
    const raw = e.currentTarget.dataset.value;
    await saveCorrection(field, raw === "true", "Corrected from the app", ctx, refresh);
  });

  on("select[data-field='life_phase']", "change", async (e) => {
    await saveCorrection("life_phase", e.target.value, "Set by me", ctx, refresh);
  });

  on("[data-segmented] button", "click", async (e) => {
    const group = e.currentTarget.closest("[data-segmented]").dataset.segmented;
    const value = e.currentTarget.dataset.value === "true";
    await saveCorrection(group, value, "Set by me", ctx, refresh);
  });

  on("[data-save-field]", "click", async (e) => {
    const field = e.currentTarget.dataset.saveField;
    const input = root.querySelector(`[data-field="${CSS.escape(field)}"]`);
    if (!input) return;
    await saveCorrection(field, Number(input.value), "Set by me", ctx, refresh);
  });

  on("[data-clear-corrections]", "click", async () => {
    await api.clearCorrections(customerState.customerId);
    toast("All your corrections were undone.");
    await refresh({ reload: true });
  });
}

async function saveCorrection(field, value, note, ctx, refresh) {
  try {
    const result = await api.correct(customerState.customerId, field, value, note);
    customerState.changed = result.twin.changed_fields || [];
    toast(`Saved. ${result.notice}`);
    await refresh({ reload: true });
  } catch (error) {
    toast(`Could not save: ${error.message}`);
  }
}

/** The demo money-shot: publish, then walk the stages as the worker reports
 *  them, then re-render the Twin with the changed values highlighted. */
async function runInjection(actionKey, ctx, refresh) {
  customerState.busy = true;
  customerState.changed = [];
  const label = (ctx.meta?.demo_actions || []).find((a) => a.key === actionKey)?.label || "Event";
  customerState.pipeline = { label, stages: null, activeIndex: 0, complete: false };
  await refresh();

  try {
    const accepted = await api.inject(customerState.customerId, actionKey);

    // Animate through the stages while the worker is actually working.
    const ticker = setInterval(async () => {
      if (!customerState.pipeline || customerState.pipeline.complete) return;
      customerState.pipeline.activeIndex =
        Math.min(5, customerState.pipeline.activeIndex + 1);
      await refresh({ pipelineOnly: true });
    }, 170);

    const trace = await waitForEvent(accepted.event_id);
    clearInterval(ticker);

    customerState.pipeline = {
      label,
      stages: trace.stages,
      activeIndex: trace.stages.length,
      complete: true,
      version: trace.twin_version,
      totalMs: trace.total_ms,
      summary: "",
    };
    customerState.changed = trace.changed || [];
    customerState.busy = false;
    await refresh({ reload: true });

    const twin = ctx.twin;
    if (twin?.change_summary) {
      customerState.pipeline.summary = twin.change_summary;
      toast(twin.change_summary.split(";")[0]);
      await refresh({ pipelineOnly: true });
    }
  } catch (error) {
    customerState.busy = false;
    customerState.pipeline = null;
    toast(`Event failed: ${error.message}`);
    await refresh();
  }
}
