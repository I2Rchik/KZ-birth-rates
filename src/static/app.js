// Presentation only: every number shown comes from /api/state, which reads
// data/processed and model/artifact.json. No model is estimated here.
// The scenario recomputes y-hat and its band from the artifact's
// coefficients and covariance matrix (linear algebra on stored values).
"use strict";
const Z90 = 1.6449;
let S = null;

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v)) ? "n/a" : v.toFixed(d);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function load() {
  let res;
  try {
    res = await fetch("/api/state", { cache: "no-store" });
    S = await res.json();
  } catch (e) {
    $("banners").innerHTML = `<div class="banner err">The local server is not responding. Restart it with: python run.py</div>`;
    return;
  }
  const sel = $("region");
  const regions = (S.model && S.model.regions) || (S.meta && S.meta.regions) || {};
  sel.innerHTML = `<option value="KZ">Kazakhstan (16 regions)</option>` +
    Object.entries(regions).sort((a, b) => a[1].localeCompare(b[1]))
      .map(([c, n]) => `<option value="${c}">${esc(n)}</option>`).join("");
  sel.onchange = render;
  render();
  if (S.source && !S.source.checked) setTimeout(refreshSource, 3500);
}

async function refreshSource() {
  try {
    const r = await (await fetch("/api/state", { cache: "no-store" })).json();
    S.source = r.source;
    chip();
  } catch (e) { /* server stopped: the banner on next load says so */ }
}

function retrievedDate() {
  const src = (S.meta && S.meta.sources) || [];
  const d = src.map((s) => s.retrieved).filter(Boolean).sort();
  return d.length ? d[d.length - 1] : "unknown date";
}

function chip() {
  const c = $("dataChip");
  const r = S.source || {};
  if (r.checked && r.reachable === false) {
    c.className = "chip off";
    c.textContent = `Offline: stat.gov.kz unreachable. Showing cached data retrieved ${retrievedDate()}`;
  } else {
    c.className = "chip";
    c.textContent = `Cached data, retrieved ${retrievedDate()}` + (r.checked ? "" : " · checking source…");
  }
}

function banners() {
  const out = [];
  const synth = (S.model && S.model.synthetic_data) || (S.meta && S.meta.synthetic);
  if (synth) out.push(`<div class="banner test">TEST DATA: this run uses a synthetic fixture, not official statistics. No number on this page describes Kazakhstan.</div>`);
  for (const e of S.errors || []) out.push(`<div class="banner err">${esc(e.message)}</div>`);
  const w = (S.meta && S.meta.warnings) || [];
  if (w.length) out.push(`<div class="banner warn">Data check: ${w.map(esc).join(" ")}</div>`);
  $("banners").innerHTML = out.join("");
}

function series(code) {
  if (code === "KZ") return S.model && S.model.national ? S.model.national.history : null;
  return S.history ? S.history[code] : null;
}

function forecastFor(code) {
  if (!S.model) return null;
  if (code === "KZ") return S.model.national.forecast ? { ...S.model.national.forecast, available: true, national: true } : null;
  return S.model.forecast[code];
}

function render() {
  chip();
  banners();
  const code = $("region").value;
  const regs = (S.model && S.model.regions) || (S.meta && S.meta.regions) || {};
  const name = code === "KZ" ? "Kazakhstan" : (regs[code] || code);
  const hist = (series(code) || []).filter((p) => p[1] !== null);
  const fc = forecastFor(code);
  headline(name, hist, fc);
  chart(name, hist, fc, null);
  drivers(fc);
  scenario(code, fc, hist, name);
  evidence();
  provenance();
}

function band(fc, delta, j) {
  // y-hat and its 90% bands from the artifact (coefficients, covariance, residual variance)
  const m = S.model, V = m.covariance;
  const b = m.specification.regressors.map((n) => m.coefficients[n]);
  const x = fc.x_dev.slice();
  let y = fc.yhat;
  if (j !== null && j !== undefined) { x[j] += delta; y += b[j] * delta; }
  let v = 0;
  for (let r = 0; r < x.length; r++) for (let c = 0; c < x.length; c++) v += x[r] * V[r][c] * x[c];
  const vPar = v + m.residual_variance / fc.T_i;
  const vPred = vPar + m.residual_variance;
  const L = fc.base_level;
  return { y, level: L * Math.exp(y),
           par: [L * Math.exp(y - Z90 * Math.sqrt(vPar)), L * Math.exp(y + Z90 * Math.sqrt(vPar))],
           pred: [L * Math.exp(y - Z90 * Math.sqrt(vPred)), L * Math.exp(y + Z90 * Math.sqrt(vPred))] };
}

