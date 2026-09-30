/* Thin API client. Every call goes to the ONE shared Twin API - the customer
   app, the advisor view and the architecture page all use this same module,
   which is the point being demonstrated. */

const BASE = "/api";

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (response.status === 202) return { pending: true, ...(await response.json()) };
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch { /* keep */ }
    throw new Error(detail);
  }
  return response.json();
}

export const api = {
  health:        ()            => request("/health"),
  meta:          ()            => request("/meta"),
  personas:      ()            => request("/personas"),
  architecture:  ()            => request("/architecture"),
  playbooks:     ()            => request("/playbooks"),
  benchmark:     ()            => request("/benchmark"),
  cost:          ()            => request("/cost"),
  pipeline:      (limit = 8)   => request(`/pipeline?limit=${limit}`),

  customers: (search = "", limit = 40) =>
    request(`/customers?search=${encodeURIComponent(search)}&limit=${limit}`),
  customer: (id) => request(`/customers/${id}`),

  twin:  (id, open = false) => request(`/twins/${id}${open ? "?open=true" : ""}`),
  advisor: (id)             => request(`/advisor/${id}`),
  history: (id)             => request(`/twins/${id}/history`),
  corrections: (id)         => request(`/twins/${id}/corrections`),

  correct: (id, field, value, note = "") =>
    request(`/twins/${id}/corrections`, {
      method: "POST",
      body: JSON.stringify({ field, value, note }),
    }),

  clearCorrections: (id) =>
    request(`/twins/${id}/corrections`, { method: "DELETE" }),

  /* Fire and forget: the API returns as soon as the event is on the queue,
     exactly like a Kafka producer. The UI then polls, which is what makes the
     asynchronous pipeline visible instead of hidden behind a spinner. */
  inject: (id, action) => request(`/demo/${id}/${action}`, { method: "POST" }),
  event:  (eventId)    => request(`/events/${eventId}`),
  reset:  ()           => request("/demo/reset", { method: "POST" }),
  runBenchmark: (customers) =>
    request(`/benchmark/run${customers ? `?customers=${customers}` : ""}`, { method: "POST" }),
};

/** Poll an injected event until the worker has processed it. */
export async function waitForEvent(eventId, { timeout = 20000, interval = 140 } = {}) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const trace = await api.event(eventId);
    if (trace.status === "processed") return trace;
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error("Event was not processed in time");
}
