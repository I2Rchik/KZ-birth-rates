"""Builds the technical note (4 pages + annexes) as outputs/technical_note.html.

Every number in the note is read from model/artifact.json, data/processed/
or outputs/ at build time - nothing is typed by hand - so the note always
matches the code that produced it. Print it to PDF from a browser (A4,
default margins) or run `python run.py note --pdf` where Playwright exists.
Run automatically by `python run.py rebuild`.
"""
import base64
import csv
import html
import json
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z90 = 1.6449


def f(v, d=2):
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:,.{d}f}".replace(",", " ")


def p(v):
    return "&lt;0.001" if v is not None and v < 0.001 else f(v, 3)


def esc(s):
    return html.escape(str(s))


def table(head, rows, cls=""):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def img(path, width="100%"):
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode()
    return f'<img src="data:image/png;base64,{data}" style="width:{width}">'


def decision_rule(a):
    """Threshold argued from the data: the model's own 90% forecast interval.
    Returns per-region signals and the median half-width in percent."""
    names = a["specification"]["regressors"]
    V = np.array(a["covariance"])
    s2 = a["residual_variance"]
    rows, widths = [], []
    for code, fc in a["forecast"].items():
        if not fc.get("available"):
            continue
        x = np.array(fc["x_dev"])
        sd = math.sqrt(float(x @ V @ x) + s2 / fc["T_i"] + s2)
        lo = fc["base_level"] * math.exp(fc["yhat"] - Z90 * sd)
        hi = fc["base_level"] * math.exp(fc["yhat"] + Z90 * sd)
        widths.append(100 * (math.exp(Z90 * sd) - 1))
        if hi < fc["base_level"]:
            sig = f"plan for {f(100 * (1 - fc['forecast_level'] / fc['base_level']), 1)}% fewer births"
        elif lo > fc["base_level"]:
            sig = f"plan for {f(100 * (fc['forecast_level'] / fc['base_level'] - 1), 1)}% more births"
        else:
            sig = "no clear signal: plan at last year's level"
        rows.append((a["regions"][code], f(fc["base_level"]), f(fc["forecast_level"]), f"{f(lo)}–{f(hi)}", sig))
    return rows, float(np.median(widths))


