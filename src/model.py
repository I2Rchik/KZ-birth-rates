"""Model layer: estimate the pre-registered panel ARDL, test it, evaluate it
out of sample, and serialise everything the website shows into
model/artifact.json. Also writes every table and figure for the note to outputs/.

Run:  python run.py model
"""
import datetime as dt
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import econometrics as ec  # noqa: E402
from regions import REGIONS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def qlabel(t):
    return f"{t // 4}Q{t % 4 + 1}"


def qindex(label):
    return int(label[:4]) * 4 + int(label[-1]) - 1


# ------------------------------------------------------------- design
def add_lags(panel, spec):
    """Add y_lag{k} and driver lags within each region (panel is a full grid)."""
    p = panel.sort_values(["code", "t"]).copy()
    g = p.groupby("code")
    dep = spec["dep"]
    for k in spec["own_lags"]:
        p[f"{dep}_l{k}"] = g[dep].shift(k)
    for d in spec["drivers"]:
        p[f"{d['name']}_l{d['lag']}"] = g[d["name"]].shift(d["lag"])
    return p


def regressor_names(spec):
    return [f"{spec['dep']}_l{k}" for k in spec["own_lags"]] + \
           [f"{d['name']}_l{d['lag']}" for d in spec["drivers"]]


def design(p, spec, t_min=None, t_max=None, exclude=None):
    names = regressor_names(spec)
    d = p.dropna(subset=[spec["dep"]] + names)
    if t_min is not None:
        d = d[d.t >= t_min]
    if t_max is not None:
        d = d[d.t <= t_max]
    if exclude is not None:
        d = d[~d.t.between(*exclude)]
    return d, names


def fit(d, names, dep):
    X = d[names].to_numpy(float)
    y = d[dep].to_numpy(float)
    return ec.panel_fe(X, y, d["code"].to_numpy(), d["t"].to_numpy(), names)


def predict(res, rows, names):
    X = rows[names].to_numpy(float)
    a = rows["code"].map(res["alpha"]).to_numpy(float)
    return a + X @ res["beta"]


# --------------------------------------------------------- evaluation
def out_of_sample(p, spec, holdout_share, exclude=None):
    """Estimate once on the first (1-h) share of quarters, then forecast each
    hold-out quarter one step ahead with data available at the time.
    Forecasts are compared in births per 1,000 (annualised)."""
    full, names = design(p, spec)
    ts = np.sort(full.t.unique())
    n_hold = max(1, int(math.ceil(holdout_share * len(ts))))
    cut = ts[-n_hold - 1]
    train, _ = design(p, spec, t_max=cut, exclude=exclude)
    res = fit(train, names, spec["dep"])
    test = full[full.t > cut].copy()
    level = spec["level"]
    test["yhat"] = predict(res, test, names)
    base = p.set_index(["code", "t"])[level]
    test["base_level"] = [base.get((c, t - 4), np.nan) for c, t in zip(test.code, test.t)]
    test = test.dropna(subset=["base_level", level])
    test["f_model"] = test["base_level"] * np.exp(test["yhat"])
    test["f_bench"] = test["base_level"]  # seasonal random walk: same quarter last year
    e_m = test[level] - test["f_model"]
    e_b = test[level] - test["f_bench"]
    rm, rb = float(np.sqrt((e_m ** 2).mean())), float(np.sqrt((e_b ** 2).mean()))
    mm, mb = float(e_m.abs().mean()), float(e_b.abs().mean())
    dm = ec.diebold_mariano(e_m.to_numpy(), e_b.to_numpy(), test.t.to_numpy())
    by_region = test.assign(e_m=e_m, e_b=e_b).groupby("code").apply(
        lambda g: pd.Series({"rmse_model": np.sqrt((g.e_m ** 2).mean()),
                             "rmse_benchmark": np.sqrt((g.e_b ** 2).mean())}), include_groups=False)
    return {
        "train_window": [qlabel(int(train.t.min())), qlabel(int(cut))],
        "test_window": [qlabel(int(test.t.min())), qlabel(int(test.t.max()))],
        "n_test_obs": int(len(test)), "n_test_quarters": int(test.t.nunique()),
        "rmse_model": rm, "rmse_benchmark": rb, "rmse_ratio": rm / rb if rb else None,
        "mae_model": mm, "mae_benchmark": mb, "mae_ratio": mm / mb if mb else None,
        "winner": "model" if rm < rb else "benchmark",
        "diebold_mariano": dm, "train_result": res,
        "test_rows": test[["code", "t", level, "f_model", "f_bench"]],
        "by_region": by_region,
    }


