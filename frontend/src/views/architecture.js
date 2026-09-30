/* ==========================================================================
   ARCHITECTURE / SCALE

   Two jobs: explain the three tiers in plain language, and show the MEASURED
   benchmark with its extrapolation clearly labelled as an estimate.

   Everything numeric on this page comes from GET /api/benchmark and
   GET /api/cost. Nothing is hardcoded in the frontend - if the benchmark has
   not finished, the page says so rather than showing a placeholder number.
   ========================================================================== */

import { api } from "../api.js";
import {
  KbcCard, KbcInfoBanner, KbcPrimaryButton, KbcStatusChip, MetricTile, toast,
} from "../components.js";
import { compact, count, duration, escapeHtml as h, money2, pct } from "../format.js";

export const archState = { running: false };

export function renderArchitecture(ctx) {
  const { architecture, benchmark, cost, meta } = ctx;
  return `
  <div class="page">
    <div class="page__inner stack stack--lg">

      ${KbcCard({
        label: "Architecture",
        title: "One Twin, every channel",
        body: `
          <p class="t-body t-muted" style="margin:0 auto var(--space-6);max-width:62ch;text-align:center">
            Channels do not each keep their own idea of the customer. They publish
            events into one pipeline and read one shared model back out. The
            customer owns that model and can correct it.
          </p>
          ${renderFlow(architecture)}`,
      })}

      ${renderTiers(architecture)}
      ${renderMapping(architecture)}
      ${renderBenchmark(benchmark)}
      ${renderCost(cost)}
      ${renderPrivacy(meta)}
    </div>
  </div>`;
}

/* ==========================================================================
   Flow diagram
   ========================================================================== */
function renderFlow(architecture) {
  const channels = architecture?.channels || [];
  const channelColor = {
    core_banking: "var(--kbc-channel-core)",
    kbc_mobile: "var(--kbc-channel-mobile)",
    kate: "var(--kbc-channel-kate)",
    advisor: "var(--kbc-channel-visit)",
    insurance: "var(--kbc-channel-insurance)",
    lending: "var(--kbc-channel-lending)",
  };
  const arrow = `<div class="arch-arrow">&#8595;</div>`;
  return `
    <div class="arch-flow">
      <div class="arch-node arch-node--channels">
        <div class="arch-node__title" style="margin-bottom:var(--space-3)">Channels write events</div>
        <div class="channel-chips">
          ${channels.map((c) => `
            <span class="channel-chip">
              <span class="channel-chip__dot" style="background:${channelColor[c.id] || "var(--kbc-accent)"}"></span>
              ${h(c.label)}
            </span>`).join("")}
        </div>
      </div>
      ${arrow}
      <div class="arch-node">
        <div class="arch-node__title">Event ingestion</div>
        <div class="arch-node__sub">asyncio.Queue here &middot; Kafka in production, partitioned by customer_id</div>
      </div>
      ${arrow}
      <div class="arch-node arch-node--tier">
        <div class="arch-node__title">Tier 1 &mdash; streaming feature updates</div>
        <div class="arch-node__sub">One function folds each transaction into per-customer feature state</div>
      </div>
      ${arrow}
      <div class="arch-node arch-node--tier">
        <div class="arch-node__title">Tier 2 &mdash; life-event scoring</div>
        <div class="arch-node__sub">Interpretable weighted models, each output carrying its own evidence</div>
      </div>
      ${arrow}
      <div class="arch-node arch-node--twin">
        <div class="arch-node__title">The Financial Twin</div>
        <div class="arch-node__sub">Versioned, explainable, correctable. The single source of truth.</div>
      </div>
      ${arrow}
      <div class="arch-node">
        <div class="arch-node__title">Shared Twin API</div>
        <div class="arch-node__sub">Every channel reads and writes this one document</div>
      </div>
      ${arrow}
      <div class="row" style="gap:var(--space-4);flex-wrap:wrap;justify-content:center;width:100%;max-width:560px">
        <div class="arch-node" style="flex:1;min-width:150px">
          <div class="arch-node__title">Customer app</div>
        </div>
        <div class="arch-node" style="flex:1;min-width:150px">
          <div class="arch-node__title">Kate</div>
        </div>
        <div class="arch-node" style="flex:1;min-width:150px">
          <div class="arch-node__title">Advisor</div>
        </div>
      </div>
      ${arrow}
      <div class="arch-node arch-node--tier" style="border-left-color:var(--kbc-channel-kate)">
        <div class="arch-node__title">Tier 3 &mdash; narrative generation</div>
        <div class="arch-node__sub">
          Claude, or a deterministic template. Called on Twin change or app open.
          Never per transaction, never to calculate.
        </div>
      </div>
    </div>`;
}

