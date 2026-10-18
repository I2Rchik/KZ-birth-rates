"""Writes outputs/note_numbers.md: every number used in the technical note,
generated from model/artifact.json so nothing is retyped by hand.
Run automatically by `python run.py rebuild`."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _f(v, d=3):
    return "n/a" if v is None else f"{v:.{d}f}"


def write(model_dir=None, outputs=None):
    model_dir = model_dir or os.path.join(ROOT, "model")
    outputs = outputs or os.path.join(ROOT, "outputs")
    with open(os.path.join(model_dir, "artifact.json"), encoding="utf-8") as f:
        a = json.load(f)
    sp, b, fl = a["specification"], a["benchmark"], a["diagnostic_flags"]
    L = []
    if a["synthetic_data"]:
        L.append("> **SYNTHETIC TEST DATA - these numbers do not describe Kazakhstan. Do not submit.**\n")
    L.append("## Section 3 numbers (generated)\n")
    L.append(f"Sample: {sp['sample_window'][0]}-{sp['sample_window'][1]}, {sp['n_regions']} regions, "
             f"{sp['n_quarters']} quarters, {sp['n_obs']} region-quarters. Within R2 = {_f(sp['r2_within'])}. "
             f"Specifications run: {sp['specifications_run']}.\n")
    L.append("| Regressor | Expected sign | Coefficient | Driscoll-Kraay SE | p-value |")
    L.append("| --- | --- | --- | --- | --- |")
    for n in sp["regressors"]:
        L.append(f"| {sp['labels'][n]} | {sp['expected_signs'].get(n, '')} | {_f(a['coefficients'][n])} | "
                 f"{_f(a['std_errors'][n])} | {_f(a['p_values'][n])} |")
    d = a["diagnostics"]
    L.append("\n**Diagnostics (3 lines).**")
    L.append(f"Serial correlation (lags 1-4) p = {_f(d['serial_correlation']['pvalue'])}; "
             f"Breusch-Pagan p = {_f(d['heteroskedasticity_bp']['pvalue'])}; "
             f"Jarque-Bera p = {_f(d['normality_jb']['pvalue'])}.")
    L.append(f"Max VIF = {_f(max(d['vif'].values()), 2)}; Pesaran CD p = {_f(d['cross_sectional_dependence_cd']['pvalue'])} "
             f"(mean cross-region residual correlation {_f(d['cross_sectional_dependence_cd']['mean_rho'])}).")
    chow = "; ".join(f"{k}: p = {_f(v['pvalue'])}" for k, v in d["stability_chow"].items() if v)
    L.append(f"Chow stability tests - {chow}.\n")
    L.append("**Out of sample.**")
    L.append(f"Hold-out {b['test_window'][0]}-{b['test_window'][1]} ({b['n_test_quarters']} quarters, {b['n_test_obs']} forecasts). "
             f"RMSE model {_f(b['rmse_model'])} vs benchmark {_f(b['rmse_benchmark'])} (ratio {_f(b['rmse_ratio'])}); "
             f"MAE {_f(b['mae_model'])} vs {_f(b['mae_benchmark'])} (ratio {_f(b['mae_ratio'])}). "
             f"Winner on RMSE: **{b['winner']}**. Diebold-Mariano p = {_f((b.get('diebold_mariano') or {}).get('pvalue'))}.\n")
    f2 = a["falsification"]["rule_2_marriage_positive_5pct"]
    L.append(f"Falsification rule 1 (beat benchmark): {'passed' if a['falsification']['rule_1_beats_benchmark']['passed'] else 'FAILED'}. "
             f"Rule 2 (marriage > 0 at 5%, one-sided): {'n/a' if not f2 else ('passed' if f2['passed'] else 'FAILED')}.\n")
    L.append("**Integration.**")
    for s, v in a["integration"].items():
        if "fisher_adf_p" not in v:
            L.append(f"- {s}: {v['verdict']}.")
            continue
        L.append(f"- {s}: Fisher-ADF p = {_f(v['fisher_adf_p'])}, ADF rejects in {100 * v['share_adf_reject_5pct']:.0f}% "
                 f"and KPSS rejects in {100 * v['share_kpss_reject_5pct']:.0f}% of regions -> {v['verdict']}.")
    cf = a["cointegration"]["fisher"]
    if cf:
        L.append(f"- Engle-Granger (ln CBR on ln marriage rate), Fisher p = {_f(cf['pvalue'])}. Not needed for validity: no levels regression is run.\n")
    L.append("**Economic size (one-standard-deviation move, births per 1,000 at the sample mean).**")
    for n, v in a["economic_size"].items():
        L.append(f"- {sp['labels'][n]}: {_f(v['effect_per_1000'], 3)}")
    L.append("\n## Robustness (Section 4 table)\n")
    L.append("| Check | Marriage coef | p | RMSE ratio | Winner |")
    L.append("| --- | --- | --- | --- | --- |")
    for r in a["robustness"]:
        L.append(f"| {r['check']} | {_f(r['marriage_coef'])} | {_f(r['marriage_p'])} | {_f(r['rmse_ratio'])} | {r['winner']} |")
    L.append("\n## Deviations from pre-registration\n")
    L.extend([f"- {x['what']}: {x['why']}; pre-registered result: {x['pre_registered_result']}."
              for x in a["deviations_from_preregistration"]] or ["- None generated automatically. Add any manual change here."])
    nat = a["national"]
    L.append(f"\n## Headline\n\nKazakhstan {nat['latest']['quarter']}: {_f(nat['latest']['value'], 2)} births per 1,000 (annualised).")
    if nat.get("forecast"):
        L.append(f"Forecast {nat['forecast']['quarter']}: {_f(nat['forecast']['value'], 2)}. "
                 f"Replication tolerance: +/-{a['replication_tolerance_per_1000']} per 1,000.")
    os.makedirs(outputs, exist_ok=True)
    with open(os.path.join(outputs, "note_numbers.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    write()
