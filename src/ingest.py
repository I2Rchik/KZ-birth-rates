"""Data layer: data/raw (immutable downloads) -> data/processed (generated).

Run:  python run.py ingest
Every transformation is a named function below. Nothing in data/raw is ever
modified (checksums are verified); data/processed is fully regenerated on
every run and is byte-identical across runs on the same raw files.

Formats read:
  * Taldau "data.csv" downloads (tab-separated, gzip-compressed, long format:
    NAM / DAT / PERIOD / KATO / [SPTM] / VAL)
  * Taldau "download.xls" (an HTML table: regions x periods in the header)
  * plain .xlsx / .csv tables with regions in rows and periods in columns
"""
import gzip
import hashlib
import io
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from periods import parse_period  # noqa: E402
from regions import REGIONS, is_top_level, region_code  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "src", "config.json")
COLS = ["code", "component", "kind", "year", "idx", "value"]


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
        raise DataError("No data/raw/manifest.json. Register downloads with "
                        "`python run.py register-raw` (see README).")
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


def _bytes(path):
    with open(path, "rb") as f:
        b = f.read()
    return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b


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


def _rows(names, periods, values, top_only):
    out = []
    for name, per, val in zip(names, periods, values):
        if top_only and not is_top_level(name):
            continue  # districts, towns, the national total
        code, comp = region_code(name)
        if code and per:
            out.append((code, comp, *per, _to_number(val)))
    return pd.DataFrame(out, columns=COLS)


def read_taldau_long(text):
    """Taldau data.csv: one row per (indicator, period, region, settlement type)."""
    d = pd.read_csv(io.StringIO(text), sep="\t", dtype=str)
    kato = [c for c in d.columns if c.startswith("КАТО")][0]
    sptm = [c for c in d.columns if c.startswith("СПТМ")]
    if sptm:
        d = d[d[sptm[0]] == "Всего"]  # total, not urban/rural split
    return _rows(d[kato], [parse_period(x) for x in d["DAT"]], d["VAL"], top_only=True)


def read_taldau_html(text):
    """Taldau download.xls: an HTML table whose header holds region and period."""
    tables = pd.read_html(io.StringIO(text))
    out = []
    for t in tables:
        names, pers, vals = [], [], []
        for col in t.columns:
            if not isinstance(col, tuple):
                continue
            per = parse_period(col[-1])
            if per is None:
                continue
            v = t[col].dropna()
            if v.empty:
                continue
            names.append(col[0])
            pers.append(per)
            vals.append(v.iloc[0])
        out.append(_rows(names, pers, vals, top_only=True))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS)


def parse_wide(df):
    """A table with region names in one column and period labels in a header row."""
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    df.columns = range(df.shape[1])
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
    names, pers, vals = [], [], []
    for i in range(header_row + 1, len(df)):
        for j, per in period_cols.items():
            names.append(df.iat[i, region_col])
            pers.append(per)
            vals.append(df.iat[i, j])
    return _rows(names, pers, vals, top_only=True)


