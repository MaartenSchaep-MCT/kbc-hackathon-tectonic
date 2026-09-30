/* ==========================================================================
   The KBC component system.

   Every screen is assembled from these. They return HTML strings, which keeps
   the prototype dependency-free (no build step, no npm) while still giving one
   coherent design system rather than per-screen styling.

   Components: KbcHeader, KbcBottomNavigation, KbcCard, KbcPrimaryButton,
   KbcSecondaryButton, KbcProgressBar, KbcStatusChip, KbcInfoBanner,
   KbcFormField, KbcTimeline, KbcGoalCard, KbcTwinInsight, KbcAdvisorPanel,
   plus the provenance chip and confidence meter that carry the
   explainability story.
   ========================================================================== */

import { escapeHtml, money, pct } from "./format.js";

const h = escapeHtml;

/* --- icons: neutral, inline, currentColor. No proprietary KBC iconography. */
export const Icon = {
  home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>`,
  target: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/></svg>`,
  route: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="6" r="2.5"/><path d="M8.5 18h5a4 4 0 0 0 4-4V8.5"/></svg>`,
  sliders: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 7h16M4 12h16M4 17h16"/><circle cx="9" cy="7" r="2" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="2" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="2" fill="currentColor" stroke="none"/></svg>`,
  euro: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M16.5 6.5A6 6 0 1 0 16.5 17.5"/><path d="M4.5 10.5h8M4.5 13.5h8"/></svg>`,
  crib: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 9v10M21 9v10M3 13h18M3 19h18"/><path d="M7 9v4M11 9v4M15 9v4M19 9v4"/><path d="M3 9h18"/></svg>`,
  receipt: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/></svg>`,
  piggy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 13a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><path d="M7 18v2M17 18v2M9 7V5"/><circle cx="16" cy="12" r="1" fill="currentColor" stroke="none"/></svg>`,
  info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><circle cx="12" cy="8" r="1" fill="currentColor" stroke="none"/></svg>`,
  chevron: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m9 6 6 6-6 6"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 13 4 4L19 7"/></svg>`,
  edit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L20 8l-4-4L4 16z"/></svg>`,
};

/* ==========================================================================
   KbcHeader
   ========================================================================== */
export function KbcHeader({ tabs, active, status }) {
  return `
    <header class="kbc-appbar">
      <span class="kbc-wordmark">
        <span class="kbc-wordmark__mark">KBC</span>
        Financial Twin
        <span class="kbc-wordmark__sub">prototype</span>
      </span>
      <nav class="kbc-tabs" role="tablist" aria-label="Channel">
        ${tabs.map((t) => `
          <button class="kbc-tab" role="tab" data-route="${h(t.id)}"
                  aria-selected="${t.id === active}">
            <span class="kbc-tab__long">${h(t.label)}</span>
            <span class="kbc-tab__short">${h(t.short || t.label)}</span>
          </button>`).join("")}
      </nav>
      <div class="kbc-appbar__status">${status || ""}</div>
    </header>`;
}

/* ==========================================================================
   KbcBottomNavigation
   ========================================================================== */
export function KbcBottomNavigation({ items, active }) {
  return `
    <nav class="phone__nav" role="tablist" aria-label="App sections">
      ${items.map((item) => `
        <button role="tab" data-tab="${h(item.id)}"
                aria-selected="${item.id === active}">
          ${Icon[item.icon] || ""}
          <span>${h(item.label)}</span>
        </button>`).join("")}
    </nav>`;
}

/* ==========================================================================
   KbcCard
   ========================================================================== */
export function KbcCard({ title, label, action = "", body, variant = "", className = "", id = "" }) {
  const head = (title || label || action)
    ? `<div class="kbc-card__header">
         <div>
           ${label ? `<div class="kbc-card__label">${h(label)}</div>` : ""}
           ${title ? `<div class="kbc-card__title">${h(title)}</div>` : ""}
         </div>
         ${action}
       </div>`
    : "";
  return `<section class="kbc-card ${variant} ${className}" ${id ? `id="${h(id)}"` : ""}>
            ${head}${body}
          </section>`;
}

/* ==========================================================================
   Buttons
   ========================================================================== */