def integration_tests(p, rng):
    rows = []
    series = {"ln_cbr": np.log(p["cbr"]), "y": p["y"], "m": p.get("m"), "w": p.get("w"),
              "u": p.get("u"), "h": p.get("h")}
    summary = {}
    for name, s in series.items():
        if s is None or s.isna().all():
            continue
        if s.groupby(p.code).nunique().median() < 20:
            summary[name] = {"verdict": "not tested: annual series repeated over 4 quarters "
                                        "(about 10 values per region, too few for ADF/KPSS)"}
            continue
        adf_p, kpss_p = [], []
        for code in sorted(REGIONS):
            z = s[p.code == code].to_numpy(float)
            a, k = ec.adf(z, rng=rng), ec.kpss(z, rng=rng)
            if a is None or k is None:
                continue
            adf_p.append(a["pvalue"])
            kpss_p.append(k["pvalue"])
            rows.append({"series": name, "region": code, "adf_stat": a["stat"], "adf_lags": a["lags"],
                         "adf_p": a["pvalue"], "kpss_stat": k["stat"], "kpss_p": k["pvalue"], "n": a["n"]})
        if adf_p:
            fisher = ec.fisher_panel(adf_p)
            summary[name] = {
                "fisher_adf_p": fisher["pvalue"],
                "share_adf_reject_5pct": float(np.mean(np.array(adf_p) < 0.05)),
                "share_kpss_reject_5pct": float(np.mean(np.array(kpss_p) < 0.05)),
                "verdict": verdict(fisher["pvalue"], np.mean(np.array(kpss_p) < 0.05)),
            }
    return pd.DataFrame(rows), summary


def verdict(fisher_p, kpss_reject_share):
    if fisher_p < 0.05 and kpss_reject_share <= 0.5:
        return "stationary (both tests agree)"
    if fisher_p >= 0.05 and kpss_reject_share > 0.5:
        return "unit root (both tests agree)"
    return "inconclusive (tests disagree)"


def cointegration(p, rng):
    rows = []
    for code in sorted(REGIONS):
        g = p[p.code == code]
        r = ec.engle_granger(np.log(g["cbr"]).to_numpy(float), np.log(g["marriage_rate"]).to_numpy(float), rng=rng)
        if r:
            rows.append({"region": code, "eg_stat": r["stat"], "eg_p": r["pvalue"], "n": r["n"]})
    df = pd.DataFrame(rows)
    fisher = ec.fisher_panel(df["eg_p"].tolist()) if len(df) else None
    return df, fisher


