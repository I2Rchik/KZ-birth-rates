"""SYNTHETIC TEST FIXTURE - NOT REAL DATA.

Generates raw files in the same formats as the real Taldau downloads:
  * gzip "data.csv" long tables (NAM/DAT/PERIOD/KATO/SPTM/VAL) with districts,
    towns, villages and the national total mixed in, the old South Kazakhstan
    region before 2018, Shymkent listed as a town before 2018, and the 2022
    regions (Abai, Zhetisu, Ulytau);
  * a quarterly CPI "download.xls" HTML table.
Every file is flagged "synthetic": true; the website then shows a red TEST
DATA banner. Never copy these files into data/raw.
"""
import gzip
import hashlib
import json
import os
import sys

import numpy as np

MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль",
          "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
REG = ["АКМОЛИНСКАЯ ОБЛАСТЬ", "АКТЮБИНСКАЯ ОБЛАСТЬ", "АЛМАТИНСКАЯ ОБЛАСТЬ", "АТЫРАУСКАЯ ОБЛАСТЬ",
       "ЗАПАДНО-КАЗАХСТАНСКАЯ ОБЛАСТЬ", "ЖАМБЫЛСКАЯ ОБЛАСТЬ", "КАРАГАНДИНСКАЯ ОБЛАСТЬ",
       "КОСТАНАЙСКАЯ ОБЛАСТЬ", "КЫЗЫЛОРДИНСКАЯ ОБЛАСТЬ", "МАНГИСТАУСКАЯ ОБЛАСТЬ", "ТУРКЕСТАНСКАЯ ОБЛАСТЬ",
       "ПАВЛОДАРСКАЯ ОБЛАСТЬ", "СЕВЕРО-КАЗАХСТАНСКАЯ ОБЛАСТЬ", "ВОСТОЧНО-КАЗАХСТАНСКАЯ ОБЛАСТЬ",
       "Г.АСТАНА", "Г.АЛМАТЫ", "Г.ШЫМКЕНТ", "ОБЛАСТЬ АБАЙ", "ОБЛАСТЬ ЖЕТІСУ", "ОБЛАСТЬ ҰЛЫТАУ"]
SPLIT = {"Г.ШЫМКЕНТ": ("ТУРКЕСТАНСКАЯ ОБЛАСТЬ", (2018, 6), 0.35),
         "ОБЛАСТЬ АБАЙ": ("ВОСТОЧНО-КАЗАХСТАНСКАЯ ОБЛАСТЬ", (2022, 8), 0.45),
         "ОБЛАСТЬ ЖЕТІСУ": ("АЛМАТИНСКАЯ ОБЛАСТЬ", (2022, 8), 0.33),
         "ОБЛАСТЬ ҰЛЫТАУ": ("КАРАГАНДИНСКАЯ ОБЛАСТЬ", (2022, 8), 0.15)}
NOISE = ["Г.АКТОБЕ", "АКСУ Г.А.", "АБАЙСКИЙ РАЙОН", "С.АБАЙ", "Г.А.АЛАТАУ"]  # must be ignored


