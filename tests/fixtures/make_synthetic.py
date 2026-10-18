"""SYNTHETIC TEST FIXTURE - NOT REAL DATA.

Generates raw files in the same shape as Taldau exports (regions in rows,
Russian period labels in columns, current 20-region names including the
2018 and 2022 splits) so the pipeline, tests and acceptance checks can run
without network access. Every file is flagged "synthetic": true in the
manifest, and the website then shows a red TEST DATA banner.
Never copy these files into data/raw.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль",
          "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
CURRENT = ["Акмолинская", "Актюбинская", "Алматинская", "Атырауская", "Западно-Казахстанская",
           "Жамбылская", "Карагандинская", "Костанайская", "Кызылординская", "Мангистауская",
           "Туркестанская", "Павлодарская", "Северо-Казахстанская", "Восточно-Казахстанская",
           "г.Астана", "г.Алматы", "г.Шымкент", "Абай", "Жетісу", "Улытау"]
SPLIT_FROM = {"г.Шымкент": ("Туркестанская", 2018, 0.35), "Абай": ("Восточно-Казахстанская", 2022, 0.45),
              "Жетісу": ("Алматинская", 2022, 0.33), "Улытау": ("Карагандинская", 2022, 0.15)}


def _label(r):
    return r if r.startswith("г.") or r in ("Абай", "Жетісу", "Улытау") else r + " область"


def make(out_dir, start=2010, end_year=2026, end_month=6, seed=7):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)
    months = [(y, m) for y in range(start, end_year + 1) for m in range(1, 13)
              if (y, m) <= (end_year, end_month)]
    n = len(months)
    base = {r: rng.uniform(15, 27) for r in CURRENT}
    popl = {r: rng.uniform(0.5, 2.2) * 1e6 for r in CURRENT}
    marriage = {}
    births = {}
    for r in CURRENT:
        mr = base[r] * 0.45 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
        marriage[r] = mr
        b = np.empty(n)
        for i in range(n):
            lagged = mr[i - 9] if i >= 9 else mr[0]
            season = 1 + 0.08 * np.sin(2 * np.pi * (months[i][1] - 3) / 12)
            b[i] = 2.2 * lagged * season * np.exp(rng.normal(0, 0.03))
        births[r] = b

    def share(r, y):
        if r in SPLIT_FROM:
            parent, yr, s = SPLIT_FROM[r]
            return s if y >= yr else 0.0
        kids = [k for k, v in SPLIT_FROM.items() if v[0] == r]
        return 1 - sum(SPLIT_FROM[k][2] for k in kids if y >= SPLIT_FROM[k][1])

    def full(r):
        """Rate series of a current region: use the parent's process for children."""
        return r if r not in SPLIT_FROM else SPLIT_FROM[r][0]

    def write(name, cols, values):
        df = pd.DataFrame([[np.nan] * len(cols)] + values, columns=cols)
        df.insert(0, "Регион", ["Республика Казахстан"] + [_label(r) for r in CURRENT])
        path = os.path.join(out_dir, name)
        with pd.ExcelWriter(path, engine="openpyxl") as xw:
            pd.DataFrame([["Источник: SYNTHETIC TEST FIXTURE"]]).to_excel(xw, index=False, header=False, startrow=0)
            df.to_excel(xw, index=False, startrow=2)
        return path

    mcols = [f"{MONTHS[m - 1]} {y}" for y, m in months]

    def monthly_counts(src, scale):
        rows = []
        for r in CURRENT:
            row = []
            for i, (y, m) in enumerate(months):
                s = share(r, y)
                row.append(np.nan if s == 0 else round(src[full(r)][i] * popl[full(r)] / 12000 * s * scale))
            rows.append(row)
        return rows

    files = {
        "births": write("births_monthly.xlsx", mcols, monthly_counts(births, 1.0)),
        "marriages": write("marriages_monthly.xlsx", mcols, monthly_counts(marriage, 1.0)),
    }
    years = list(range(start, end_year + 2))
    pop_rows = [[np.nan if share(r, y) == 0 else round(popl[full(r)] * (1.012 ** (y - start)) * share(r, y))
                 for y in years] for r in CURRENT]
    files["population"] = write("population_jan1.xlsx", [f"на 1 января {y} г." for y in years], pop_rows)
    quarters = [(y, q) for y in range(start, end_year + 1) for q in range(1, 5) if (y, q * 3) <= (end_year, end_month)]
    qcols = [f"{q} квартал {y}" for y, q in quarters]
    wage = [[np.nan if share(r, y) == 0 else round(80000 * 1.09 ** (y - start) * (1 + 0.02 * q) * rng.uniform(0.95, 1.05))
             for y, q in quarters] for r in CURRENT]
    files["wage"] = write("wage_quarterly.xlsx", qcols, wage)
    unemp = [[np.nan if share(r, y) == 0 else round(rng.uniform(4.3, 5.5), 1) for y, q in quarters] for r in CURRENT]
    files["unemployment"] = write("unemployment_quarterly.xlsx", qcols, unemp)
    cpi = [[np.nan if share(r, y) == 0 else round(100 + rng.normal(0.6, 0.4), 1) for y, m in months] for r in CURRENT]
    files["cpi"] = write("cpi_mom.xlsx", mcols, cpi)
    housing = [[np.nan if share(r, y) == 0 else round(popl[full(r)] * share(r, y) * rng.uniform(0.04, 0.09))
                for y, m in months] for r in CURRENT]
    files["housing"] = write("housing_monthly.xlsx", mcols, housing)

    manifest = {"files": []}
    for s, path in files.items():
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        manifest["files"].append({"series": s, "file": os.path.basename(path), "sha256": digest,
                                  "publisher": "SYNTHETIC TEST FIXTURE", "url": "none",
                                  "identifier": "synthetic", "retrieved": "2026-10-18",
                                  "revised": "n/a", "synthetic": True})
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return out_dir


if __name__ == "__main__":
    make(sys.argv[1])
    print("synthetic fixture written to", sys.argv[1])
