"""Data layer: data/raw (immutable downloads) -> data/processed (generated).

Run:  python run.py ingest
Every transformation is a named function below. Nothing in data/raw is
ever modified; data/processed is fully regenerated on every run and is
byte-identical across runs on the same raw files.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from periods import parse_period, quarter_of  # noqa: E402
from regions import REGIONS, is_total, region_code  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "src", "config.json")


class DataError(Exception):
    """Raised with a plain-language message when inputs are missing or invalid."""


# ---------------------------------------------------------------- reading
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(raw_dir):
    path = os.path.join(raw_dir, "manifest.json")
    if not os.path.exists(path):
        raise DataError(f"No data/raw/manifest.json. Register downloads with "
                        f"`python run.py register-raw` (see README).")
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)["files"]
    for e in entries:
        p = os.path.join(raw_dir, e["file"])
        if not os.path.exists(p):
            raise DataError(f"Raw file listed in manifest is missing: data/raw/{e['file']}")
        if sha256(p) != e["sha256"]:
            raise DataError(f"data/raw/{e['file']} changed since it was downloaded "
                            f"(checksum mismatch). Raw files must never be edited.")
    return entries


def _read_table(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        sheets = pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl")
        return list(sheets.values())
    if ext == ".csv":
        for enc in ("utf-8-sig", "cp1251"):
            try:
                return [pd.read_csv(path, header=None, dtype=object, encoding=enc, sep=None, engine="python")]
            except UnicodeDecodeError:
                continue
    raise DataError(f"Unsupported raw file type: {os.path.basename(path)} (use .xlsx or .csv)")


def _to_number(v):
    if v is None:
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "—", "...", "x", "х", "nan"):
        return np.nan
    try:
        return float(s)
    except ValueError:
        return np.nan


def parse_table(df):
    """Find regions and periods in a wide (regions x periods) or long table.

    Returns long DataFrame: code, component, kind, year, idx, value."""
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    df.columns = range(df.shape[1])
    # long format: header row containing region / period / value
    head = [str(x).strip().lower() for x in df.iloc[0].tolist()]
    if {"region", "period", "value"} <= set(head):
        cols = {name: head.index(name) for name in ("region", "period", "value")}
        rows = []
        for _, r in df.iloc[1:].iterrows():
            code, comp = region_code(r[cols["region"]])
            per = parse_period(r[cols["period"]])
            if code and per:
                rows.append((code, comp, *per, _to_number(r[cols["value"]])))
        return pd.DataFrame(rows, columns=["code", "component", "kind", "year", "idx", "value"])

    # wide format: a header row with >= 3 period labels, a column of region names
    header_row, period_cols = None, {}
    for i in range(min(len(df), 30)):
        found = {j: parse_period(df.iat[i, j]) for j in range(df.shape[1])}
        found = {j: p for j, p in found.items() if p}
        if len(found) >= 3:
            header_row, period_cols = i, found
            break
    if header_row is None:
        raise DataError("Could not find a row of period labels (e.g. 'январь 2015', '2015 Q1').")
    region_col, best = None, 0
    for j in range(df.shape[1]):
        if j in period_cols:
            continue
        n = sum(region_code(v)[0] is not None for v in df.iloc[header_row + 1:, j])
        if n > best:
            region_col, best = j, n
    if region_col is None or best < 3:
        raise DataError("Could not find a column of region names.")
    rows = []
    for i in range(header_row + 1, len(df)):
        label = df.iat[i, region_col]
        code, comp = region_code(label)
        if code is None:
            continue  # national total, notes, blank rows
        for j, per in period_cols.items():
            rows.append((code, comp, *per, _to_number(df.iat[i, j])))
    return pd.DataFrame(rows, columns=["code", "component", "kind", "year", "idx", "value"])


def read_raw(path):
    out = []
    for sheet in _read_table(path):
        try:
            out.append(parse_table(sheet))
        except DataError:
            continue
    if not out:
        raise DataError(f"No region-by-period table found in {os.path.basename(path)}.")
    df = pd.concat(out, ignore_index=True)
    # a series may appear in several sheets/files: keep the first value per cell
    return df.drop_duplicates(["code", "component", "kind", "year", "idx"])


# ------------------------------------------------------ transformations
def cumulative_to_monthly(df):
    """'January-March' style cumulative values -> monthly values by differencing."""
    cum = df[df.kind == "CUM"]
    if cum.empty:
        return df
    parts = []
    for (code, comp, year), g in cum.groupby(["code", "component", "year"]):
        s = g.set_index("idx")["value"].sort_index()
        prev_m, prev_v = 0, 0.0
        for m, v in s.items():
            if m == 1 or prev_m == m - 1 or (prev_m == m - 3 and m % 3 == 0):
                kind, idx = ("M", m) if m - prev_m == 1 else ("Q", m // 3)
                if v == v and (prev_m == 0 or prev_v == prev_v):
                    parts.append((code, comp, kind, year, idx, v - prev_v))
            prev_m, prev_v = m, v
    conv = pd.DataFrame(parts, columns=["code", "component", "kind", "year", "idx", "value"])
    return pd.concat([df[df.kind != "CUM"], conv], ignore_index=True)


def to_quarterly(df, how):
    """Monthly -> quarterly. how = 'sum' (flows) or 'mean' (rates, indices).
    A quarter is kept only if all three months are present."""
    q = df[df.kind == "Q"].copy()
    m = df[df.kind == "M"].copy()
    if not m.empty:
        m["q"] = (m["idx"] - 1) // 3 + 1
        g = m.groupby(["code", "component", "year", "q"])["value"]
        agg = g.sum(min_count=3) if how == "sum" else g.mean()
        cnt = g.count()
        agg[cnt < 3] = np.nan
        agg = agg.reset_index().rename(columns={"q": "idx"})
        agg["kind"] = "Q"
        q = pd.concat([q, agg[q.columns if len(q.columns) else agg.columns]], ignore_index=True)
    q = q.drop_duplicates(["code", "component", "year", "idx"])
    q["quarter"] = q["year"].astype(int).astype(str) + "Q" + q["idx"].astype(int).astype(str)
    return q[["code", "component", "quarter", "value"]]


def chain_index(df, base):
    """CPI to a level index. base='previous_period' chains month-on-month
    indices (previous month = 100); 'level' leaves the index unchanged."""
    if base == "level":
        return df
    if base != "previous_period":
        raise DataError(f"Unknown CPI base '{base}' in src/config.json")
    df = df[df.kind.isin(["M", "Q"])].sort_values(["code", "component", "kind", "year", "idx"]).copy()
    df["value"] = df.groupby(["code", "component", "kind"])["value"].transform(
        lambda s: 100 * np.exp(np.log(s / 100).cumsum()))
    return df


def population_average(df):
    """Stock at start of period -> average population over each quarter:
    mean of the stock at the start of the quarter and at the start of the next.
    Annual (1 January) stocks are linearly interpolated to quarter starts."""
    rows = []
    for (code, comp), g in df.groupby(["code", "component"]):
        pts = {}
        for _, r in g.iterrows():
            if r.kind == "M":
                t = r.year + (r.idx - 1) / 12
            elif r.kind == "Q":
                t = r.year + (r.idx - 1) / 4
            elif r.kind == "A":
                t = float(r.year)
            else:
                continue
            if r.value == r.value:
                pts[t] = r.value
        if len(pts) < 2:
            continue
        ts = np.array(sorted(pts))
        vs = np.array([pts[t] for t in ts])
        y0, y1 = int(np.floor(ts.min())), int(np.floor(ts.max()))
        for y in range(y0, y1 + 1):
            for qq in range(1, 5):
                a, b = y + (qq - 1) / 4, y + qq / 4
                if a < ts.min() or b > ts.max():
                    continue
                pa, pb = np.interp(a, ts, vs), np.interp(b, ts, vs)
                rows.append((code, comp, f"{y}Q{qq}", (pa + pb) / 2))
    return pd.DataFrame(rows, columns=["code", "component", "quarter", "value"])


def _drop_before_existence(q):
    """A component (e.g. Abai) is counted only from its first reported quarter."""
    first = q.dropna(subset=["value"]).groupby(["code", "component"])["quarter"].min()
    q = q.merge(first.rename("first"), on=["code", "component"], how="inner")
    return q[q.quarter >= q["first"]].drop(columns="first")


def harmonise_sum(q):
    """Counts and stocks: add the current regions inside each harmonised unit.
    Once a component exists, a missing value makes the unit-quarter missing
    (no silent under-counting)."""
    q = _drop_before_existence(q)
    return (q.groupby(["code", "quarter"])["value"]
            .apply(lambda s: s.sum() if s.notna().all() else np.nan).reset_index())


def break_check(panel, col, quarters=("2018Q3", "2022Q3"), limit=0.25):
    """Flag jumps at the border changes: a sign of double counting or of
    old/new-border series being mixed. Returns plain-language warnings."""
    out = []
    for code, g in panel.groupby("code"):
        s = g.set_index("quarter")[col]
        for qb in quarters:
            if qb not in s.index:
                continue
            i = list(s.index).index(qb)
            before, after = s.iloc[max(0, i - 4):i].mean(), s.iloc[i:i + 4].mean()
            if before and after and abs(after / before - 1) > limit:
                out.append(f"{code}: {col} jumps {100 * (after / before - 1):+.0f}% around {qb}; "
                           f"check the border harmonisation.")
    return out


def harmonise_weighted(q, pop_components):
    """Rates and indices: population-weighted mean of the components."""
    q = _drop_before_existence(q)
    m = q.merge(pop_components.rename(columns={"value": "w"}), on=["code", "component", "quarter"], how="left")
    m["w"] = m["w"].fillna(m.groupby(["code", "quarter"])["w"].transform("mean")).fillna(1.0)
    m = m.dropna(subset=["value"])
    m["vw"] = m["value"] * m["w"]
    g = m.groupby(["code", "quarter"])
    return (g["vw"].sum() / g["w"].sum()).rename("value").reset_index()


def annualised_rate(count, population):
    """Events per 1,000 population, annualised (x4 for a quarter)."""
    return 4 * 1000 * count / population


def log_yoy(s, by):
    """Year-on-year log change: ln x(t) - ln x(t-4) within each region."""
    return np.log(s) - np.log(s).groupby(by).shift(4)


def diff_yoy(s, by):
    """Year-on-year difference x(t) - x(t-4) within each region."""
    return s - s.groupby(by).shift(4)


# ---------------------------------------------------------------- build
def build(raw_dir=None, out_dir=None):
    raw_dir = raw_dir or os.path.join(ROOT, "data", "raw")
    out_dir = out_dir or os.path.join(ROOT, "data", "processed")
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)["series"]
    manifest = load_manifest(raw_dir)

    raw = {}
    for e in manifest:
        df = read_raw(os.path.join(raw_dir, e["file"]))
        raw.setdefault(e["series"], []).append(df)
    missing = [s for s, c in cfg.items() if c.get("required") and s not in raw]
    if missing:
        raise DataError("Missing required raw series: " + ", ".join(missing))
    raw = {s: pd.concat(v, ignore_index=True).drop_duplicates(["code", "component", "kind", "year", "idx"])
           for s, v in raw.items()}

    pop_c = population_average(raw["population"])
    quarterly = {"population": harmonise_sum(pop_c)}
    for s, c in cfg.items():
        if s == "population" or s not in raw:
            continue
        df = cumulative_to_monthly(raw[s])
        if c["type"] == "index":
            df = chain_index(df, c.get("base", "previous_period"))
        q = to_quarterly(df, "sum" if c["type"] == "count" else "mean")
        quarterly[s] = harmonise_sum(q) if c["type"] == "count" else harmonise_weighted(q, pop_c)

    panel = None
    for s, q in quarterly.items():
        q = q.rename(columns={"value": s})
        panel = q if panel is None else panel.merge(q, on=["code", "quarter"], how="outer")
    panel = panel[panel.code.isin(REGIONS)]
    panel["t"] = panel["quarter"].str[:4].astype(int) * 4 + panel["quarter"].str[-1].astype(int) - 1
    # full rectangular grid so lags are always exactly k quarters back
    grid = pd.MultiIndex.from_product([sorted(REGIONS), range(panel.t.min(), panel.t.max() + 1)],
                                      names=["code", "t"]).to_frame(index=False)
    panel = grid.merge(panel.drop(columns="quarter"), on=["code", "t"], how="left")
    panel["quarter"] = (panel.t // 4).astype(str) + "Q" + (panel.t % 4 + 1).astype(str)
    panel = panel.sort_values(["code", "t"]).reset_index(drop=True)

    by = panel["code"]
    panel["cbr"] = annualised_rate(panel["births"], panel["population"])
    panel["marriage_rate"] = annualised_rate(panel["marriages"], panel["population"])
    panel["y"] = log_yoy(panel["cbr"], by)
    panel["y_births"] = log_yoy(panel["births"], by)
    panel["m"] = log_yoy(panel["marriage_rate"], by)
    if "wage" in panel and "cpi" in panel:
        panel["w"] = log_yoy(panel["wage"], by) - log_yoy(panel["cpi"], by)
    if "unemployment" in panel:
        panel["u"] = diff_yoy(panel["unemployment"], by)
    if "housing" in panel:
        panel["housing_pc"] = 1000 * panel["housing"] / panel["population"]
        panel["h"] = log_yoy(panel["housing_pc"], by)

    # drop leading/trailing quarters with no births anywhere
    has = panel.groupby("t")["births"].count()
    keep = has[has > 0].index
    panel = panel[panel.t.between(keep.min(), keep.max())]

    os.makedirs(out_dir, exist_ok=True)
    cols = ["code", "quarter", "t", "births", "marriages", "population", "cbr", "marriage_rate",
            "wage", "cpi", "unemployment", "housing", "housing_pc", "y", "y_births", "m", "w", "u", "h"]
    cols = [c for c in cols if c in panel.columns]
    panel[cols].to_csv(os.path.join(out_dir, "panel.csv"), index=False, float_format="%.10g",
                       lineterminator="\n")
    meta = {
        "regions": REGIONS,
        "sources": [{k: e.get(k) for k in ("series", "file", "publisher", "url", "identifier",
                                           "retrieved", "revised", "synthetic")} for e in manifest],
        "synthetic": any(e.get("synthetic") for e in manifest),
        "first_quarter": panel.quarter.iloc[0],
        "last_quarter": panel.dropna(subset=["cbr"]).quarter.max(),
        "warnings": break_check(panel, "births") + break_check(panel, "population"),
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return panel


if __name__ == "__main__":
    try:
        p = build()
        print(f"data/processed rebuilt: {p.code.nunique()} regions, {p.quarter.min()}-{p.quarter.max()}")
    except DataError as e:
        print("DATA ERROR:", e)
        sys.exit(2)