# ------------------------------------------------------------ forecast
def forecast_next(p, res, spec, names):
    """One-quarter-ahead forecast for every region from the latest data,
    with each term's contribution and the vectors the app needs for the
    scenario band (no estimation happens in the app)."""
    dep, level = spec["dep"], spec["level"]
    last_t = int(p.dropna(subset=[level]).t.max())
    t_next = last_t + 1
    idx = p.set_index(["code", "t"])
    est, _ = design(p, spec)
    out = {}
    for code in sorted(REGIONS):
        row, why = {}, []
        for nm in names:
            base, k = nm.rsplit("_l", 1)
            v = idx[base].get((code, t_next - int(k)), np.nan)
            row[nm] = v
            if v != v:
                why.append(f"{base} for {qlabel(t_next - int(k))}")
        base_level = idx[level].get((code, t_next - 4), np.nan)
        if base_level != base_level:
            why.append(f"{level} for {qlabel(t_next - 4)}")
        if why or code not in res["alpha"]:
            out[code] = {"available": False, "missing": why or ["region not in estimation sample"]}
            continue
        x = np.array([row[n] for n in names], float)
        contrib = dict(zip(names, (x * res["beta"]).tolist()))
        yhat = res["alpha"][code] + float(x @ res["beta"])
        xbar = est[est.code == code][names].to_numpy(float).mean(axis=0)
        Ti = int((est.code == code).sum())
        out[code] = {
            "available": True, "quarter": qlabel(t_next), "yhat": yhat,
            "region_effect": res["alpha"][code], "contributions": contrib,
            "x": x.tolist(), "x_dev": (x - xbar).tolist(), "T_i": Ti,
            "base_quarter": qlabel(t_next - 4), "base_level": float(base_level),
            "forecast_level": float(base_level * math.exp(yhat)),
        }
    return out, last_t


def latest_values(p, level):
    out = {}
    for code in sorted(REGIONS):
        g = p[(p.code == code)].dropna(subset=[level]).set_index("t")
        if g.empty:
            continue
        t = int(g.index.max())
        prev = g[level].get(t - 4, np.nan)
        out[code] = {"quarter": qlabel(t), "value": float(g[level][t]),
                     "same_quarter_last_year": None if prev != prev else float(prev),
                     "change": None if prev != prev else float(g[level][t] - prev),
                     "population": float(g["population"][t]), "births": float(g["births"][t]),
                     "population_projected": bool(g["pop_extrapolated"][t]) if "pop_extrapolated" in g else False}
    return out


def national(p, fc, latest):
    """Kazakhstan = sum of the 16 harmonised regions (births / population)."""
    g = p.dropna(subset=["births", "population"]).groupby("t")[["births", "population"]].sum(min_count=16)
    g = g.dropna()
    g = g[p.dropna(subset=["births"]).groupby("t").code.nunique().reindex(g.index) == 16]
    cbr = 4000 * g.births / g.population
    t = int(cbr.index.max())
    res = {"history": [[qlabel(int(k)), float(v)] for k, v in cbr.items()],
           "latest": {"quarter": qlabel(t), "value": float(cbr[t]),
                      "change": float(cbr[t] - cbr[t - 4]) if t - 4 in cbr.index else None}}
    if all(fc[c]["available"] for c in REGIONS):
        births_f = sum(fc[c]["forecast_level"] * latest[c]["population"] / 4000 for c in REGIONS)
        births_b = sum(fc[c]["base_level"] * latest[c]["population"] / 4000 for c in REGIONS)
        pop = sum(latest[c]["population"] for c in REGIONS)
        w = {c: fc[c]["base_level"] * latest[c]["population"] / 4000 / births_b for c in REGIONS}
        names = list(fc["AKM"]["contributions"])
        res["forecast"] = {
            "quarter": fc["AKM"]["quarter"], "value": 4000 * births_f / pop,
            "base_quarter": fc["AKM"]["base_quarter"], "base_level": 4000 * births_b / pop,
            "contributions": {n: sum(w[c] * fc[c]["contributions"][n] for c in REGIONS) for n in names},
            "region_effect": sum(w[c] * fc[c]["region_effect"] for c in REGIONS),
            "note": "Sum of the 16 regional forecasts; population held at its latest quarterly value; "
                    "contributions are birth-weighted averages of the regional ones."}
    return res