function headline(name, hist, fc) {
  const el = $("headline");
  if (!hist.length) { el.innerHTML = `<div class="banner err">No birth-rate observations for ${esc(name)} in data/processed.</div>`; return; }
  const [q, v] = hist[hist.length - 1];
  const prev = hist.find((p) => p[0] === `${+q.slice(0, 4) - 1}${q.slice(4)}`);
  let delta = "";
  if (prev) {
    const d = v - prev[1], pct = 100 * (v / prev[1] - 1);
    delta = `<div class="delta ${d >= 0 ? "up" : "down"}">${d >= 0 ? "▲" : "▼"} ${fmt(Math.abs(d), 2)} vs ${prev[0]} (${pct >= 0 ? "+" : ""}${fmt(pct, 1)}%)</div>`;
  } else {
    delta = `<div class="muted">No observation for the same quarter a year earlier.</div>`;
  }
  let next = `<div class="muted">Forecast unavailable: the model artifact is missing.</div>`;
  if (fc && fc.available) {
    const lvl = fc.national ? fc.value : fc.forecast_level;
    let bandTxt = "";
    if (!fc.national) { const bb = band(fc, 0, null); bandTxt = `<div class="unit">90% interval ${fmt(bb.pred[0])}–${fmt(bb.pred[1])}</div>`; }
    next = `<div class="unit">Forecast for ${fc.quarter}</div><div class="big" style="font-size:30px">${fmt(lvl)}</div>${bandTxt}`;
  } else if (fc && !fc.available) {
    next = `<div class="muted">No forecast for ${esc(name)}: missing ${fc.missing.map(esc).join(", ")}.</div>`;
  }
  el.innerHTML = `
    <div><div class="unit">${esc(name)} · ${q}</div><div class="big">${fmt(v)}</div>
      <div class="unit">live births per 1,000 population, annualised</div></div>
    <div><div class="unit">Change on the same quarter last year</div>${delta}</div>
    <div>${next}</div>`;
}

function chart(name, hist, fc, scen) {
  const el = $("chart");
  if (!hist.length) { el.innerHTML = `<p class="muted">No data to plot.</p>`; return; }
  const W = 1000, H = 300, ml = 52, mr = 16, mt = 14, mb = 54;
  const pts = hist.map((p) => p[1]);
  let lo = Math.min(...pts), hi = Math.max(...pts);
  let fpt = null;
  if (fc && fc.available && !fc.national) { fpt = band(fc, scen ? scen.delta : 0, scen ? scen.j : null); lo = Math.min(lo, fpt.pred[0]); hi = Math.max(hi, fpt.pred[1]); }
  else if (fc && fc.available && fc.national) { lo = Math.min(lo, fc.value); hi = Math.max(hi, fc.value); }
  const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
  const n = hist.length + 1;
  const X = (i) => ml + (i / (n - 1)) * (W - ml - mr);
  const Y = (v) => mt + (1 - (v - lo) / (hi - lo)) * (H - mt - mb);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Birth rate history for ${esc(name)}">`;
  const ticks = 5;
  for (let k = 0; k <= ticks; k++) {
    const v = lo + (k / ticks) * (hi - lo);
    s += `<line x1="${ml}" x2="${W - mr}" y1="${Y(v)}" y2="${Y(v)}" stroke="#e7eaee"/>`;
    s += `<text x="${ml - 6}" y="${Y(v) + 4}" font-size="11" text-anchor="end" fill="#5d6b7a">${fmt(v)}</text>`;
  }
  const step = Math.max(1, Math.round(hist.length / 9));
  hist.forEach((p, i) => { if (i % step === 0) s += `<text x="${X(i)}" y="${H - mb + 16}" font-size="11" text-anchor="middle" fill="#5d6b7a">${p[0]}</text>`; });
  s += `<text x="12" y="${mt + (H - mt - mb) / 2}" font-size="11" fill="#5d6b7a" transform="rotate(-90 12 ${mt + (H - mt - mb) / 2})" text-anchor="middle">births per 1,000, annualised</text>`;
  s += `<polyline fill="none" stroke="#1f5f8b" stroke-width="2" points="${hist.map((p, i) => `${X(i)},${Y(p[1])}`).join(" ")}"/>`;
  if (fpt) {
    const xi = X(n - 1);
    s += `<rect x="${xi - 9}" y="${Y(fpt.pred[1])}" width="18" height="${Y(fpt.pred[0]) - Y(fpt.pred[1])}" fill="#1f5f8b18"/>`;
    s += `<rect x="${xi - 9}" y="${Y(fpt.par[1])}" width="18" height="${Math.max(1, Y(fpt.par[0]) - Y(fpt.par[1]))}" fill="#1f5f8b40"/>`;
    s += `<circle cx="${xi}" cy="${Y(fpt.level)}" r="5" fill="#fff" stroke="#1f5f8b" stroke-width="2"/>`;
    s += `<text x="${xi - 12}" y="${Y(fpt.level) - 10}" font-size="11" text-anchor="end" fill="#1f5f8b">${fc.quarter} forecast</text>`;
  } else if (fc && fc.available && fc.national) {
    s += `<circle cx="${X(n - 1)}" cy="${Y(fc.value)}" r="5" fill="#fff" stroke="#1f5f8b" stroke-width="2"/>`;
  }
  const src = (S.meta && S.meta.sources || []).find((x) => x.series === "births") || {};
  s += `<text x="${ml}" y="${H - 22}" font-size="11" fill="#5d6b7a">Source: ${esc(src.publisher || "Bureau of National Statistics")} (${esc(src.identifier || "series id not recorded")}), births and population, retrieved ${esc(src.retrieved || "n/a")}.</text>`;
  s += `<text x="${ml}" y="${H - 6}" font-size="11" fill="#5d6b7a">Shaded: 90% interval. Dark: parameter uncertainty from the model covariance matrix. Light: also includes residual variance.</text>`;
  s += `</svg>`;
  el.innerHTML = s;
}