export const KbcPrimaryButton = ({ label, attrs = "", block = false, small = false }) =>
  `<button class="kbc-btn kbc-btn--primary${block ? " kbc-btn--block" : ""}${small ? " kbc-btn--sm" : ""}" ${attrs}>${h(label)}</button>`;

export const KbcSecondaryButton = ({ label, attrs = "", block = false, small = false }) =>
  `<button class="kbc-btn kbc-btn--secondary${block ? " kbc-btn--block" : ""}${small ? " kbc-btn--sm" : ""}" ${attrs}>${h(label)}</button>`;

export const KbcGhostButton = ({ label, attrs = "" }) =>
  `<button class="kbc-btn kbc-btn--ghost kbc-btn--sm" ${attrs}>${h(label)}</button>`;

/* ==========================================================================
   KbcStatusChip + provenance
   ========================================================================== */
export const KbcStatusChip = ({ label, tone = "", icon = "" }) =>
  `<span class="kbc-chip ${tone ? `kbc-chip--${tone}` : ""}">${icon}${h(label)}</span>`;

const PROVENANCE = {
  observed: { label: "Observed fact",  short: "Observed",   tone: "observed" },
  derived:  { label: "Calculated from your data", short: "Calculated", tone: "derived" },
  inferred: { label: "Our assumption", short: "Assumption", tone: "inferred" },
  declared: { label: "You told us",    short: "You told us", tone: "declared" },
};

/** The single most important component in the prototype: it makes the
 *  difference between a fact and a guess visible everywhere, in one glance. */
export function ProvenanceChip(provenance, { short = false } = {}) {
  const meta = PROVENANCE[provenance] || PROVENANCE.derived;
  const label = short ? meta.short : meta.label;
  return `<span class="kbc-chip kbc-prov kbc-prov--${meta.tone}" title="${h(meta.label)}">${h(label)}</span>`;
}

/* ==========================================================================
   KbcProgressBar + confidence meter
   ========================================================================== */
export function KbcProgressBar({ value, tone = "", large = false }) {
  const width = Math.max(0, Math.min(1, value || 0)) * 100;
  return `<div class="kbc-progress${large ? " kbc-progress--lg" : ""}"
               role="progressbar" aria-valuenow="${Math.round(width)}" aria-valuemin="0" aria-valuemax="100">
            <div class="kbc-progress__fill${tone ? ` kbc-progress__fill--${tone}` : ""}" style="width:${width}%"></div>
          </div>`;
}

/** Segmented, deliberately. A continuous bar reads as a quantity; confidence
 *  is not a quantity of anything, so it gets its own visual language. */
export function ConfidenceMeter(confidence, { segments = 5, warn = false } = {}) {
  const filled = Math.round((confidence || 0) * segments);
  return `<span class="kbc-confidence" aria-label="Confidence ${pct(confidence)}">
    ${Array.from({ length: segments }, (_, i) =>
      `<span class="kbc-confidence__seg${i < filled ? (warn ? " kbc-confidence__seg--warn" : " kbc-confidence__seg--on") : ""}"></span>`
    ).join("")}
  </span>`;
}

/* ==========================================================================
   KbcInfoBanner
   ========================================================================== */
export const KbcInfoBanner = ({ text, tone = "", icon = Icon.info, html = "" }) =>
  `<div class="kbc-banner ${tone ? `kbc-banner--${tone}` : ""}">
     <span class="kbc-banner__icon" style="width:20px;height:20px">${icon}</span>
     <div>${html || h(text)}</div>
   </div>`;

/* ==========================================================================
   KbcFormField
   ========================================================================== */
export function KbcFormField({ label, help = "", control }) {
  return `<div class="field">
            <label class="field__label">${h(label)}</label>
            ${control}
            ${help ? `<div class="field__help">${h(help)}</div>` : ""}
          </div>`;
}

export const KbcSegmented = ({ name, options, value }) =>
  `<div class="segmented" role="group" data-segmented="${h(name)}">
     ${options.map((o) => `
       <button type="button" data-value="${h(String(o.value))}"
               aria-pressed="${String(o.value) === String(value)}">${h(o.label)}</button>`).join("")}
   </div>`;

/* ==========================================================================
   Progress ring (headline metric)
   ========================================================================== */
