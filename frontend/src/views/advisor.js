/* ==========================================================================
   ADVISOR VIEW - the SAME Twin, reprojected for a professional.

   Denser than the customer app and desktop-first, but built from the identical
   component system. The thing to notice: there is no advisor-specific
   personalisation anywhere. The version number in the header is the same
   number the customer app shows.

   The layout is organised by PROVENANCE, because that is the distinction an
   advisor has to get right before opening their mouth: what the customer
   actually said, versus what a model guessed.
   ========================================================================== */

import { api } from "../api.js";
import {
  ConfidenceMeter, EvidenceList, KbcAdvisorPanel, KbcCard, KbcInfoBanner,
  KbcProgressBar, KbcStatusChip, KbcTimeline, ProgressRing, ProvenanceChip,
} from "../components.js";
import { escapeHtml as h, money, pct } from "../format.js";

export const advisorState = { customerId: null };

export function renderAdvisor(ctx) {
  const { advisor, customerTwinVersion } = ctx;
  if (!advisor) return `<div class="page"><div class="skeleton" style="height:300px"></div></div>`;

  const s = advisor.summary;
  const twin = advisor.twin;

  return `
  <div class="page">
    <div class="page__inner stack stack--lg">

      ${renderConsistencyBanner(advisor.twin_version, customerTwinVersion)}

      <div class="kbc-card" style="padding:var(--space-5)">
        <div class="row row--between row--wrap" style="gap:var(--space-5)">
          <div class="row" style="gap:var(--space-4)">
            <span class="persona__avatar" style="width:52px;height:52px;font-size:var(--text-h3)">
              ${h(initialsOf(s.name))}
            </span>
            <div>
              <div class="t-h1">${h(s.name)}</div>
              <div class="kbc-meta">
                ${s.age} &middot; ${h(s.city)} &middot; ${h(advisor.customer.household_type)}
                &middot; ${h(advisor.customer_id)}
              </div>
              <div class="row" style="gap:var(--space-2);margin-top:var(--space-2)">
                ${KbcStatusChip({ label: h(s.life_phase.label), tone: "accent" })}
                ${ConfidenceMeter(s.life_phase.confidence, { warn: s.life_phase.provenance === "inferred" })}
                <span class="t-small t-bold">${pct(s.life_phase.confidence)}</span>
                ${ProvenanceChip(s.life_phase.provenance)}
              </div>
            </div>
          </div>
          <div class="row" style="gap:var(--space-5)">
            <div style="text-align:center">
              ${ProgressRing(s.progress_score, { size: 84, stroke: 8 })}
              <div class="kbc-meta" style="margin-top:var(--space-2)">Customer progress</div>
            </div>
            <div>
              <div class="kbc-card__label">Twin version</div>
              <div class="t-display t-num">${advisor.twin_version}</div>
              <div class="kbc-meta">same document as the app</div>
            </div>
          </div>
        </div>
      </div>

      ${KbcInfoBanner({
        tone: "neutral",
        html: `<div class="t-small"><strong>What this view is for.</strong> ${h(advisor.guardrail)}</div>`,
      })}

      <div class="advisor-grid">
        <!-- LEFT: what is true, grouped by how we know it -->
        <div class="stack">
          ${KbcAdvisorPanel({
            label: "Provenance: observed",
            title: "Observed facts",
            provenance: "observed",
            note: "Straight from transactions. Verifiable.",
            items: advisor.observed_facts,
          })}
          ${KbcAdvisorPanel({
            label: "Provenance: declared",
            title: "What the customer told us",
            provenance: "declared",
            note: "Outranks every model output below. Do not argue with it.",
            items: advisor.customer_declared,
          })}
          ${advisor.corrections.length ? KbcCard({
            variant: "kbc-card--tinted",
            label: "Active corrections",
            title: `${advisor.corrections.length} assumption${advisor.corrections.length > 1 ? "s" : ""} overridden`,
            body: `
              <div class="stack stack--sm">
                ${advisor.corrections.map((c) => `
                  <div>
                    <div class="row row--between">
                      <span class="t-small t-bold">${h(c.field.replace(/_/g, " "))}</span>
                      ${KbcStatusChip({ label: String(c.value), tone: "success" })}
                    </div>
                    ${c.note ? `<div class="kbc-meta">&ldquo;${h(c.note)}&rdquo;</div>` : ""}
                  </div>`).join("")}
              </div>
              <div class="kbc-meta" style="margin-top:var(--space-3)">
                The customer set these. Anything they switched off has already
                been removed from the goals and the timeline.
              </div>`,
          }) : ""}
        </div>

        <!-- MIDDLE: inference, goals, timeline -->
        <div class="stack">
          ${KbcCard({
            label: "Provenance: inferred",
            title: "Signals and confidence",
            action: ProvenanceChip("inferred"),
            body: `
              <div class="kbc-meta" style="margin-bottom:var(--space-3)">
                Model output. Every one of these can be wrong, and the customer
                can switch it off.
              </div>
              ${advisor.inferred_signals.map((sig) => `
                <div class="signal-row ${sig.suppressed ? "signal-row--suppressed" : ""}">
                  <span class="signal-row__name">
                    ${h(sig.label)}
                    ${sig.suppressed ? KbcStatusChip({ label: "customer says no", tone: "success" }) : ""}
                    ${sig.triggered && !sig.suppressed ? KbcStatusChip({ label: "active", tone: "accent" }) : ""}
                  </span>
                  <span class="signal-bar">${KbcProgressBar({ value: sig.confidence, tone: sig.triggered ? "" : "warning" })}</span>
                  <span class="t-small t-num t-bold" style="flex:0 0 40px;text-align:right">${pct(sig.confidence)}</span>
                </div>
                ${sig.evidence.length ? `<div style="padding-left:var(--space-2)">${EvidenceList(sig.evidence)}</div>` : ""}
              `).join("")}`,
          })}

          ${KbcCard({
            label: "The customer's goals",
            title: "What they are actually trying to do",
            body: `
              <table class="kbc-table">
                <thead><tr>
                  <th>Goal</th><th class="t-num">Now</th><th class="t-num">Target</th>
                  <th class="t-num">Monthly</th><th>Projected</th><th>Progress</th>
                </tr></thead>
                <tbody>
                  ${advisor.goals.map((g) => `
                    <tr>
                      <td><strong>${h(g.title)}</strong><div class="kbc-meta">${h(g.origin || "")}</div></td>
                      <td class="t-num">${money(g.current_amount)}</td>
                      <td class="t-num">${money(g.target_amount)}</td>
                      <td class="t-num">${g.monthly_contribution ? money(g.monthly_contribution) : "-"}</td>
                      <td>${h(g.projected_completion || "no date")}</td>
                      <td style="min-width:90px">${KbcProgressBar({
                        value: g.target_amount ? Math.min(1, g.current_amount / g.target_amount) : 0,
                        tone: g.projected_completion === "reached" ? "success" : g.on_track ? "" : "warning",
                      })}</td>
                    </tr>`).join("")}
                </tbody>
              </table>`,
          })}

          ${KbcCard({
            label: "Future Me",
            title: "The same timeline the customer sees",
            body: KbcTimeline(advisor.timeline),
          })}
        </div>

        <!-- RIGHT: what to actually talk about -->
        <div class="stack">
          ${KbcCard({
            label: "Suggested conversation",
            title: "Topics, not offers",
            body: `
              ${advisor.conversation_topics.length
                ? advisor.conversation_topics.map((t) => `
                    <div class="topic">
                      ${h(t.topic)}
                      <div class="topic__source">
                        from &ldquo;${h(t.from_playbook)}&rdquo; &middot; ${pct(t.confidence)} confidence
                      </div>
                    </div>`).join("")
                : `<div class="kbc-meta">No playbook is active for this customer right now.</div>`}
              <div class="kbc-meta" style="margin-top:var(--space-4)">
                There are no product targets in this list, by design. Success is
                measured on the customer's progress score.
              </div>`,
          })}

          ${advisor.advisor_context.length ? KbcCard({
            label: "Context before you talk",
            body: advisor.advisor_context.map((a) => `
              <div style="padding:var(--space-3) 0;border-bottom:1px solid var(--kbc-divider)">
                <div class="row row--between">
                  <span class="t-small t-bold">${h(a.playbook)}</span>
                  ${KbcStatusChip({
                    label: pct(a.confidence),
                    tone: a.confidence >= 0.8 ? "accent" : "warning",
                  })}
                </div>
                <div class="t-small t-muted" style="margin-top:var(--space-2)">${h(a.context)}</div>
              </div>`).join(""),
          }) : ""}

          ${advisor.risks.length ? KbcCard({
            label: "Risks",
            body: advisor.risks.map((r) => `
              <div class="kbc-banner kbc-banner--${r.severity === "high" ? "danger" : "warning"}"
                   style="margin-bottom:var(--space-2)">
                <div>
                  <div class="row row--between">
                    <span class="t-small t-bold">${h(r.label)}</span>
                    ${KbcStatusChip({ label: r.severity, tone: r.severity === "high" ? "danger" : "warning" })}
                  </div>
                  ${EvidenceList(r.evidence)}
                  ${r.mitigation ? `<div class="kbc-meta" style="margin-top:var(--space-2)">${h(r.mitigation)}</div>` : ""}
                </div>
              </div>`).join(""),
          }) : ""}

          ${KbcCard({
            label: "Recent changes",
            title: "What moved, and when",
            body: `
              <div class="stack stack--sm">
                ${advisor.recent_changes.map((c) => `
                  <div style="padding-bottom:var(--space-2);border-bottom:1px solid var(--kbc-divider)">
                    <div class="row row--between">
                      ${KbcStatusChip({ label: `v${c.version}`, tone: "outline" })}
                      <span class="kbc-meta">${h(c.created_at)}</span>
                    </div>
                    <div class="t-small" style="margin-top:var(--space-2)">${h(c.change_summary)}</div>
                  </div>`).join("")}
              </div>
              <div class="kbc-meta" style="margin-top:var(--space-3)">
                Append-only version history. In production this is the audit trail.
              </div>`,
          })}
        </div>
      </div>
    </div>
  </div>`;
}

function renderConsistencyBanner(advisorVersion, customerVersion) {
  if (customerVersion === null || customerVersion === undefined) return "";
  const same = advisorVersion === customerVersion;
  return KbcInfoBanner({
    tone: same ? "success" : "danger",
    html: `<div class="t-small">
      ${same
        ? `<strong>One Twin, both channels.</strong> The customer app is showing
           version ${customerVersion} and so is this view &mdash; not a copy, the
           same document from the same API. No advisor-side personalisation
           logic exists.`
        : `<strong>Version mismatch:</strong> app v${customerVersion}, advisor
           v${advisorVersion}. An event is still in flight.`}
    </div>`,
  });
}

function initialsOf(name) {
  return (name || "").split(/\s+/).filter(Boolean).slice(0, 2)
    .map((p) => p[0].toUpperCase()).join("");
}

export function bindAdvisor() { /* read-only view */ }