def read_raw(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        out = []
        for sheet in pd.read_excel(path, sheet_name=None, header=None, engine="openpyxl").values():
            try:
                out.append(parse_wide(sheet))
            except DataError:
                continue
        df = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=COLS)
    else:
        raw = _bytes(path)
        text = None
        for enc in ("utf-8-sig", "cp1251"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise DataError(f"{os.path.basename(path)}: unreadable text encoding.")
        head = text[:400].lower()
        if head.lstrip().startswith("<html") or "<table" in head:
            df = read_taldau_html(text)
        elif '"nam"' in head or head.startswith("nam\t"):
            df = read_taldau_long(text)
        else:
            df = parse_wide(pd.read_csv(io.StringIO(text), header=None, dtype=object, sep=None, engine="python"))
    if df.empty:
        raise DataError(f"No region-by-period values found in {os.path.basename(path)}.")
    df["year"] = df["year"].astype(int)
    df["idx"] = df["idx"].astype(int)
    return df.drop_duplicates(["code", "component", "kind", "year", "idx"])


# ------------------------------------------------- border harmonisation
def full_unit_rule(df):
    """Where a row describes the whole harmonised unit on its old borders
    (component *_FULL, e.g. South Kazakhstan before the 2018 split), drop the
    other components for that period: Taldau also lists Shymkent as a town
    inside South Kazakhstan, which would otherwise be counted twice."""
    full = df[df.component.str.endswith("_FULL")][["code", "kind", "year", "idx"]].drop_duplicates()
    if full.empty:
        return df
    m = df.merge(full.assign(has_full=True), on=["code", "kind", "year", "idx"], how="left")
    keep = m["has_full"].isna() | m["component"].str.endswith("_FULL")
    return m[keep.to_numpy()].drop(columns="has_full")


def existence_rule(df):
    """A component (e.g. Abai) counts only from its first reported period, so a
    blank cell before it existed is not read as a missing observation."""
    df = df.copy()
    df["order"] = df["year"] * 100 + df["idx"]
    first = df.dropna(subset=["value"]).groupby(["code", "component", "kind"])["order"].min().rename("first")
    df = df.merge(first, on=["code", "component", "kind"], how="inner")
    return df[df.order >= df["first"]].drop(columns=["order", "first"])


def harmonise_counts(df):
    """Counts and stocks: add the components of each harmonised unit for each
    period. Once a component exists, a missing value makes the sum missing
    (no silent under-counting)."""
    df = existence_rule(full_unit_rule(df))
    g = df.groupby(["code", "kind", "year", "idx"])["value"]
    out = g.apply(lambda s: s.sum() if s.notna().all() else np.nan).reset_index()
    out["component"] = out["code"]
    return out[COLS]


def harmonise_weighted(df, weights):
    """Rates, per-capita values and price changes: population-weighted mean of
    the components. `weights` has code, component, year, idx(quarter), w."""
    df = existence_rule(full_unit_rule(df)).dropna(subset=["value"])
    m = df.merge(weights, on=["code", "component", "year", "idx"], how="left")
    m["w"] = m["w"].fillna(m.groupby(["code", "kind", "year", "idx"])["w"].transform("mean")).fillna(1.0)
    m["vw"] = m["value"] * m["w"]
    g = m.groupby(["code", "kind", "year", "idx"])
    out = (g["vw"].sum() / g["w"].sum()).rename("value").reset_index()
    out["component"] = out["code"]
    return out[COLS]


# ------------------------------------------------------ transformations
def cumulative_to_period(df):
    """'January-March', 'January-June', ... cumulative values -> the value of
    each quarter (or month) by differencing within the year."""
    cum = df[df.kind == "CUM"]
    if cum.empty:
        return df
    parts = []
    for (code, comp, year), g in cum.groupby(["code", "component", "year"]):
        s = g.set_index("idx")["value"].sort_index()
        prev_m, prev_v = 0, 0.0
        for m, v in s.items():
            step = m - prev_m
            if step in (1, 3) and (step == 1 or m % 3 == 0):
                kind, idx = ("M", m) if step == 1 else ("Q", m // 3)
                parts.append((code, comp, kind, year, idx, v - prev_v))
            prev_m, prev_v = m, v
    conv = pd.DataFrame(parts, columns=COLS)
    return pd.concat([df[df.kind != "CUM"], conv], ignore_index=True)


def to_quarterly(df, how):
    """Monthly -> quarterly ('sum' for flows, 'mean' for rates/indices).
    A quarter built from months is kept only if all three are present."""
    q = df[df.kind == "Q"][["code", "component", "year", "idx", "value"]]
    m = df[df.kind == "M"].copy()
    if not m.empty:
        m["q"] = (m["idx"] - 1) // 3 + 1
        g = m.groupby(["code", "component", "year", "q"])["value"]
        agg = g.sum(min_count=3) if how == "sum" else g.mean()
        agg[g.count() < 3] = np.nan
        agg = agg.reset_index().rename(columns={"q": "idx"})
        q = pd.concat([q, agg], ignore_index=True)
    q = q.drop_duplicates(["code", "component", "year", "idx"])
    q["t"] = q["year"] * 4 + q["idx"] - 1
    return q


def chain_index(df):
    """Period-on-period index (previous period = 100) -> level index (first period = 100)."""
    df = df.sort_values(["code", "t"]).copy()
    df["value"] = df.groupby("code")["value"].transform(lambda s: 100 * np.exp(np.log(s / 100).cumsum()))
    return df


def population_quarterly(df, window_months=12):
    """Start-of-month (or 1 January) stocks -> average population per quarter:
    mean of the stock at the start of the quarter and at the start of the next.
    After the last published month the stock is projected forward at the
    average monthly growth of the last `window_months` months; every quarter
    that uses a projected value is flagged."""
    rows = []
    months = df.year * 12 + np.where(df.kind == "M", df.idx - 1, 0)
    global_last = int(months[df.value.notna()].max())
    for (code, comp), g in df.groupby(["code", "component"]):
        pts = {}
        for _, r in g.dropna(subset=["value"]).iterrows():
            if r.kind == "M":
                pts[r.year * 12 + r.idx - 1] = r.value
            elif r.kind == "A":
                pts[r.year * 12] = r.value
        if len(pts) < 2:
            continue
        ms = np.array(sorted(pts))
        vs = np.log(np.array([pts[m] for m in ms]))
        last = ms.max()
        recent = ms[ms >= last - window_months]
        growth = (vs[-1] - vs[ms == recent.min()][0]) / max(1, last - recent.min())
        # only series still published at the file's last month are projected;
        # a series that ended (South Kazakhstan in 2018) simply stops
        horizon = last + 36 if last == global_last else last
        for t in range(int(np.ceil(ms.min() / 3)), int(horizon // 3)):
            a, b = 3 * t, 3 * t + 3
            if a < ms.min():
                continue

            def at(mm):
                if mm <= last:
                    return float(np.exp(np.interp(mm, ms, vs))), False
                return float(np.exp(vs[-1] + growth * (mm - last))), True
            pa, ea = at(a)
            pb, eb = at(b)
            rows.append((code, comp, t // 4, t % 4 + 1, (pa + pb) / 2, ea or eb))
    out = pd.DataFrame(rows, columns=["code", "component", "year", "idx", "value", "extrapolated"])
    out["t"] = out["year"] * 4 + out["idx"] - 1
    return out


def annualised_rate(count, population, per_year=4):
    """Events per 1,000 population, annualised (x4 for a quarter)."""
    return per_year * 1000 * count / population


def log_yoy(s, by, k=4):
    """Year-on-year log change: ln x(t) - ln x(t-k) within each region."""
    return np.log(s) - np.log(s).groupby(by).shift(k)


def diff_yoy(s, by, k=4):
    return s - s.groupby(by).shift(k)


def annual_to_publication_quarters(annual, col):
    """An annual value for year Y is published early in Y+1, so it is dated at
    the four quarters of Y+1. With a driver lag of 1 quarter the model then
    only ever uses annual figures that had been published."""
    rows = [(c, (int(y) + 1) * 4 + q, v) for c, y, v in zip(annual["code"], annual["year"], annual[col])
            for q in range(4)]
    return pd.DataFrame(rows, columns=["code", "t", col])


def break_check(panel, col, quarters=("2018Q2", "2018Q3", "2022Q3", "2023Q1"), limit=0.25):
    """Flag year-on-year jumps over 25% right at the border changes or the
    January-2023 population revision: a sign of double counting."""
    out = []
    for code, g in panel.groupby("code"):
        s = g.set_index("quarter")[col]
        prev = g.set_index("quarter")[col].shift(4)
        for qb in quarters:
            if qb in s.index and prev.get(qb, np.nan) == prev.get(qb, np.nan) and s[qb] == s[qb]:
                ch = s[qb] / prev[qb] - 1
                if abs(ch) > limit:
                    out.append(f"{code}: {col} changes {100 * ch:+.0f}% year on year in {qb}; check the border harmonisation.")
    return out


# ---------------------------------------------------------------- build
def _read_series(raw_dir, manifest):
    raw = {}
    for e in manifest:
        df = read_raw(os.path.join(raw_dir, e["file"]))
        raw.setdefault(e["series"], []).append(df)
    return {s: pd.concat(v, ignore_index=True).drop_duplicates(["code", "component", "kind", "year", "idx"])
            for s, v in raw.items()}


def build(raw_dir=None, out_dir=None):
    raw_dir = raw_dir or os.path.join(ROOT, "data", "raw")
    out_dir = out_dir or os.path.join(ROOT, "data", "processed")
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    scfg = cfg["series"]
    manifest = load_manifest(raw_dir)
    raw = _read_series(raw_dir, manifest)
    missing = [s for s, c in scfg.items() if c.get("required") and s not in raw]
    if missing:
        raise DataError("Missing required raw series: " + ", ".join(missing))

    # population: harmonise monthly stocks first, then average per quarter
    win = scfg["population"].get("extrapolate_window_months", 12)
    # unit totals month by month (so the August-2022 split of Abai is seamless),
    # then quarterly averages; component averages are kept only as weights
    pop_code = population_quarterly(harmonise_counts(raw["population"]), win)
    pop_code = pop_code.rename(columns={"value": "population", "extrapolated": "pop_extrapolated"})
    pop_code = pop_code[["code", "t", "population", "pop_extrapolated"]]
    pop_comp = population_quarterly(existence_rule(full_unit_rule(raw["population"])), win)
    weights = pop_comp.rename(columns={"value": "w"})[["code", "component", "year", "idx", "w"]]
    weights_annual = (pop_comp.groupby(["code", "component", "year"])["value"].mean()
                      .rename("w").reset_index().assign(idx=1))

    # births: quarterly (cumulative Jan-X is differenced after harmonising)
    b = cumulative_to_period(harmonise_counts(raw["births"]))
    births = to_quarterly(b, "sum")[["code", "t", "value"]].rename(columns={"value": "births"})

    panel = pop_code.merge(births, on=["code", "t"], how="outer")

    # quarterly CPI: weighted price change across components, then chained
    annual_cpi = None
    if "cpi" in raw:
        c = raw["cpi"]
        qq = c[c.kind == "Q"]
        if not qq.empty:
            h = harmonise_weighted(qq, weights)
            h["t"] = h["year"] * 4 + h["idx"] - 1
            lvl = chain_index(h)[["code", "t", "value"]].rename(columns={"value": "cpi"})
            panel = panel.merge(lvl, on=["code", "t"], how="left")
            lvl["year"] = lvl["t"] // 4
            annual_cpi = lvl.groupby(["code", "year"])["cpi"].agg(["mean", "count"]).reset_index()
            annual_cpi = annual_cpi[annual_cpi["count"] == 4].rename(columns={"mean": "cpi_avg"})

    # annual series -> annual drivers dated at publication
    annual_pop = pop_code.assign(year=pop_code.t // 4).groupby(["code", "year"])["population"].agg(["mean", "count"])
    annual_pop = annual_pop[annual_pop["count"] == 4]["mean"].rename("pop_avg").reset_index()
    drivers = []
    if "marriages" in raw:
        mr = harmonise_counts(raw["marriages"])
        mr = mr[mr.kind == "A"][["code", "year", "value"]].rename(columns={"value": "marriages"})
        mr = mr.merge(annual_pop, on=["code", "year"], how="inner").sort_values(["code", "year"])
        mr["marriage_rate"] = 1000 * mr["marriages"] / mr["pop_avg"]
        mr["m"] = log_yoy(mr["marriage_rate"], mr["code"], k=1)
        drivers.append(annual_to_publication_quarters(mr, "m"))
        drivers.append(annual_to_publication_quarters(mr, "marriage_rate"))
    if "income" in raw and annual_cpi is not None:
        inc = harmonise_weighted(raw["income"][raw["income"].kind == "A"], weights_annual)
        inc = inc[["code", "year", "value"]].rename(columns={"value": "income"})
        inc = inc.merge(annual_cpi[["code", "year", "cpi_avg"]], on=["code", "year"], how="inner").sort_values(["code", "year"])
        inc["w"] = log_yoy(inc["income"], inc["code"], k=1) - log_yoy(inc["cpi_avg"], inc["code"], k=1)
        drivers.append(annual_to_publication_quarters(inc, "w"))
    if "housing_pc" in raw:
        hp = harmonise_weighted(raw["housing_pc"][raw["housing_pc"].kind == "A"], weights_annual)
        hp = hp[["code", "year", "value"]].rename(columns={"value": "housing_pc"}).sort_values(["code", "year"])
        hp["h"] = log_yoy(hp["housing_pc"], hp["code"], k=1)
        drivers.append(annual_to_publication_quarters(hp, "h"))
    if "unemployment" in raw:
        u = harmonise_weighted(raw["unemployment"], weights)
        uq = to_quarterly(u, "mean")[["code", "t", "value"]].rename(columns={"value": "unemployment"})
        panel = panel.merge(uq, on=["code", "t"], how="left")
    for d in drivers:
        panel = panel.merge(d, on=["code", "t"], how="left")

    panel = panel[panel.code.isin(REGIONS)]
    # full rectangular grid so a lag of k is always exactly k quarters back
    has_births = panel.dropna(subset=["births"])
    t0, t1 = int(has_births.t.min()), int(has_births.t.max())
    grid = pd.MultiIndex.from_product([sorted(REGIONS), range(t0 - 8, t1 + 2)], names=["code", "t"]).to_frame(index=False)
    panel = grid.merge(panel, on=["code", "t"], how="left").sort_values(["code", "t"]).reset_index(drop=True)
    panel["quarter"] = (panel.t // 4).astype(str) + "Q" + (panel.t % 4 + 1).astype(str)

    by = panel["code"]
    panel["cbr"] = annualised_rate(panel["births"], panel["population"])
    panel["y"] = log_yoy(panel["cbr"], by)
    panel["y_births"] = log_yoy(panel["births"], by)
    if "unemployment" in panel:
        panel["u"] = diff_yoy(panel["unemployment"], by)
    # keep from the first quarter with any births up to one quarter past the last
    panel = panel[panel.t.between(t0, t1 + 1)]
    panel["pop_extrapolated"] = panel["pop_extrapolated"].fillna(False).astype(bool)

    os.makedirs(out_dir, exist_ok=True)
    cols = ["code", "quarter", "t", "births", "population", "pop_extrapolated", "cbr", "marriage_rate", "cpi",
            "unemployment", "y", "y_births", "m", "w", "u", "h"]
    cols = [c for c in cols if c in panel.columns]
    panel[cols].to_csv(os.path.join(out_dir, "panel.csv"), index=False, float_format="%.10g", lineterminator="\n")
    first_extrap = panel[panel.pop_extrapolated].quarter.min() if panel.pop_extrapolated.any() else None
    meta = {
        "regions": REGIONS,
        "sources": [{k: e.get(k) for k in ("series", "file", "publisher", "url", "identifier",
                                           "retrieved", "revised", "synthetic", "used_as")} for e in manifest],
        "synthetic": any(e.get("synthetic") for e in manifest),
        "first_quarter": panel.quarter.iloc[0],
        "last_quarter": panel.dropna(subset=["cbr"]).quarter.max(),
        "population_projected_from": first_extrap,
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