export function ProgressRing(value, { size = 74, stroke = 7 } = {}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.max(0, Math.min(1, value || 0)));
  return `<div class="ring" style="width:${size}px;height:${size}px">
    <svg width="${size}" height="${size}">
      <circle class="ring__track" cx="${size / 2}" cy="${size / 2}" r="${r}"
              fill="none" stroke-width="${stroke}"/>
      <circle class="ring__fill" cx="${size / 2}" cy="${size / 2}" r="${r}"
              fill="none" stroke-width="${stroke}" stroke-linecap="round"
              stroke-dasharray="${c}" stroke-dashoffset="${offset}"/>
    </svg>
    <span class="ring__value">${pct(value)}</span>
  </div>`;
}

/* ==========================================================================
   KbcTwinInsight - the hero card. Life phase + confidence + "why we think this"
   ========================================================================== */
export function KbcTwinInsight(twin, { expanded = false } = {}) {
  const phase = twin.life_phase;
  const isAssumption = phase.provenance === "inferred";
  const explanation = (twin.explanations || []).find((e) => e.field === "life_phase");
  return `
    <section class="twin-hero" id="twin-hero">
      <div class="row row--between" style="align-items:flex-start">
        <div style="min-width:0">
          <div class="twin-hero__eyebrow">Your Financial Twin &middot; v${twin.version}</div>
          <div class="twin-hero__phase" id="phase-value">${h(phase.label || phase.value)}</div>
          <div class="twin-hero__conf">
            ${ConfidenceMeter(phase.confidence, { warn: isAssumption })}
            <span class="t-small t-bold">${pct(phase.confidence)}</span>
            ${ProvenanceChip(phase.provenance, { short: true })}
          </div>
        </div>
        ${ProgressRing(twin.progress_score)}
      </div>
      <div class="kbc-meta" style="color:var(--kbc-primary-150);margin-top:var(--space-2)">
        Progress towards your own goals
      </div>
      <button class="twin-hero__why" data-toggle="why" aria-expanded="${expanded}">
        ${expanded ? "Hide the reasoning" : "Why we think this"}
        <span style="width:16px;height:16px;display:inline-flex;transform:rotate(${expanded ? 90 : 0}deg);transition:transform var(--duration)">${Icon.chevron}</span>
      </button>
      ${expanded && explanation ? `
        <ul class="twin-hero__reasons">
          ${explanation.reasons.map((r) => `<li><span>${h(r)}</span></li>`).join("")}
        </ul>
        <div class="kbc-meta" style="color:var(--kbc-primary-150);margin-top:var(--space-3)">
          ${isAssumption
            ? "This is our reading of your transactions, not something you told us. You can change it."
            : "You told us this, so it overrides anything we would have inferred."}
        </div>` : ""}
    </section>`;
}

/* ==========================================================================
   KbcGoalCard
   ========================================================================== */
export function KbcGoalCard(goal) {
  const progress = goal.target_amount > 0
    ? Math.min(1, goal.current_amount / goal.target_amount) : 0;
  const done = goal.projected_completion === "reached";
  const tone = done ? "success" : goal.on_track ? "" : "warning";
  return `
    <div class="goal" data-goal="${h(goal.id)}">
      <div class="goal__top">
        <span class="t-body t-bold">${h(goal.title)}</span>
        ${done
          ? KbcStatusChip({ label: "Reached", tone: "success" })
          : `<span class="kbc-meta">${h(goal.projected_completion || "no date yet")}</span>`}
      </div>
      <div class="goal__amounts t-num">
        ${money(goal.current_amount)}
        <span class="goal__target"> / ${money(goal.target_amount)}</span>
      </div>
      ${KbcProgressBar({ value: progress, tone })}
      <div class="goal__foot">
        <span class="kbc-meta">
          ${goal.monthly_contribution > 0
            ? `${money(goal.monthly_contribution)} per month`
            : done ? "Fully funded" : "Nothing allocated yet"}
        </span>
        <span class="kbc-meta">${pct(progress)}</span>
      </div>
      ${goal.explanation ? `<div class="kbc-meta">${h(goal.explanation)}</div>` : ""}
      <div class="row" style="gap:var(--space-2)">
        ${ProvenanceChip(goal.provenance, { short: true })}
        ${goal.origin ? `<span class="kbc-meta">from &ldquo;${h(goal.origin)}&rdquo;</span>` : ""}
      </div>
    </div>`;
}

/* ==========================================================================
   KbcTimeline - Future Me
   ========================================================================== */