def make(out_dir, start=2014, end=(2026, 6), seed=7):
    rng = np.random.default_rng(seed)
    os.makedirs(out_dir, exist_ok=True)
    parents = [r for r in REG if r not in SPLIT]
    months = [(y, m) for y in range(start - 3, end[0] + 1) for m in range(1, 13) if (y, m) <= end]
    n = len(months)
    pop0 = {r: rng.uniform(0.6, 2.2) * 1e6 for r in parents}
    cbr0 = {r: rng.uniform(15, 27) for r in parents}
    years = sorted({y for y, _ in months})
    marr = {r: {y: cbr0[r] * 0.45 * np.exp(rng.normal(0, 0.05)) for y in years} for r in parents}
    births_m = {}
    for r in parents:
        level = cbr0[r] * np.exp(np.cumsum(rng.normal(-0.002, 0.01, n)))
        b = []
        for i, (y, m) in enumerate(months):
            lag = marr[r].get(y - 1, marr[r][years[0]])
            season = 1 + 0.08 * np.sin(2 * np.pi * (m - 3) / 12)
            b.append(level[i] * (lag / (cbr0[r] * 0.45)) ** 0.3 * season * pop0[r] / 12000 * np.exp(rng.normal(0, 0.03)))
        births_m[r] = b

    def share(region, y, m=12):
        """Share of the parent's flow/stock that a current region reports."""
        if region in SPLIT:
            par, (ys, ms), s = SPLIT[region]
            return s if (y, m) >= (ys, ms) else 0.0
        kids = [k for k, v in SPLIT.items() if v[0] == region and (y, m) >= v[1]]
        return 1 - sum(SPLIT[k][2] for k in kids)

    def parent(region):
        return SPLIT[region][0] if region in SPLIT else region

    def name_at(region, y, m):
        if region == "ТУРКЕСТАНСКАЯ ОБЛАСТЬ" and (y, m) < (2018, 6):
            return "ЮЖНО-КАЗАХСТАНСКАЯ ОБЛАСТЬ"
        return region

    def gz(fname, nam, rows, sptm=True):
        head = ['"NAM"', '"DAT"', '"PERIOD"', '"КАТО(по каталогу)"', '"LКАТО(по каталогу)"']
        head += ['"СПТМ (по каталогу)"', '"LСПТМ (по каталогу)"'] if sptm else []
        lines = ["\t".join(head + ['"VAL"'])]
        for dat, per, reg, val in rows:
            for kind in (["Всего", "городская местность"] if sptm else [None]):
                v = val if kind != "городская местность" else val * 0.6
                cells = [nam, dat, per, reg, "0"] + ([kind, "0"] if sptm else []) + [f"{v:,.1f}".replace(",", " ")]
                lines.append("\t".join(f'"{c}"' for c in cells))
        path = os.path.join(out_dir, fname)
        with open(path, "wb") as f:
            f.write(gzip.compress("\n".join(lines).encode("utf-8")))
        return path

    files = {}
    # births: cumulative January-quarter end, 2014 onwards, Jan-Jun 2022 missing (as in Taldau)
    rows = []
    for y in range(start, end[0] + 1):
        for q in range(1, 5):
            mend = 3 * q
            if (y, mend) > end or (y, mend) == (2022, 6):
                continue
            for r in REG:
                s = share(r, y, mend)
                if s == 0:
                    continue
                tot = sum(births_m[parent(r)][months.index((y, mm))] for mm in range(1, mend + 1))
                rows.append((f"Январь - {MONTHS[mend - 1]} {y} г. (кв.)", f"{y}{mend:02d}", name_at(r, y, mend), round(tot * s)))
            rows.append((f"Январь - {MONTHS[mend - 1]} {y} г. (кв.)", f"{y}{mend:02d}", "Г.А.АЛАТАУ", 400))
    files["births"] = gz("births.csv.gz", "Число родившихся (живыми)(Человек)", rows)
    # population: start of month, ends Jan 2024; Shymkent also listed as a town before 2018
    rows = []
    for i, (y, m) in enumerate(months):
        if (y, m) > (2024, 1):
            break
        for r in REG:
            s = share(r, y, m)
            if s == 0:
                if r == "Г.ШЫМКЕНТ" and y >= 2017:
                    rows.append((f"{MONTHS[m - 1]} {y} г.", f"{y}{m:02d}", r, pop0[parent(r)] * 0.35))
                continue
            rows.append((f"{MONTHS[m - 1]} {y} г.", f"{y}{m:02d}", name_at(r, y, m), pop0[parent(r)] * 1.012 ** (i / 12) * s))
        for nz in NOISE:
            rows.append((f"{MONTHS[m - 1]} {y} г.", f"{y}{m:02d}", nz, 50000))
    files["population"] = gz("population.csv.gz", "Численность населения на начало периода(Человек)", rows)

    def annual(fname, nam, fn, sptm=True):
        rws = []
        for y in years[:-1]:
            for r in REG:
                s = share(r, y)
                if s:
                    rws.append((f"{y} год", f"{y}12", name_at(r, y, 12), fn(r, y, s)))
        return gz(fname, nam, rws, sptm)
    files["marriages"] = annual("marriages.csv.gz", "Число зарегистрированных браков(Человек)",
                                lambda r, y, s: marr[parent(r)][y] * pop0[parent(r)] / 1000 * s)
    files["income"] = annual("income.csv.gz", "Среднедушевые номинальные денежные доходы населения(Тенге казахский)",
                             lambda r, y, s: 50000 * 1.1 ** (y - start) * rng.uniform(0.95, 1.05), sptm=False)
    files["housing_pc"] = annual("housing.csv.gz", "Обеспеченность жильем на одного проживающего(Метр квадратный)",
                                 lambda r, y, s: 20 + 0.3 * (y - start) + rng.normal(0, 0.2))
    # CPI: quarterly, previous quarter = 100, HTML table like Taldau's download.xls
    quarters = [(y, q) for y in range(start - 3, end[0] + 1) for q in range(1, 5) if (y, 3 * q) <= end]
    th = "".join(f"<th>{r}</th>" for r in REG for _ in quarters)
    tq = "".join(f"<th>{q} квартал {y} г.</th>" for _ in REG for y, q in quarters)
    td = "".join(f"<td>{100 + rng.normal(2, 0.7):.1f}</td>" if share(r, y, 3 * q) else "<td></td>"
                 for r in REG for y, q in quarters)
    html = (f"<html><body><table><thead><tr><th>Показатели</th>{th}</tr><tr><th>Даты</th>{tq}</tr></thead>"
            f"<tbody><tr><td>Индекс потребительских цен(Процент)</td>{td}</tr></tbody></table></body></html>")
    files["cpi"] = os.path.join(out_dir, "cpi.xls")
    with open(files["cpi"], "w", encoding="utf-8") as f:
        f.write(html)

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
