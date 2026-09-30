/* ==========================================================================
   App shell: data loading, re-render.

   Deliberately vanilla rather than a framework. It keeps
   the prototype buildless (no npm, no bundler, no node_modules in the image)
   which is the single biggest reduction in setup complexity available here.
   ========================================================================== */

import { api } from "./api.js";
import { KbcHeader, toast } from "./components.js";
import {
  bindCustomer, customerState, renderCustomer, resetCustomerState,
} from "./views/customer.js";

const ctx = {
  meta: null,
  health: null,
  personas: [],
  twin: null,
  customer: null,
  customerTwinVersion: null,
};

const root = document.getElementById("app");

/* ==========================================================================
   Data loading
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
  if (!id) return;
  const [twin, customer] = await Promise.all([
    api.twin(id, !ctx.twin),      // ?open=true only on first open (Tier 3 trigger)
    api.customer(id),
  ]);
  ctx.twin = twin;
  ctx.customer = customer;
  ctx.customerTwinVersion = twin.version;
}

/* ==========================================================================
   Render
   ========================================================================== */
function bindRoute() {
  root.querySelectorAll("[data-persona]").forEach((el) =>
    el.addEventListener("click", async () => {
      if (el.dataset.persona === customerState.customerId) return;
      customerState.customerId = el.dataset.persona;
      resetCustomerState();
      await refresh({ reload: true, resetScroll: true });
    }));

  bindCustomer(root, ctx, refresh);
}

/**
 * Re-render.
 *  reload      - refetch data first
 *  resetScroll - start the phone at the top (new customer)
 */
async function refresh({ reload = false, resetScroll = false } = {}) {
  if (reload) {
    try {
      await loadRoute();
    } catch (error) {
      toast(`Could not load: ${error.message}`);
    }
  }

  const scroll = resetScroll ? 0 : root.querySelector("#phone-scroll")?.scrollTop ?? 0;
  root.innerHTML = KbcHeader({
    personas: ctx.personas, customerId: customerState.customerId,
  }) + renderCustomer(ctx);
  const scroller = root.querySelector("#phone-scroll");
  if (scroller) scroller.scrollTop = scroll;
  bindRoute();
}


/* ==========================================================================
   Boot
   ========================================================================== */
async function boot() {
  root.innerHTML = `
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
}

boot();