export function KbcTimeline(milestones, { changedYears = [] } = {}) {
  if (!milestones.length) {
    return `<div class="kbc-meta">No milestones yet.</div>`;
  }
  return `<ol class="timeline">
    ${milestones.map((m) => `
      <li class="tl-item tl-item--${h(m.kind)} ${changedYears.includes(m.year) ? "just-changed" : ""}">
        <span class="tl-item__dot"></span>
        <div class="tl-item__year">${h(m.date_label || m.year)}</div>
        <div class="tl-item__title">${h(m.title)}</div>
        ${m.detail ? `<div class="tl-item__detail">${h(m.detail)}</div>` : ""}
        <div class="row" style="gap:var(--space-2);margin-top:var(--space-2)">
          ${ProvenanceChip(m.provenance, { short: true })}
          ${m.kind === "life_event" || m.confidence < 0.95
            ? `<span class="kbc-meta">${pct(m.confidence)} confidence</span>` : ""}
        </div>
      </li>`).join("")}
  </ol>`;
}

/* ==========================================================================
   Pipeline visualiser
   ========================================================================== */
export function PipelineStages(stages, { activeIndex = -1, complete = false } = {}) {
  const planned = [
    { name: "Event ingestion", detail: "Accepted onto the queue" },
    { name: "Transaction stored", detail: "Observed fact recorded" },
    { name: "Tier 1 - feature update", detail: "Streaming features recomputed" },
    { name: "Tier 2 - life-event scoring", detail: "Interpretable models scored" },
    { name: "Financial Twin updated", detail: "New version written" },
    { name: "Shared Twin API", detail: "Every channel sees it" },
  ];
  const list = stages && stages.length ? stages : planned;
  return `<div class="pipe">
    ${list.map((stage, i) => {
      const state = complete || (activeIndex > i) ? "done"
                  : activeIndex === i ? "active" : "";
      return `<div class="pipe__stage ${state ? `pipe__stage--${state}` : ""}">
        <span class="pipe__num">${state === "done" ? `<span style="width:13px;height:13px;display:inline-flex">${Icon.check}</span>` : i + 1}</span>
        <div class="pipe__body">
          <div class="pipe__name">${h(stage.name)}</div>
          <div class="pipe__detail">${h(stage.detail || "")}</div>
        </div>
        ${stage.ms !== undefined && (complete || activeIndex > i)
          ? `<span class="pipe__ms">${stage.ms.toFixed(1)} ms</span>` : ""}
      </div>`;
    }).join("")}
  </div>`;
}

/* ==========================================================================
   KbcAdvisorPanel - facts grouped by provenance
   ========================================================================== */
export function KbcAdvisorPanel({ title, label, items, provenance, note = "" }) {
  return KbcCard({
    label,
    title,
    action: ProvenanceChip(provenance),
    body: `
      ${note ? `<div class="kbc-meta" style="margin-bottom:var(--space-3)">${h(note)}</div>` : ""}
      <div class="fact-list">
        ${items.map((item) => `
          <div class="fact">
            <span class="fact__label">${h(item.label)}${item.is_correction ? " &middot; correction" : ""}</span>
            <span class="fact__value">${h(formatFactValue(item.value))}</span>
          </div>`).join("")}
      </div>`,
  });
}

function formatFactValue(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  if (value === null || value === undefined) return "-";
  return value;
}

export function EvidenceList(evidence) {
  if (!evidence || !evidence.length) return "";
  return `<ul class="evidence">
    ${evidence.map((e) => `
      <li><span>${h(e.text || e)}</span>
        ${e.weight ? `<span class="evidence__weight">+${e.weight.toFixed(2)}</span>` : ""}
      </li>`).join("")}
  </ul>`;
}

/* ==========================================================================
   Misc
   ========================================================================== */
export function MetricTile({ value, label, accent = false, sub = "" }) {
  return `<div class="metric ${accent ? "metric--accent" : ""}">
            <div class="metric__value">${h(value)}</div>
            <div class="metric__label">${h(label)}</div>
            ${sub ? `<div class="kbc-meta" style="margin-top:var(--space-2)">${h(sub)}</div>` : ""}
          </div>`;
}

export function toast(message) {
  document.querySelectorAll(".toast").forEach((t) => t.remove());
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}