/* ==========================================================================
   Tiers
   ========================================================================== */
function renderTiers(architecture) {
  const tiers = architecture?.tiers || [];
  return `<div class="grid grid--3">
    ${tiers.map((t) => KbcCard({
      label: `Tier ${t.tier}`,
      title: t.name,
      body: `
        <p class="t-small" style="margin-bottom:var(--space-4)">${h(t.what_it_does)}</p>
        <div class="fact-list">
          <div class="fact">
            <span class="fact__label">Here</span>
            <span class="fact__value" style="font-weight:var(--weight-regular);text-align:right">${h(t.hackathon)}</span>
          </div>
          <div class="fact">
            <span class="fact__label">Production</span>
            <span class="fact__value" style="font-weight:var(--weight-regular);text-align:right">${h(t.production)}</span>
          </div>
        </div>
        <div class="t-mono t-muted" style="margin-top:var(--space-3)">${h(t.module)}</div>`,
    })).join("")}
  </div>`;
}

function renderMapping(architecture) {
  const rows = architecture?.production_mapping || [];
  return KbcCard({
    label: "Production mapping",
    title: "What each piece becomes at KBC scale",
    body: `
      <table class="kbc-table">
        <thead><tr><th>This prototype</th><th>Production</th></tr></thead>
        <tbody>
          ${rows.map((r) => `
            <tr>
              <td class="t-mono">${h(r.hackathon)}</td>
              <td><strong>${h(r.production)}</strong></td>
            </tr>`).join("")}
        </tbody>
      </table>
      ${architecture?.invariant ? KbcInfoBanner({
        tone: "success",
        html: `<div class="t-small"><strong>Why this scales.</strong> ${h(architecture.invariant)}</div>`,
      }) : ""}`,
  });
}

/* ==========================================================================
   Benchmark - measured, then extrapolated
   ========================================================================== */