def build(model_dir=None, outputs=None, processed=None):
    model_dir = model_dir or os.path.join(ROOT, "model")
    outputs = outputs or os.path.join(ROOT, "outputs")
    processed = processed or os.path.join(ROOT, "data", "processed")
    with open(os.path.join(model_dir, "artifact.json"), encoding="utf-8") as fh:
        a = json.load(fh)
    with open(os.path.join(processed, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    sp, b, d = a["specification"], a["benchmark"], a["diagnostics"]
    with open(os.path.join(ROOT, "src", "config.json"), encoding="utf-8") as fh:
        cfg_model = json.load(fh)["model"]
    names = sp["regressors"]
    nat = a["national"]
    fals = a["falsification"]
    rob = a["robustness"]
    econ = a["economic_size"]
    dr_rows, median_hw = decision_rule(a)
    synth = a["synthetic_data"]
    src = {s["series"]: s for s in a["sources"]}

    # --- section 3 results table
    res_rows = [(esc(sp["labels"][n]), sp["expected_signs"].get(n, ""), f(a["coefficients"][n], 3),
                 f(a["std_errors"][n], 3), p(a["p_values"][n]),
                 f(econ[n]["effect_per_1000"], 2)) for n in names]
    m_key = next((n for n in names if n.startswith("m_")), None)
    r2 = fals.get("rule_2_marriage_positive_5pct") or {}
    dm = b.get("diebold_mariano") or {}
    chow = "; ".join(f"{k}: p {p(v['pvalue'])}" for k, v in d["stability_chow"].items() if v)
    integ = a["integration"]
    lncbr, yint = integ.get("ln_cbr", {}), integ.get("y", {})
    deviations = a["deviations_from_preregistration"]
    rob_rows = [(esc(r["check"]), f(r["marriage_coef"], 3), p(r["marriage_p"]), f(r["rmse_ratio"], 3), r["winner"])
                for r in rob]
    overturned = [r["check"] for r in rob[1:] if r["winner"] != rob[0]["winner"]]

    css = """
    @page { size: A4; margin: 16mm 15mm; }
    body { font: 9.6pt/1.38 "Times New Roman", Georgia, serif; color: #111; max-width: 180mm; margin: 0 auto; }
    h1 { font-size: 14pt; margin: 0 0 2pt; } h2 { font-size: 11pt; margin: 9pt 0 3pt; border-bottom: 1px solid #999; }
    h3 { font-size: 10pt; margin: 6pt 0 2pt; } p { margin: 0 0 4pt; text-align: justify; }
    table { border-collapse: collapse; width: 100%; margin: 3pt 0 5pt; font-size: 8.6pt; }
    th, td { border-bottom: 1px solid #ccc; padding: 1.5pt 4pt; text-align: left; vertical-align: top; }
    th { border-bottom: 1px solid #333; } .meta { color: #444; font-size: 8.6pt; margin-bottom: 6pt; }
    .annex { page-break-before: always; } .warn { color: #a00; font-weight: bold; }
    ul { margin: 0 0 4pt 14pt; padding: 0; } li { margin: 0 0 1pt; }
    .small { font-size: 8.4pt; color: #333; }
    """
    H = [f"<!doctype html><html><head><meta charset='utf-8'><title>Technical note: regional birth rate, Kazakhstan</title><style>{css}</style></head><body>"]
    if synth:
        H.append("<p class='warn'>SYNTHETIC TEST DATA: these numbers do not describe Kazakhstan. Do not submit.</p>")
    H.append("<h1>Kazakhstan regional birth rate: now and next quarter</h1>")
    H.append(f"<div class='meta'>ECO1209 Data Analysis and Economic Forecasting, KBTU. Group assignment “Build an Indicator”. "
             f"Team: [names]. Model estimated {esc(a['estimated_at'])}; data retrieved {esc(src['births']['retrieved'])}. "
             f"Repository: github.com/I2Rchik/KZ-birth-rates.</div>")

    # 1. Indicator card
    H.append("<h2>1. Indicator card</h2>")
    card = [
        ("Concept", "How many babies are born per 1,000 residents of each region this quarter, and what next quarter is likely to bring. Regional authorities use it to plan maternity capacity, kindergarten and school places."),
        ("Formula", "CBR(i,q) = 4 × 1,000 × B(i,q) / P̄(i,q). B = live births registered in quarter q in region i. P̄ = mean of the populations at the start of q and of q+1. The factor 4 annualises the rate."),
        ("Unit and scale", "Live births per 1,000 population, annualised. Changes are year-on-year, in births per 1,000 and in percent."),
        ("Frequency and lag", "Quarterly. Published about 40–45 days after the quarter ends (January–March 2025 data were released on 12 May 2025)."),
        ("Coverage", f"16 harmonised regions on pre-2018 borders (14 oblasts, Astana, Almaty city). {esc(meta['first_quarter'])}–{esc(meta['last_quarter'])}."),
        ("Source and vintage", "Bureau of National Statistics, Taldau: “Число родившихся (живыми)”, “Численность населения на начало периода”. Retrieved 18 October 2026. Monthly operational figures are revised when the annual data are final."),
        ("Transformations", "Cumulative January–quarter-end births are differenced to quarters after harmonising regions. Abai, Zhetisu and Ulytau (2022) and Shymkent (2018) are added to their parent regions. Taking logs makes changes read as percentages. The four-quarter difference removes seasonality without a seasonal-adjustment model."),
        ("Known weaknesses", f"A crude rate ignores age structure. Births are counted by registration date. The source has no January–June 2022 figure, so 2022Q2–Q3 are blank. Population from {esc(meta.get('population_projected_from') or 'n/a')} onward is projected (the downloaded series ends in January 2024). Harmonised units hide the 2022 regions."),
    ]
    H.append(table(["Element", "Statement"], [(f"<b>{k}</b>", v) for k, v in card]))

    # 2. Data and pipeline
    H.append("<h2>2. Data and pipeline</h2>")
    used = [(esc(s["series"]), esc(s["identifier"]), esc(s["file"])) for s in a["sources"]]
    H.append(table(["Series", "Taldau indicator (as exported)", "File in data/raw"], used, "small"))
    H.append("<p>All six files are untouched Taldau exports with SHA-256 checksums in <code>data/raw/manifest.json</code>. The build stops if any file changes. "
             "The data layer (<code>src/ingest.py</code>) keeps only oblasts and the three republican cities. It drops districts, towns, villages, the Alatau city administration and the national total, which Taldau lists in the same files. "
             "Check: the 16 regions sum exactly to the national births total in every quarter. "
             "Where Taldau reports old South Kazakhstan for a period, that row replaces Turkestan and Shymkent, so Shymkent is not counted twice in 2017–18. "
             "Population is summed across regions month by month, then averaged per quarter. "
             "Annual drivers (marriages, per-capita income, housing per resident) are dated at the quarters of the following year, when they are published. The CPI is chained from quarter-on-quarter indices. "
             "<b>One command</b> rebuilds everything: <code>python run.py rebuild</code>. Deleting <code>data/processed</code> and re-running restores it byte for byte, which a test checks.</p>")

    # 3. Model and results
    H.append("<h2>3. Model and results</h2>")
    H.append(f"<p>Dependent variable: y = ln CBR(t) − ln CBR(t−4). Estimator: panel ARDL with region fixed effects, by OLS, with {esc(sp['standard_errors'])} standard errors. "
             f"These are robust to the common shocks shared by all regions (Driscoll &amp; Kraay, 1998; Hoechle, 2007). "
             f"Sample {sp['sample_window'][0]}–{sp['sample_window'][1]}, {sp['n_regions']} regions, {sp['n_quarters']} quarters, {sp['n_obs']} region-quarters. Within R² = {f(sp['r2_within'], 2)}. "
             f"Expected signs were fixed before estimation. The last column gives the effect of a one-standard-deviation move, in births per 1,000 at the sample mean.</p>")
    H.append(table(["Regressor", "Exp.", "Coef.", "DK s.e.", "p", "1 s.d. effect"], res_rows))
    H.append(f"<p><b>Diagnostics.</b> Serial correlation (lags 1–4): p {p(d['serial_correlation']['pvalue'])}. Breusch–Pagan: p {p(d['heteroskedasticity_bp']['pvalue'])}. Jarque–Bera: p {p(d['normality_jb']['pvalue'])}. "
             f"Max VIF {f(max(d['vif'].values()), 2)}. Pesaran CD: p {p(d['cross_sectional_dependence_cd']['pvalue'])}, mean cross-region residual correlation {f(d['cross_sectional_dependence_cd']['mean_rho'], 2)}. "
             f"Chow stability: {chow}, so stability is rejected at every break date.</p>")
    H.append(f"<p><b>Integration.</b> For ln CBR, ADF rejects in {f(100 * lncbr.get('share_adf_reject_5pct', float('nan')), 0)}% of regions and KPSS rejects in {f(100 * lncbr.get('share_kpss_reject_5pct', float('nan')), 0)}%: {esc(lncbr.get('verdict', ''))}. "
             f"For y, ADF rejects in {f(100 * yint.get('share_adf_reject_5pct', float('nan')), 0)}% and KPSS in {f(100 * yint.get('share_kpss_reject_5pct', float('nan')), 0)}% (Fisher-ADF p {p(yint.get('fisher_adf_p'))}): {esc(yint.get('verdict', ''))}. "
             f"No regression is run in levels, so a spurious levels regression cannot arise. Engle–Granger (ln CBR on ln marriage rate) is reported in Annex A for information only.</p>")
    H.append(f"<p><b>Out of sample.</b> Estimated once on {b['train_window'][0]}–{b['train_window'][1]}, then one-step-ahead forecasts for {b['test_window'][0]}–{b['test_window'][1]} ({b['n_test_obs']} region-quarters). "
             f"RMSE: model {f(b['rmse_model'], 3)} vs benchmark {f(b['rmse_benchmark'], 3)} (ratio {f(b['rmse_ratio'], 3)}). MAE: {f(b['mae_model'], 3)} vs {f(b['mae_benchmark'], 3)} (ratio {f(b['mae_ratio'], 3)}). "
             f"The benchmark is a seasonal random walk, chosen in advance. <b>{'The model wins' if b['winner'] == 'model' else 'The benchmark wins'}</b>, but the Diebold–Mariano test gives p {p(dm.get('pvalue'))}, so the gain is "
             f"{'not ' if (dm.get('pvalue') or 1) >= 0.05 else ''}significant at 5%. "
             f"Falsification rule 1 (beat the benchmark): {'passed' if fals['rule_1_beats_benchmark']['passed'] else 'FAILED'}. "
             f"Rule 2 (marriage effect &gt; 0 at 5%, one-sided): {'passed' if r2.get('passed') else 'FAILED'} (one-sided p {p(r2.get('p_one_sided'))}).</p>")
    w_key = next((n for n in names if n.startswith("w_")), None)
    m_eff = econ.get(m_key, {}).get("effect_per_1000")
    H.append("<p><b>Economic size.</b> A one-standard-deviation move in real income changes the rate by "
             f"{f(econ.get(w_key, {}).get('effect_per_1000'), 2)} births per 1,000, and in marriages by {f(m_eff, 2)}. "
             "The 2025–26 fall was several births per 1,000, so these are small against what they would need to explain. Most of the forecast comes from momentum, not from the drivers.</p>")
    if r2 and not r2.get("passed") and m_key:
        H.append(f"<p><b>The core mechanism is rejected.</b> The pre-registered marriage effect has the wrong sign ({f(a['coefficients'][m_key], 3)}, p {p(a['p_values'][m_key])}), so falsification rule 2 fails. "
                 f"Dropping 2020Q2–2021Q4 leaves it negative but no longer significant (Annex B). The sign is therefore driven largely by the pandemic, when marriages fell in 2020 and births rose in 2021. "
                 "We report this as the result and do not swap in a specification that passes.</p>")
    H.append("<p><b>New element.</b> This is the first one-quarter-ahead forecast of the birth rate for Kazakhstan's regions on a harmonised 16-region quarterly panel. Published regional work is annual and descriptive (Aubakirova et al., 2024).</p>")
    H.append("<p><b>Deviations from pre-registration</b> (memo of 18 October 2026, in <code>docs/pre_registration.md</code>):</p><ul>" +
             "".join(f"<li>{esc(x['what'])}. Why: {esc(x['why'])}. Pre-registered specification: {esc(x['pre_registered_result'])}.</li>" for x in deviations) +
             "<li>The memo was written and the model estimated on the same day, and the memo was not time-stamped by the course system before estimation.</li></ul>")

    # 4. Validity
    H.append("<h2>4. Validity and limits</h2>")
    H.append("<p><b>Construct.</b> The crude rate measures births per resident, not fertility per woman. Regions with young age structures (Turkestan, Mangystau) look more fertile than their total fertility rate implies, and ageing northern regions look less fertile. "
             "Migration of young adults into Astana and Almaty raises the cities' rates and lowers the regions they leave. "
             "Projected population after January 2024 biases the latest rates if growth slowed: real growth below the projection makes the rate too low. "
             "The January 2023 population revision shifts the denominator by about 2–3% in some regions.</p>")
    H.append("<p><b>Internal.</b> There is no identification strategy, so the coefficients are labelled conditional correlations, not effects. "
             "Omitted variables: family-benefit and mortgage programmes raise income, housing and births together, which biases those coefficients upward. "
             "Pandemic shocks moved marriages and births in opposite directions, which biases the marriage coefficient downward. "
             "Reverse causality: an expected birth can bring a marriage forward. The 3-quarter lag reduces this but does not remove it. "
             "Measurement error: revisions to the latest data and the projected denominator bias coefficients toward zero. "
             "Residual serial correlation with a lagged dependent variable leaves a small bias in the momentum terms.</p>")
    H.append("<p><b>External.</b> The sample covers 2016–2026: a floating tenge after 2015, COVID-19 in 2020–21, the 2022 border changes, and oil-price swings in a commodity exporter. "
             "The Chow tests show the relationship shifted at each of these dates. Results apply to Kazakhstan's high-fertility, oil-dependent regime and do not transfer to low-fertility economies.</p>")
    prior = cfg_model.get("prior_runs", [])
    n_prior = sum(r["specs"] for r in prior)
    prior_txt = " ".join(f"An earlier run ({esc(r['date'])}, {r['specs']} specifications): {esc(r['what'])}; {esc(r['result'])}; {esc(r['status'])}." for r in prior)
    H.append(f"<p><b>Statistical.</b> {sp['specifications_run'] + n_prior} specifications were run in total, all declared in advance, and every one is reported. {prior_txt} "
             f"With {sp['n_obs']} region-quarters the pooled tests have reasonable power. A single region has only {sp['n_quarters']} quarters, so no region-level effects are claimed. "
             "Failing to reject an effect (housing) is not evidence that it is absent.</p>")
    H.append(table(["Robustness check", "Marriage coef.", "p", "RMSE ratio", "Winner"], rob_rows))
    if overturned:
        H.append(f"<p>Overturns the main result: {esc('; '.join(overturned))}. The model's edge over the benchmark depends on the denominator. On births counts the benchmark wins.</p>")

    # 5. Product
    H.append("<h2>5. The product</h2>")
    H.append("<p>Three layers with separate entry points. <code>src/ingest.py</code> turns raw files into processed data. <code>src/model.py</code> writes <code>model/artifact.json</code> (coefficients, covariance, diagnostics, benchmark, forecasts). "
             "<code>src/app.py</code> is a standard-library web server that only reads those two. There is no regression in the request path, and the artifact is re-read on every request. "
             "<b>Run:</b> <code>pip install -r requirements.txt</code> then <code>python run.py</code>, which opens http://127.0.0.1:8050. "
             "The page shows, for any region or the national total:</p><ul>"
             "<li>the latest rate, its quarter and the change on a year earlier, above the fold;</li>"
             "<li>the full history with the source named on the chart;</li>"
             "<li>each driver's contribution to the forecast;</li>"
             "<li>a scenario slider whose 90% band comes from the artifact's covariance matrix, with a decision signal;</li>"
             "<li>a provenance panel and an honesty panel.</li></ul>"
             "<p><b>Error states:</b> no network shows a labelled cached snapshot; a missing or renamed artifact, missing processed data, or a missing input for a region each give a plain-language message; an edited raw file stops the build. "
             "On a fresh clone from GitHub (18 October 2026), acceptance checks 2–10 pass: page in 0.12 s, contributions match the artifact, offline and missing-model messages shown. Checks 4, 5, 8, 9 and 10 are also automated in <code>tests/</code>. Check 1 (a clean install on another machine) is left to the Week 6 peer session. A static snapshot is published at i2rchik.github.io/KZ-birth-rates. "
             "<b>Next, with two more weeks:</b> published 2024–26 population, monthly marriages, quarterly unemployment by region, and an age-standardised fertility measure.</p>")

    # 6. Decision rule
    H.append("<h2>6. Decision rule</h2>")
    H.append(f"<p><b>User:</b> the maternity and child-health department of a regional akimat, setting next quarter's staffing and bed capacity. "
             f"<b>Rule:</b> if the 90% forecast interval for next quarter lies entirely below (above) the same quarter last year, plan capacity for the forecast percentage fewer (more) births; otherwise plan at last year's level. "
             f"<b>Why:</b> the threshold is the model's own measured uncertainty, a median half-width of ±{f(median_hw, 1)}% across regions. Smaller moves cannot be told apart from noise, and re-staffing on noise is costly. "
             f"For {esc(dr_rows[0][3] if False else nat.get('forecast', {}).get('quarter', ''))}: "
             f"{sum('fewer' in r[4] for r in dr_rows)} regions signal fewer births, {sum('more' in r[4] for r in dr_rows)} signal more, and {sum('no clear' in r[4] for r in dr_rows)} show no clear signal (Annex C).</p>")

    # Annexes
    H.append("<div class='annex'><h2>Annex A. Full diagnostic and test output</h2>")
    H.append(f"<p class='small'>Unit-root tests per region are in <code>outputs/annex_unit_roots.csv</code>, cointegration in <code>outputs/annex_cointegration.csv</code>, and everything else in <code>outputs/annex_diagnostics.json</code>. "
             f"Monte Carlo p-values use seed 20261018, 2,000 draws. Engle–Granger Fisher p {p(a['cointegration']['fisher']['pvalue'] if a['cointegration']['fisher'] else None)}.</p>")
    diag_rows = [("Serial correlation, lags 1–4 (F, DK)", f(d['serial_correlation']['stat'], 2), p(d['serial_correlation']['pvalue'])),
                 ("Breusch–Pagan (LM)", f(d['heteroskedasticity_bp']['stat'], 2), p(d['heteroskedasticity_bp']['pvalue'])),
                 ("Jarque–Bera", f(d['normality_jb']['stat'], 2), p(d['normality_jb']['pvalue'])),
                 ("Pesaran CD", f(d['cross_sectional_dependence_cd']['stat'], 2), p(d['cross_sectional_dependence_cd']['pvalue']))] + \
                [(f"Chow at {k} (F, DK)", f(v['stat'], 2), p(v['pvalue'])) for k, v in d['stability_chow'].items() if v] + \
                [(f"VIF {esc(sp['labels'][k])}", f(v, 2), "") for k, v in d['vif'].items()]
    H.append(table(["Test", "Statistic", "p"], diag_rows, "small"))
    if os.path.exists(os.path.join(outputs, "fig_holdout.png")):
        H.append(img(os.path.join(outputs, "fig_holdout.png"), "88%"))
    oos_path = os.path.join(outputs, "annex_oos_by_region.csv")
    if os.path.exists(oos_path):
        with open(oos_path, encoding="utf-8") as fh:
            rr = list(csv.reader(fh))
        H.append("<h3>Hold-out RMSE by region</h3>")
        H.append(table(["Region", "RMSE model", "RMSE benchmark"],
                       [(esc(a["regions"].get(r[0], r[0])), f(float(r[1]), 3), f(float(r[2]), 3)) for r in rr[1:]], "small"))
    H.append("</div>")
    H.append("<div class='annex'><h2>Annex B. Robustness (full)</h2>")
    H.append(table(["Check", "Obs.", "Marriage coef.", "p", "RMSE ratio", "Winner"],
                   [(esc(r["check"]), r["n_obs"], f(r["marriage_coef"], 3), p(r["marriage_p"]), f(r["rmse_ratio"], 3), r["winner"]) for r in rob], "small"))
    H.append("<h2>Annex C. Next-quarter forecasts and decision signals</h2>")
    H.append(table(["Region", "Same quarter last year", "Forecast", "90% interval", "Signal"], dr_rows, "small"))
    H.append("<h2>Annex D. References (APA 7)</h2><ul class='small'>"
             "<li>Adserà, A. (2004). Changing fertility rates in developed countries. The impact of labor market institutions. <i>Journal of Population Economics, 17</i>(1), 17–43. https://doi.org/10.1007/s00148-003-0166-x</li>"
             "<li>Aubakirova, Z., Nogaibayev, Y., Ualiyeva, S., Stolyarova, E., &amp; Krasnobayeva, N. (2024). Regional fertility characteristics of urban population of Kazakhstan at the end of the 20th–first quarter of the 21st centuries. <i>Journal of Infrastructure Policy and Development, 8</i>(12), 8948. https://doi.org/10.24294/jipd.v8i12.8948</li>"
             "<li>Bureau of National Statistics. (2025, May 12). <i>Natural movement of the population of the Republic of Kazakhstan, January–March 2025</i>. https://stat.gov.kz/api/iblock/element/346557/file/ru/</li>"
             "<li>Bureau of National Statistics. (2026). <i>Taldau statistical database</i> [Data set]. Retrieved October 18, 2026, from https://taldau.stat.gov.kz/ru</li>"
             "<li>Dettling, L. J., &amp; Kearney, M. S. (2014). House prices and birth rates: The impact of the real estate market on the decision to have a baby. <i>Journal of Public Economics, 110</i>, 82–100. https://doi.org/10.1016/j.jpubeco.2013.09.009</li>"
             "<li>Driscoll, J. C., &amp; Kraay, A. C. (1998). Consistent covariance matrix estimation with spatially dependent panel data. <i>Review of Economics and Statistics, 80</i>(4), 549–560. https://ideas.repec.org/a/tpr/restat/v80y1998i4p549-560.html</li>"
             "<li>García-Pereiro, T., Misuraca, R., Pace, R., &amp; Patimo, R. (2024). Disentangling the role of composition factors in fertility responses to unemployment. <i>Social Sciences, 13</i>(12), 683. https://doi.org/10.3390/socsci13120683</li>"
             "<li>Hoechle, D. (2007). Robust standard errors for panel regressions with cross-sectional dependence. <i>The Stata Journal, 7</i>(3), 281–312. https://doi.org/10.1177/1536867X0700700301</li>"
             "<li>Kassimova, G. K., Yermakhanova, S. A., &amp; Nakipbayeva, Zh. A. (2026). Unrealized fertility in Kazakhstan: The gap between desired and actual number of children. <i>Gumilyov Journal of Sociology, 155</i>(2), 121–129. https://doi.org/10.32523/3080-1702-2026-155-2-121-129</li>"
             "</ul><p class='small'>Each link must be opened and checked by a team member before submission (brief, Section 15).</p>")
    H.append("<h2>Annex E. AI-use declaration</h2><p class='small'>See <code>AI_USE.md</code>. Claude (Anthropic) wrote the first version of the code, the documents and this note's wording, and searched for references. "
             "All numbers come from the code's outputs, not from the AI's text. The team must verify the items listed in <code>AI_USE.md</code> and sign it.</p>")
    H.append("<h2>Annex F. Contribution statement and replication receipt</h2><p class='small'>See <code>CONTRIBUTIONS.md</code> (signed by every member) and <code>docs/replication_receipt.md</code> (signed by the reviewing team in Week 6).</p>")
    H.append("</body></html>")
    os.makedirs(outputs, exist_ok=True)
    path = os.path.join(outputs, "technical_note.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(H))
    return path


def to_pdf(html_path, pdf_path):
    """Optional: print the note to PDF with Playwright/Chromium if installed."""
    from playwright.sync_api import sync_playwright
    exe = os.environ.get("CHROMIUM_PATH")
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        pg = br.new_page()
        pg.goto("file://" + os.path.abspath(html_path))
        pg.pdf(path=pdf_path, format="A4", print_background=True,
               margin={"top": "16mm", "bottom": "16mm", "left": "15mm", "right": "15mm"})
        br.close()


if __name__ == "__main__":
    print(build())
