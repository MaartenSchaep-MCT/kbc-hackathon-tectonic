/* ==========================================================================
   The KBC component system.

   Every screen is assembled from these. They return HTML strings, which keeps
   the prototype dependency-free (no build step, no npm) while still giving one
   coherent design system rather than per-screen styling.

   Components: KbcHeader, KbcCard, KbcPrimaryButton, KbcSecondaryButton,
   KbcProgressBar, KbcStatusChip, KbcInfoBanner, KbcTimeline, KbcAdvisorPanel,
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
  wallet: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3"/><rect x="4" y="8" width="16" height="11" rx="2.5"/><path d="M16 13.5h1.5"/></svg>`,
  user: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="8.5" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/></svg>`,
  kate: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 8h7M5 12h14M10 16h7"/></svg>`,
  bell: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5h4"/></svg>`,
  sun: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4"/></svg>`,
  house: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 11 12 4l8.5 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/></svg>`,
  shield: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5 5 6v5.5c0 4.2 3 7.6 7 9 4-1.4 7-4.8 7-9V6z"/><path d="m9 12 2 2 4-4"/></svg>`,
  plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 6v12M6 12h12"/></svg>`,
  minus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 12h12"/></svg>`,
  close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M7 7l10 10M17 7 7 17"/></svg>`,
  car: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 16v-4l2-5h12l2 5v4z"/><path d="M4 12h16"/><circle cx="7.5" cy="16.5" r="1.5"/><circle cx="16.5" cy="16.5" r="1.5"/></svg>`,
  globe: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.4 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.4-3.5-8.5s1-5.9 3.5-8.5z"/></svg>`,
  heart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M12 19.5s-7.5-4.4-7.5-9.7A4.1 4.1 0 0 1 12 7.6a4.1 4.1 0 0 1 7.5 2.2c0 5.3-7.5 9.7-7.5 9.7z"/></svg>`,
};

/* ==========================================================================
   KbcHeader
   ========================================================================== */
export function KbcHeader({ tabs, active, personas = [], customerId }) {
  return `
    <header class="kbc-appbar">
      <span class="kbc-wordmark">
        <span class="kbc-wordmark__mark">KBC</span>
        Future Me
      </span>
      <nav class="kbc-tabs" role="tablist" aria-label="View">
        ${tabs.map((t) => `
          <button class="kbc-tab" role="tab" data-route="${h(t.id)}"
                  aria-selected="${t.id === active}">
            <span class="kbc-tab__long">${h(t.label)}</span>
            <span class="kbc-tab__short">${h(t.short || t.label)}</span>
          </button>`).join("")}
      </nav>
    </header>
    ${personas.length ? `
      <div class="persona-bar" role="group" aria-label="Customer">
        ${personas.map((p) => `
          <button class="persona-pill" data-persona="${h(p.customer_id)}"
                  aria-pressed="${p.customer_id === customerId}">
            <b>${h(p.first_name)}, ${p.age}</b> <span>${h(p.hero_label)}</span>
          </button>`).join("")}
      </div>` : ""}`;
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
    { name: "Future updated", detail: "New version written" },
    { name: "Shared API", detail: "App and advisor see it" },
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