function drivers(fc) {
  const el = $("drivers");
  if (!S.model) { el.innerHTML = `<p class="muted">Model missing: driver contributions cannot be shown.</p>`; return; }
  if (!fc || !fc.available) { el.innerHTML = `<p class="muted">No forecast for this region, so no contributions.</p>`; return; }
  const labels = S.model.specification.labels;
  const rows = Object.entries(fc.contributions).map(([k, v]) => [labels[k] || k, 100 * v, k]);
  rows.push(["Region's usual trend (fixed effect)", 100 * fc.region_effect, "fe"]);
  const total = rows.reduce((a, r) => a + r[1], 0);
  const mx = Math.max(...rows.map((r) => Math.abs(r[1])), 0.01);
  el.innerHTML = `<p class="muted" style="margin-top:0">Contribution to the forecast change in ${fc.quarter} versus ${fc.base_quarter}, in % (log points ×100). Read from model/artifact.json.</p>
  <table><tr><th>Term</th><th class="num">pp</th><th style="width:38%"></th></tr>
  ${rows.map((r) => `<tr><td>${esc(r[0])}</td><td class="num">${r[1] >= 0 ? "+" : ""}${fmt(r[1], 2)}</td>
    <td><div style="display:flex;${r[1] < 0 ? "justify-content:flex-end;" : ""}width:50%;${r[1] < 0 ? "" : "margin-left:50%"}">
    <div class="bar" style="width:${100 * Math.abs(r[1]) / mx}%;background:${r[1] >= 0 ? "#2f7d4f" : "#b0413e"}"></div></div></td></tr>`).join("")}
  <tr><th>Forecast change</th><th class="num">${total >= 0 ? "+" : ""}${fmt(total, 2)}</th><th></th></tr></table>`;
}

function scenario(code, fc, hist, name) {
  const el = $("scenario");
  if (!S.model) { el.innerHTML = `<p class="muted">Model missing: the scenario cannot run.</p>`; return; }
  if (code === "KZ") { el.innerHTML = `<p class="muted">Pick a region to run a scenario. The national figure is the sum of 16 regional forecasts.</p>`; return; }
  if (!fc || !fc.available) { el.innerHTML = `<p class="muted">No forecast for this region.</p>`; return; }
  const names = S.model.specification.regressors;
  const labels = S.model.specification.labels;
  const drv = names.map((n, j) => [n, j]).filter(([n]) => !n.startsWith("y_"));
  el.innerHTML = `<label class="muted">Driver <select id="scDriver">${drv.map(([n, j]) => `<option value="${j}">${esc(labels[n])}</option>`).join("")}</select></label>
    <div style="margin:10px 0"><input id="scDelta" type="range" min="-20" max="20" step="1" value="0" style="width:100%"></div>
    <div id="scOut"></div>`;
  const upd = () => {
    const j = +$("scDriver").value, nm = names[j];
    const isPP = nm.startsWith("u_");
    const raw = +$("scDelta").value;
    const delta = isPP ? raw / 10 : raw / 100;
    const b = band(fc, delta, j);
    const unit = isPP ? `${raw >= 0 ? "+" : ""}${fmt(raw / 10, 1)} pp` : `${raw >= 0 ? "+" : ""}${raw}%`;
    const base = fc.base_level;
    let sig;
    if (b.pred[1] < base) sig = `Signal: fewer births than in ${fc.base_quarter}. Plan maternity and newborn services for about ${fmt(100 * (1 - b.level / base), 1)}% fewer births.`;
    else if (b.pred[0] > base) sig = `Signal: more births than in ${fc.base_quarter}. Plan for about ${fmt(100 * (b.level / base - 1), 1)}% more births.`;
    else sig = `No clear signal: the 90% interval includes last year's level (${fmt(base)}). Plan at last year's level.`;
    $("scOut").innerHTML = `<div class="muted">Change the driver by ${unit} (year-on-year, entering with its pre-registered lag)</div>
      <div style="font-size:26px;font-weight:700">${fmt(b.level)} <span class="unit">per 1,000 in ${fc.quarter}</span></div>
      <div class="muted">90% interval ${fmt(b.pred[0])}–${fmt(b.pred[1])} · parameter-only ${fmt(b.par[0])}–${fmt(b.par[1])}</div>
      <div class="signal">${sig}</div>`;
    chart(name, hist, fc, { delta, j });
  };
  $("scDriver").onchange = upd;
  $("scDelta").oninput = upd;
  upd();
}

function evidence() {
  const el = $("evidence");
  if (!S.model) { el.innerHTML = `<p class="muted">Model missing.</p>`; return; }
  const b = S.model.benchmark, f = S.model.falsification, fl = S.model.diagnostic_flags;
  const issues = Object.entries(fl).filter(([k, v]) => (Array.isArray(v) ? v.length : v))
    .map(([k, v]) => Array.isArray(v) ? `parameter break at ${v.join(", ")}` : k.replace(/_/g, " "));
  el.innerHTML = `<table>
    <tr><th>Hold-out ${b.test_window[0]}–${b.test_window[1]}</th><th class="num">Model</th><th class="num">Benchmark</th></tr>
    <tr><td>RMSE, per 1,000</td><td class="num">${fmt(b.rmse_model, 3)}</td><td class="num">${fmt(b.rmse_benchmark, 3)}</td></tr>
    <tr><td>MAE, per 1,000</td><td class="num">${fmt(b.mae_model, 3)}</td><td class="num">${fmt(b.mae_benchmark, 3)}</td></tr></table>
    <p style="margin:8px 0 4px"><b>${b.winner === "model" ? "The model beats" : "The model does not beat"}</b> the benchmark (same quarter last year): RMSE ratio ${fmt(b.rmse_ratio, 3)}.</p>
    <p class="muted" style="margin:0">Marriage effect positive at 5%: ${f.rule_2_marriage_positive_5pct ? (f.rule_2_marriage_positive_5pct.passed ? "yes" : "no") : "not estimable"}.
    Diagnostics flagged: ${issues.length ? issues.map(esc).join("; ") : "none"}. Standard errors are Driscoll–Kraay.</p>`;
}

function provenance() {
  const el = $("provenance");
  const src = (S.meta && S.meta.sources) || [];
  const m = S.model;
  el.innerHTML = `<table><tr><th>Series</th><th>Publisher · identifier</th><th>Retrieved</th></tr>
    ${src.map((s) => `<tr><td>${esc(s.series)}</td><td>${esc(s.publisher || "")} · ${esc(s.identifier || "")}</td><td>${esc(s.retrieved || "")}</td></tr>`).join("")}</table>
    <p class="muted" style="margin:8px 0 0">Data ${S.meta ? `${S.meta.first_quarter}–${S.meta.last_quarter}` : "n/a"}.
    ${m ? `Model estimated ${esc(m.estimated_at)} on ${m.specification.sample_window[0]}–${m.specification.sample_window[1]} (${m.specification.n_obs} region-quarters).` : "Model not available."}</p>`;
}

load();
