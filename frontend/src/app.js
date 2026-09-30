/* ==========================================================================
   App shell: routing, data loading, re-render.

   Deliberately a ~200-line vanilla router rather than a framework. It keeps
   the prototype buildless (no npm, no bundler, no node_modules in the image)
   which is the single biggest reduction in setup complexity available here.
   ========================================================================== */

import { api } from "./api.js";
import { KbcHeader, toast } from "./components.js";
import {
  bindArchitecture, renderArchitecture,
} from "./views/architecture.js";
import { bindAdvisor, renderAdvisor } from "./views/advisor.js";
import { bindCustomer, customerState, renderCustomer } from "./views/customer.js";

const TABS = [
  { id: "customer",     label: "Customer App",         short: "App" },
  { id: "advisor",      label: "Advisor View",         short: "Advisor" },
  { id: "architecture", label: "Architecture & Scale", short: "Scale" },
];

const ctx = {
  route: "customer",
  meta: null,
  health: null,
  personas: [],
  twin: null,
  customer: null,
  advisor: null,
  architecture: null,
  benchmark: null,
  cost: null,
  customerTwinVersion: null,
};

const root = document.getElementById("app");

/* ==========================================================================
   Data loading - only what the active route needs
   ========================================================================== */
async function loadShared() {
  const [meta, health, personas] = await Promise.all([
    api.meta(), api.health(), api.personas(),
  ]);
  ctx.meta = meta;
  ctx.health = health;
  ctx.personas = personas.personas;
  if (!customerState.customerId && ctx.personas.length) {
    customerState.customerId = ctx.personas[0].customer_id;
  }
}

async function loadRoute() {
  const id = customerState.customerId;
  if (ctx.route === "customer" && id) {
    const [twin, customer] = await Promise.all([
      api.twin(id, !ctx.twin),      // ?open=true only on first open (Tier 3 trigger)
      api.customer(id),
    ]);
    ctx.twin = twin;
    ctx.customer = customer;
    ctx.customerTwinVersion = twin.version;
  } else if (ctx.route === "advisor" && id) {
    const [advisor, twin] = await Promise.all([api.advisor(id), api.twin(id)]);
    ctx.advisor = advisor;
    ctx.customerTwinVersion = twin.version;
  } else if (ctx.route === "architecture") {
    const [architecture, benchmark, cost] = await Promise.all([
      api.architecture(), api.benchmark(), api.cost(),
    ]);
    ctx.architecture = architecture;
    ctx.benchmark = benchmark;
    ctx.cost = cost;
  }
}

/* ==========================================================================
   Render
   ========================================================================== */
function statusHtml() {
  const bus = ctx.health?.event_bus;
  const tier3 = ctx.meta?.tier3;
  if (!bus) return "";
  const busy = bus.queue_depth > 0;
  return `
    <span class="kbc-dot ${busy ? "kbc-dot--busy" : bus.worker_running ? "" : "kbc-dot--idle"}"></span>
    <span>queue ${bus.queue_depth} &middot; ${bus.processed} processed</span>
    <span style="opacity:.6">&middot; Tier 3: ${tier3?.generator || "?"}</span>`;
}

function renderRoute() {
  switch (ctx.route) {
    case "advisor":      return renderAdvisor(ctx);
    case "architecture": return renderArchitecture(ctx);
    default:             return renderCustomer(ctx);
  }
}

function bindRoute() {
  root.querySelectorAll("[data-route]").forEach((el) =>
    el.addEventListener("click", () => navigate(el.dataset.route)));

  switch (ctx.route) {
    case "advisor":      bindAdvisor(root, ctx, refresh); break;
    case "architecture": bindArchitecture(root, ctx, refresh); break;
    default:             bindCustomer(root, ctx, refresh); break;
  }
}

/**
 * Re-render.
 *  reload       - refetch route data first
 *  pipelineOnly - swap just the pipeline card, so the phone does not
 *                 re-render (and lose scroll position) 6 times per animation
 */
async function refresh({ reload = false, pipelineOnly = false } = {}) {
  if (reload) {
    try {
      await Promise.all([loadRoute(), api.health().then((h) => { ctx.health = h; })]);
    } catch (error) {
      toast(`Could not load: ${error.message}`);
    }
  }

  if (pipelineOnly && ctx.route === "customer") {
    const fresh = document.createElement("div");
    fresh.innerHTML = renderCustomer(ctx);
    const next = fresh.querySelector("#pipeline-card");
    const current = root.querySelector("#pipeline-card");
    if (next && current) {
      current.replaceWith(next);
      next.querySelectorAll("[data-route]").forEach(() => {});
      return;
    }
  }

  const scroll = root.querySelector("#phone-scroll")?.scrollTop ?? 0;
  root.innerHTML =
    KbcHeader({ tabs: TABS, active: ctx.route, status: statusHtml() }) + renderRoute();
  const scroller = root.querySelector("#phone-scroll");
  if (scroller) scroller.scrollTop = scroll;
  bindRoute();
}

async function navigate(route) {
  if (route === ctx.route) return;
  ctx.route = route;
  await refresh({ reload: true });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ==========================================================================
   Boot
   ========================================================================== */
async function boot() {
  root.innerHTML = `
    <div class="kbc-appbar">
      <span class="kbc-wordmark"><span class="kbc-wordmark__mark">KBC</span> Financial Twin</span>
    </div>
    <div class="page"><div class="page__inner stack">
      <div class="skeleton" style="height:120px"></div>
      <div class="skeleton" style="height:320px"></div>
    </div></div>`;

  // The API seeds 1,000 customers on first boot, so give it a few tries.
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      await loadShared();
      break;
    } catch (error) {
      if (attempt === 39) {
        root.innerHTML = `<div class="page"><div class="page__inner">
          <div class="kbc-banner kbc-banner--danger">
            <div>Could not reach the Twin API. Is the backend running?
            <div class="t-mono" style="margin-top:8px">${error.message}</div></div>
          </div></div></div>`;
        return;
      }
      await new Promise((r) => setTimeout(r, 600));
    }
  }

  await refresh({ reload: true });

  // Keep the header's queue counter live. Cheap, and it makes the
  // asynchronous pipeline legible without any user action.
  setInterval(async () => {
    try {
      const health = await api.health();
      ctx.health = health;
      const status = root.querySelector(".kbc-appbar__status");
      if (status) status.innerHTML = statusHtml();
    } catch { /* ignore transient errors */ }
  }, 2500);
}

boot();
