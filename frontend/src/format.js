/* Formatting helpers. Belgian conventions: nl-BE locale, EUR. */

const eur0 = new Intl.NumberFormat("nl-BE", {
  style: "currency", currency: "EUR", maximumFractionDigits: 0,
});
const eur2 = new Intl.NumberFormat("nl-BE", {
  style: "currency", currency: "EUR", minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const num = new Intl.NumberFormat("nl-BE");

export const money  = (v) => eur0.format(Math.round(v ?? 0));
export const money2 = (v) => eur2.format(v ?? 0);
export const count  = (v) => num.format(v ?? 0);
export const pct    = (v, digits = 0) => `${((v ?? 0) * 100).toFixed(digits)}%`;

export function compact(v) {
  const n = v ?? 0;
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k`;
  return num.format(n);
}

export function duration(seconds) {
  const s = seconds ?? 0;
  if (s < 1) return `${(s * 1000).toFixed(0)} ms`;
  if (s < 90) return `${s.toFixed(1)} s`;
  const m = s / 60;
  if (m < 90) return `${m.toFixed(1)} min`;
  return `${(m / 60).toFixed(1)} h`;
}

export function initials(name) {
  return (name || "")
    .split(/\s+/).filter(Boolean).slice(0, 2)
    .map((part) => part[0].toUpperCase()).join("");
}

export const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