function renderBenchmark(benchmark) {
  if (!benchmark || benchmark.pending || benchmark.status !== "complete") {
    return KbcCard({
      label: "Scale benchmark",
      title: "Measuring...",
      body: `
        ${KbcInfoBanner({
          tone: "warning",
          html: `<div class="t-small">The benchmark runs once at startup, in a
                 background thread. It takes a few seconds. This page shows only
                 measured numbers, so there is nothing to display until it finishes.</div>`,
        })}
        <div class="grid grid--3" style="margin-top:var(--space-4)">
          ${[1, 2, 3].map(() => `<div class="skeleton" style="height:88px"></div>`).join("")}
        </div>
        <div style="margin-top:var(--space-4)">
          ${KbcPrimaryButton({ label: "Run it now", attrs: 'data-run-benchmark="1"' })}
        </div>`,
    });
  }

  const m = benchmark.measured;
  const e = benchmark.extrapolation;
  return `
    ${KbcCard({
      label: "Scale benchmark",
      title: "Measured on this machine, just now",
      action: KbcStatusChip({ label: "measured", tone: "success" }),
      body: `
        <div class="grid grid--3">
          ${MetricTile({ value: count(m.customers), label: "Customers simulated" })}
          ${MetricTile({ value: compact(m.events_processed), label: "Events processed" })}
          ${MetricTile({ value: compact(Math.round(m.events_per_second)), label: "Events / second", accent: true })}
          ${MetricTile({ value: `${m.avg_event_latency_us.toFixed(1)} µs`, label: "Average per event" })}
          ${MetricTile({ value: `${m.per_customer_latency_ms.p95.toFixed(2)} ms`, label: "p95 per customer" })}
          ${MetricTile({ value: `${m.peak_rss_mb} MB`, label: "Peak memory" })}
        </div>
        <div class="grid grid--2" style="margin-top:var(--space-5)">
          <div>
            <div class="kbc-card__label">What was timed</div>
            <ul class="evidence">
              ${benchmark.scope.included.map((i) => `<li><span>${h(i)}</span></li>`).join("")}
            </ul>
          </div>
          <div>
            <div class="kbc-card__label">What was not</div>
            <ul class="evidence">
              ${benchmark.scope.excluded.map((i) => `<li><span>${h(i)}</span></li>`).join("")}
            </ul>
          </div>
        </div>
        <div class="kbc-meta" style="margin-top:var(--space-3)">${h(benchmark.scope.why)}</div>
        <div class="kbc-meta" style="margin-top:var(--space-3)">
          ${h(benchmark.environment.platform)} &middot; Python ${h(benchmark.environment.python)}
          &middot; ${benchmark.environment.cpu_count} cores &middot; wall ${duration(m.wall_seconds)}
        </div>
        <div style="margin-top:var(--space-4)">
          ${KbcPrimaryButton({ label: archState.running ? "Running..." : "Re-run the benchmark", attrs: `data-run-benchmark="1" ${archState.running ? "disabled" : ""}` })}
        </div>`,
    })}

    ${KbcCard({
      label: "Extrapolation",
      title: `To ${count(e.target_population)} customers`,
      action: KbcStatusChip({ label: "estimate, not measured", tone: "warning" }),
      body: `
        ${KbcInfoBanner({
          tone: "warning",
          html: `<div class="t-small"><strong>This is arithmetic, not a measurement.</strong>
                 ${h(e.basis)}</div>`,
        })}
        <div class="grid grid--2" style="margin-top:var(--space-4)">
          ${MetricTile({
            value: compact(e.equivalent_events), label: "Equivalent monthly events",
            sub: `${count(e.target_population)} customers at the same events per customer`,
          })}
          ${MetricTile({
            value: duration(e.single_worker_seconds), label: "One worker, one core",
            sub: "Straight division of the measured rate",
          })}
          ${MetricTile({
            value: duration(e.parallel_seconds), label: `${e.parallel_workers} parallel workers`,
            accent: true,
            sub: "Theoretical, assuming clean partitioning by customer",
          })}
          ${MetricTile({
            value: pct(1), label: "Of events handled without an LLM",
            sub: "Tier 1 and Tier 2 are deterministic code",
          })}
        </div>
        <div style="margin-top:var(--space-5)">
          <div class="kbc-card__label">Caveats we are not hiding</div>
          <ul class="evidence">
            ${e.caveats.map((c) => `<li><span>${h(c)}</span></li>`).join("")}
          </ul>
        </div>`,
    })}`;
}

/* ==========================================================================
   Cost
   ========================================================================== */
function renderCost(cost) {
  if (!cost) return "";
  const a = cost.assumptions;
  const llm = cost.llm;
  const naive = cost.naive_per_transaction;
  return KbcCard({
    label: "Cost shape",
    title: "Why selective LLM use is the whole economic argument",
    body: `
      <div class="grid grid--3">
        ${MetricTile({
          value: compact(llm.monthly_calls), label: "LLM calls / month",
          sub: "On Twin state change, or when the customer opens the app",
        })}
        ${MetricTile({
          value: compact(naive.monthly_calls), label: "If we called per transaction",
          sub: `${naive.multiple_of_selective}x more calls for the same customers`,
        })}
        ${MetricTile({
          value: `${naive.multiple_of_selective}x`, label: "Cost avoided", accent: true,
          sub: "Same population, same model, different trigger",
        })}
      </div>

      <div class="grid grid--2" style="margin-top:var(--space-5)">
        <div>
          <div class="kbc-card__label">Deterministic core</div>
          <div class="fact-list">
            <div class="fact"><span class="fact__label">Monthly events</span>
              <span class="fact__value">${compact(cost.deterministic_core.monthly_events)}</span></div>
            <div class="fact"><span class="fact__label">Measured rate</span>
              <span class="fact__value">${compact(Math.round(cost.deterministic_core.measured_events_per_second))} /s</span></div>
            <div class="fact"><span class="fact__label">Single-worker CPU</span>
              <span class="fact__value">${cost.deterministic_core.single_worker_hours_per_month} h / month</span></div>
          </div>
          <div class="kbc-meta" style="margin-top:var(--space-2)">${h(cost.deterministic_core.note)}</div>
        </div>
        <div>
          <div class="kbc-card__label">Storage</div>
          <div class="kbc-meta">${h(cost.storage.note)}</div>
          <div class="kbc-card__label" style="margin-top:var(--space-4)">LLM per call</div>
          <div class="fact-list">
            <div class="fact"><span class="fact__label">Tokens in / out</span>
              <span class="fact__value">${a.tokens_per_call_in} / ${a.tokens_per_call_out}</span></div>
            <div class="fact"><span class="fact__label">Cost per call</span>
              <span class="fact__value">${money2(llm.cost_per_call_usd)}</span></div>
            <div class="fact"><span class="fact__label">Monthly, selective</span>
              <span class="fact__value">${money2(llm.monthly_cost_usd)}</span></div>
            <div class="fact"><span class="fact__label">Monthly, per transaction</span>
              <span class="fact__value">${money2(naive.monthly_cost_usd)}</span></div>
          </div>
        </div>
      </div>

      ${KbcInfoBanner({
        tone: "neutral",
        html: `<div class="t-small">
          <strong>Every input above is configurable.</strong> Population
          ${count(a.population)}, ${pct(a.daily_app_open_rate)} open the app daily,
          ${pct(a.monthly_twin_change_rate)} have a meaningful Twin change per month,
          prices ${money2(a.price_input_per_mtok_usd)} / ${money2(a.price_output_per_mtok_usd)}
          per million tokens in / out. ${h(a.price_source)}
        </div>`,
      })}`,
  });
}

