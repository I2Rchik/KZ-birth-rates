"""Independent cross-check with standard packages (run on your own machine).

    pip install linearmodels==6.1 statsmodels==0.14.4
    python tests/crosscheck_packages.py

It re-estimates the main regression with linearmodels' PanelOLS (entity
fixed effects, Driscoll-Kraay "kernel" covariance) and re-runs ADF/KPSS
with statsmodels, then prints them next to model/artifact.json.
Coefficients must match to about 1e-8. Standard errors can differ slightly:
small-sample scaling and the kernel bandwidth are set differently. Unit-root
p-values can differ too: statsmodels uses MacKinnon tables, we use Monte Carlo
at the exact sample size. Paste the output into AI_USE.md as the verification record.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import model  # noqa: E402

try:
    from linearmodels.panel import PanelOLS
    from statsmodels.tsa.stattools import adfuller, kpss
except ImportError:
    sys.exit("Install first:  pip install linearmodels statsmodels")

a = json.load(open(os.path.join(ROOT, "model", "artifact.json"), encoding="utf-8"))
cfg = json.load(open(os.path.join(ROOT, "src", "config.json"), encoding="utf-8"))["model"]
panel = pd.read_csv(os.path.join(ROOT, "data", "processed", "panel.csv"))
drivers = [d for d in cfg["drivers"] if d["name"] in panel and panel[d["name"]].notna().any()]
spec = {"dep": "y", "level": "cbr", "own_lags": cfg["own_lags"], "drivers": drivers}
p = model.add_lags(panel, spec)
d, names = model.design(p, spec)
d = d.set_index(["code", "t"])

lag = int(a["specification"]["standard_errors"].split(",")[-1].split()[0])
res = PanelOLS(d["y"], d[names], entity_effects=True).fit(cov_type="kernel", kernel="bartlett", bandwidth=lag)
print(f"{'regressor':<10} {'ours':>10} {'linearmodels':>14} {'our DK se':>10} {'lm DK se':>10}")
for n in names:
    print(f"{n:<10} {a['coefficients'][n]:>10.5f} {res.params[n]:>14.5f} {a['std_errors'][n]:>10.4f} {res.std_errors[n]:>10.4f}")
print("max |coef diff| =", max(abs(a["coefficients"][n] - res.params[n]) for n in names))

print("\nADF / KPSS p-values for y by region (statsmodels):")
for code, g in panel.groupby("code"):
    z = g["y"].dropna().to_numpy()
    print(f"{code}: ADF p={adfuller(z, maxlag=4, autolag='AIC', regression='c')[1]:.3f}  "
          f"KPSS p={kpss(z, regression='c', nlags='legacy')[1]:.3f}")