# ---------------------------------------------------------------- run
def run(processed=None, model_dir=None, outputs=None, make_figures=True):
    processed = processed or os.path.join(ROOT, "data", "processed")
    model_dir = model_dir or os.path.join(ROOT, "model")
    outputs = outputs or os.path.join(ROOT, "outputs")
    with open(os.path.join(ROOT, "src", "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)["model"]
    with open(os.path.join(processed, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    panel = pd.read_csv(os.path.join(processed, "panel.csv"))
    rng = np.random.default_rng(cfg["seed"])

    deviations = list(cfg.get("deviations", []))
    drivers = []
    for d in cfg["drivers"]:
        if d["name"] in panel and panel[d["name"]].notna().sum() > 0:
            drivers.append(d)
        else:
            deviations.append({"what": f"Driver '{d['label']}' dropped",
                               "why": "series not available in data/raw",
                               "pre_registered_result": "not estimable"})
    spec = {"dep": "y", "level": "cbr", "own_lags": cfg["own_lags"], "drivers": drivers}
    p = add_lags(panel, spec)
    d, names = design(p, spec)
    res = fit(d, names, "y")

    # ---- tests
    ur, ur_summary = integration_tests(panel, rng)
    coint, coint_fisher = cointegration(panel, rng)
    g, tt = d["code"].to_numpy(), d["t"].to_numpy()
    X, y = d[names].to_numpy(float), d["y"].to_numpy(float)
    diag = {
        "serial_correlation": ec.serial_correlation(res, g, tt),
        "heteroskedasticity_bp": ec.breusch_pagan(res),
        "normality_jb": ec.jarque_bera(res),
        "vif": ec.vif(res["Xd"], names),
        "cross_sectional_dependence_cd": ec.pesaran_cd(res["resid"], g, tt),
        "stability_chow": {b: ec.chow(X, y, g, tt, names, qindex(b)) for b in cfg["breaks"]},
    }
    flags = {
        "serial_correlation": diag["serial_correlation"]["pvalue"] < 0.05,
        "heteroskedasticity": diag["heteroskedasticity_bp"]["pvalue"] < 0.05,
        "non_normal_residuals": diag["normality_jb"]["pvalue"] < 0.05,
        "high_multicollinearity": max(diag["vif"].values()) > 10,
        "cross_sectional_dependence": diag["cross_sectional_dependence_cd"]["pvalue"] < 0.05,
        "unstable_at": [b for b, r in diag["stability_chow"].items() if r and r["pvalue"] < 0.05],
    }

    # ---- out of sample + robustness (all pre-declared)
    oos = out_of_sample(p, spec, cfg["holdout_share"])
    rob = []
    mkey = next((f"{d_['name']}_l{d_['lag']}" for d_ in drivers if d_["name"] == "m"), None)
    cov_w = (qindex(cfg["covid_window"][0]), qindex(cfg["covid_window"][1]))
    variants = [
        ("Main specification", spec, None, p),
        ("Alt. sample: drop 2020Q2-2021Q4", spec, cov_w, p),
        ("Alt. specification: no lagged dependent variable", dict(spec, own_lags=[]), None, None),
        ("Alt. measure: births count instead of rate", dict(spec, dep="y_births", level="births"), None, None),
    ]
    for label, sp, excl, pp in variants:
        pp = pp if pp is not None else add_lags(panel, sp)
        dd, nn = design(pp, sp, exclude=excl)
        r = fit(dd, nn, sp["dep"])
        o = out_of_sample(pp, sp, cfg["holdout_share"], exclude=excl)
        j = nn.index(mkey) if mkey in nn else None
        rob.append({"check": label, "n_obs": r["n"],
                    "marriage_coef": None if j is None else float(r["beta"][j]),
                    "marriage_p": None if j is None else float(r["p"][j]),
                    "rmse_ratio": o["rmse_ratio"], "winner": o["winner"]})

    # ---- pre-registered falsification
    jm = names.index(mkey) if mkey in names else None
    falsification = {
        "rule_1_beats_benchmark": {"rmse_ratio": oos["rmse_ratio"], "passed": oos["rmse_ratio"] < 1},
        "rule_2_marriage_positive_5pct": None if jm is None else {
            "coef": float(res["beta"][jm]), "p_one_sided": float(res["p"][jm] / 2 if res["beta"][jm] > 0
                                                                  else 1 - res["p"][jm] / 2),
            "test": "one-sided t-test, H1: coefficient > 0 (Driscoll-Kraay)",
            "passed": bool(res["beta"][jm] > 0 and res["p"][jm] / 2 < 0.05)},
    }

    # ---- economic size: effect of a one-standard-deviation move in each regressor
    mean_cbr = float(panel["cbr"].mean())
    econ = {}
    for j, nm in enumerate(names):
        sd = float(d[nm].std())
        econ[nm] = {"sd": sd, "effect_log": float(res["beta"][j] * sd),
                    "effect_per_1000": float(mean_cbr * (math.exp(res["beta"][j] * sd) - 1))}

    fc, last_t = forecast_next(p, res, spec, names)
    latest = latest_values(panel, "cbr")
    nat = national(panel, fc, latest)
    history = {c: [[q, float(v)] for q, v in panel[panel.code == c].dropna(subset=["cbr"])[["quarter", "cbr"]].values]
               for c in sorted(REGIONS)}

    labels = {f"y_l{k}": f"Own momentum (lag {k})" for k in spec["own_lags"]}
    labels.update({f"{d_['name']}_l{d_['lag']}": d_["label"] + f", lag {d_['lag']}" for d_ in drivers})
    signs = {f"{d_['name']}_l{d_['lag']}": d_["expected_sign"] for d_ in drivers}

    artifact = {
        "schema": "kz-regional-birth-rate/1",
        "indicator": "Crude birth rate, live births per 1,000 population, annualised, quarterly",
        "estimated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "synthetic_data": bool(meta.get("synthetic")),
        "data_warnings": meta.get("warnings", []),
        "population_projected_from": meta.get("population_projected_from"),
        "sources": meta["sources"],
        "regions": REGIONS,
        "specification": {
            "dependent": "y = ln CBR(t) - ln CBR(t-4)", "estimator": "Panel ARDL, region fixed effects, OLS",
            "standard_errors": f"Driscoll-Kraay, Bartlett kernel, {ec.nw_lags(res['T'])} lags",
            "regressors": names, "labels": labels, "expected_signs": signs,
            "sample_window": [qlabel(int(d.t.min())), qlabel(int(d.t.max()))],
            "n_obs": res["n"], "n_regions": res["n_groups"], "n_quarters": res["T"],
            "r2_within": res["r2_within"], "specifications_run": len(variants),
        },
        "coefficients": dict(zip(names, res["beta"].tolist())),
        "std_errors": dict(zip(names, res["se"].tolist())),
        "p_values": dict(zip(names, res["p"].tolist())),
        "covariance": res["cov"].tolist(),
        "residual_variance": res["sigma2"],
        "region_effects": res["alpha"],
        "diagnostics": diag, "diagnostic_flags": flags,
        "integration": ur_summary,
        "cointegration": {"test": "Engle-Granger, ln CBR on ln marriage rate, per region",
                          "fisher": coint_fisher},
        "benchmark": {"name": "Seasonal random walk: CBR(t+1) = CBR(t-3)",
                      **{k: oos[k] for k in ("train_window", "test_window", "n_test_obs", "n_test_quarters",
                                             "rmse_model", "rmse_benchmark", "rmse_ratio", "mae_model",
                                             "mae_benchmark", "mae_ratio", "winner", "diebold_mariano")}},
        "falsification": falsification,
        "robustness": rob, "economic_size": econ,
        "deviations_from_preregistration": deviations,
        "latest": latest, "forecast": fc, "national": nat, "history": history,
        "replication_tolerance_per_1000": cfg["replication_tolerance_per_1000"],
    }
    os.makedirs(model_dir, exist_ok=True)
    with open(os.path.join(model_dir, "artifact.json"), "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=1, default=_json_default)
        f.write("\n")

    write_outputs(outputs, artifact, res, names, ur, coint, oos, rob, make_figures)
    return artifact


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def write_outputs(outputs, a, res, names, ur, coint, oos, rob, make_figures):
    os.makedirs(outputs, exist_ok=True)
    pd.DataFrame({"regressor": names, "label": [a["specification"]["labels"][n] for n in names],
                  "expected_sign": [a["specification"]["expected_signs"].get(n, "") for n in names],
                  "coef": res["beta"], "se_dk": res["se"], "t": res["t"], "p": res["p"]}
                 ).to_csv(os.path.join(outputs, "table_results.csv"), index=False, float_format="%.4f")
    ur.to_csv(os.path.join(outputs, "annex_unit_roots.csv"), index=False, float_format="%.4f")
    coint.to_csv(os.path.join(outputs, "annex_cointegration.csv"), index=False, float_format="%.4f")
    oos["by_region"].to_csv(os.path.join(outputs, "annex_oos_by_region.csv"), float_format="%.4f")
    pd.DataFrame(rob).to_csv(os.path.join(outputs, "table_robustness.csv"), index=False, float_format="%.4f")
    b = a["benchmark"]
    pd.DataFrame([{"measure": "RMSE", "model": b["rmse_model"], "benchmark": b["rmse_benchmark"], "ratio": b["rmse_ratio"]},
                  {"measure": "MAE", "model": b["mae_model"], "benchmark": b["mae_benchmark"], "ratio": b["mae_ratio"]}]
                 ).to_csv(os.path.join(outputs, "table_oos.csv"), index=False, float_format="%.4f")
    with open(os.path.join(outputs, "annex_diagnostics.json"), "w", encoding="utf-8") as f:
        json.dump({"diagnostics": a["diagnostics"], "flags": a["diagnostic_flags"],
                   "integration": a["integration"], "cointegration": a["cointegration"]},
                  f, indent=1, default=_json_default)
    if make_figures:
        figures(outputs, a, oos)


def figures(outputs, a, oos):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tag = " [SYNTHETIC TEST DATA]" if a["synthetic_data"] else ""
    h = a["national"]["history"]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(range(len(h)), [v for _, v in h], color="#1f5f8b")
    step = max(1, len(h) // 8)
    ax.set_xticks(range(0, len(h), step), [q for q, _ in h][::step])
    ax.set_ylabel("Births per 1,000, annualised")
    ax.set_title("Kazakhstan, sum of 16 regions" + tag, fontsize=10)
    ax.text(0, -0.28, "Source: Bureau of National Statistics (stat.gov.kz); authors' calculations.",
            transform=ax.transAxes, fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(outputs, "fig_national_history.png"), dpi=150)
    plt.close(fig)
    tr = oos["test_rows"]
    agg = tr.groupby("t")[["cbr", "f_model", "f_bench"]].mean() if "cbr" in tr else None
    if agg is not None:
        fig, ax = plt.subplots(figsize=(8, 3.2))
        x = [qlabel(int(t)) for t in agg.index]
        ax.plot(x, agg["cbr"], label="Actual", color="#222")
        ax.plot(x, agg["f_model"], label="Model", color="#1f5f8b")
        ax.plot(x, agg["f_bench"], label="Benchmark (same quarter last year)", color="#c0712b", ls="--")
        ax.set_ylabel("Mean regional CBR, per 1,000")
        ax.set_title("Hold-out: one-quarter-ahead forecasts" + tag, fontsize=10)
        ax.legend(fontsize=7)
        plt.setp(ax.get_xticklabels(), rotation=45, fontsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(outputs, "fig_holdout.png"), dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    a = run()
    b = a["benchmark"]
    print(f"artifact written. RMSE ratio model/benchmark = {b['rmse_ratio']:.3f} ({b['winner']} wins)")