/* ==========================================================================
   Privacy / banking safety
   ========================================================================== */
function renderPrivacy(meta) {
  const items = [
    ["GDPR and purpose limitation", "Inferences derived for one purpose cannot silently serve another."],
    ["Consent", "Sensitive-adjacent inference (family expansion, health) needs an explicit basis, not an inferred one."],
    ["Data minimisation", "The Twin holds derived state, not a copy of the transaction history."],
    ["Explainability", "Every field carries its evidence. Nothing is a black box by construction."],
    ["Correction rights", "The customer can inspect and override, and the override persists."],
    ["Audit trail", "Twin versions are append-only, so any decision can be reconstructed."],
    ["Sensitive inference controls", "Some signals should require an opt-in before they are ever computed."],
    ["Human oversight", "The advisor view separates fact from assumption so a human can catch a wrong model."],
    ["Model governance", "Tier 2 thresholds are versioned config, reviewable like any other control."],
    ["Security boundaries", "Channel identity, per-field authorisation, and a hard no on raw data leaving the Twin service."],
  ];
  return KbcCard({
    label: "Privacy and banking safety",
    title: "What a production version would have to satisfy",
    body: `
      ${KbcInfoBanner({
        tone: "danger",
        html: `<div class="t-small"><strong>This prototype is entirely synthetic.</strong>
               ${h(meta?.synthetic_data_notice || "")} It makes no claim of
               regulatory compliance. A production version would need to be
               designed and validated against KBC's legal, risk, security and
               GDPR requirements.</div>`,
      })}
      <div class="grid grid--2" style="margin-top:var(--space-4)">
        ${items.map(([title, body]) => `
          <div style="padding:var(--space-3) 0;border-bottom:1px solid var(--kbc-divider)">
            <div class="t-small t-bold">${h(title)}</div>
            <div class="kbc-meta" style="margin-top:2px">${h(body)}</div>
          </div>`).join("")}
      </div>
      <div style="margin-top:var(--space-5)">
        <div class="kbc-card__label">The distinction the model enforces</div>
        <div class="grid grid--2" style="margin-top:var(--space-2)">
          ${[
            ["observed", "It happened. A transaction, a balance."],
            ["derived", "Arithmetic on observed data. Reproducible."],
            ["inferred", "A probabilistic conclusion. May be wrong."],
            ["declared", "The customer told us. Outranks the rest."],
          ].map(([p, text]) => `
            <div class="row" style="gap:var(--space-2);align-items:flex-start;padding:var(--space-2) 0">
              <span class="kbc-chip kbc-prov--${p}" style="flex:0 0 auto">${h(p)}</span>
              <span class="kbc-meta">${h(text)}</span>
            </div>`).join("")}
        </div>
      </div>`,
  });
}

/* ==========================================================================
   Behaviour
   ========================================================================== */
export function bindArchitecture(root, ctx, refresh) {
  root.querySelectorAll("[data-run-benchmark]").forEach((el) =>
    el.addEventListener("click", async () => {
      archState.running = true;
      await refresh();
      try {
        await api.runBenchmark();
        toast("Benchmark finished. Figures below are the new measurement.");
      } catch (error) {
        toast(`Benchmark failed: ${error.message}`);
      } finally {
        archState.running = false;
        await refresh({ reload: true });
      }
    }));
}
