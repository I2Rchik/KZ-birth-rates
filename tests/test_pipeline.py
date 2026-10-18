"""Automated tests, including the parts of the acceptance test that can be automated.

They run on a SYNTHETIC fixture (tests/fixtures/make_synthetic.py) in a
temporary folder, so they never touch data/raw, data/processed or model/.
Run:  python run.py test
"""
import filecmp
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests", "fixtures"))

import app  # noqa: E402
import econometrics as ec  # noqa: E402
import ingest  # noqa: E402
import make_synthetic  # noqa: E402
import model  # noqa: E402
from periods import parse_period  # noqa: E402
from regions import region_code  # noqa: E402


class Transforms(unittest.TestCase):
    def test_periods(self):
        cases = {"январь 2015": ("M", 2015, 1), "Март 2020 г.": ("M", 2020, 3), "май 2019": ("M", 2019, 5),
                 "2015 Q3": ("Q", 2015, 3), "Q4 2021": ("Q", 2021, 4), "2 квартал 2018": ("Q", 2018, 2),
                 "IV квартал 2016": ("Q", 2016, 4), "январь-март 2025": ("CUM", 2025, 3),
                 "2014-07": ("M", 2014, 7), "на 1 января 2012 г.": ("M", 2012, 1), "2013": ("A", 2013, 1)}
        for label, want in cases.items():
            self.assertEqual(parse_period(label), want, label)

    def test_regions(self):
        self.assertEqual(region_code("Алматинская область"), ("ALM", "ALM"))
        self.assertEqual(region_code("г. Алматы"), ("ALA", "ALA"))
        self.assertEqual(region_code("Жетісу"), ("ALM", "ZHETISU"))
        self.assertEqual(region_code("Абай облысы"), ("EKO", "ABAI"))
        self.assertEqual(region_code("г.Шымкент"), ("TUR", "SHYMKENT"))
        self.assertEqual(region_code("Западно-Казахстанская"), ("WKO", "WKO"))
        self.assertEqual(region_code("Республика Казахстан"), (None, None))
        self.assertEqual(region_code("Nur-Sultan city"), ("AST", "AST"))

    def test_quarterly_sum_needs_three_months(self):
        df = pd.DataFrame({"code": "AKM", "component": "AKM", "kind": "M", "year": 2020,
                           "idx": [1, 2, 3, 4, 5], "value": [1.0, 2.0, 3.0, 4.0, 5.0]})
        q = ingest.to_quarterly(df, "sum").set_index("quarter")["value"]
        self.assertEqual(q["2020Q1"], 6.0)
        self.assertTrue(np.isnan(q["2020Q2"]))  # only two months: not a full quarter

    def test_cumulative_to_quarter(self):
        df = pd.DataFrame({"code": "AKM", "component": "AKM", "kind": "CUM", "year": 2025,
                           "idx": [3, 6], "value": [100.0, 230.0]})
        q = ingest.to_quarterly(ingest.cumulative_to_monthly(df), "sum").set_index("quarter")["value"]
        self.assertEqual(q["2025Q1"], 100.0)
        self.assertEqual(q["2025Q2"], 130.0)

    def test_chain_index(self):
        df = pd.DataFrame({"code": "AKM", "component": "AKM", "kind": "M", "year": 2020,
                           "idx": [1, 2, 3], "value": [101.0, 102.0, 100.0]})
        out = ingest.chain_index(df, "previous_period")["value"].to_numpy()
        np.testing.assert_allclose(out, [101.0, 103.02, 103.02])

    def test_harmonisation_sums_components_once_they_exist(self):
        q = pd.DataFrame({"code": ["EKO"] * 4, "component": ["EKO", "EKO", "ABAI", "ABAI"],
                          "quarter": ["2022Q2", "2022Q3", "2022Q2", "2022Q3"], "value": [10.0, 6.0, np.nan, 4.0]})
        h = ingest.harmonise_sum(q).set_index("quarter")["value"]
        self.assertEqual(h["2022Q2"], 10.0)  # Abai did not exist yet
        self.assertEqual(h["2022Q3"], 10.0)  # 6 + 4

    def test_ols_recovers_known_coefficients(self):
        rng = np.random.default_rng(1)
        g = np.repeat(np.arange(10), 50)
        t = np.tile(np.arange(50), 10)
        X = rng.standard_normal((500, 2))
        y = 3 * (g % 3) + X @ np.array([0.5, -1.0]) + 0.1 * rng.standard_normal(500)
        r = ec.panel_fe(X, y, g, t, ["a", "b"])
        np.testing.assert_allclose(r["beta"], [0.5, -1.0], atol=0.03)

    def test_adf_kpss_behave(self):
        rng = np.random.default_rng(2)
        rw = np.cumsum(rng.standard_normal(80))
        wn = rng.standard_normal(80)
        self.assertGreater(ec.adf(rw, rng=rng)["pvalue"], 0.05)
        self.assertLess(ec.adf(wn, rng=rng)["pvalue"], 0.05)
        self.assertGreater(ec.kpss(wn, rng=rng)["pvalue"], 0.05)


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="kzb_")
        cls.raw = os.path.join(cls.tmp, "data", "raw")
        cls.proc = os.path.join(cls.tmp, "data", "processed")
        make_synthetic.make(cls.raw)
        ingest.build(cls.raw, cls.proc)
        cls.art = model.run(cls.proc, os.path.join(cls.tmp, "model"), os.path.join(cls.tmp, "outputs"),
                            make_figures=False)
        cls.panel = pd.read_csv(os.path.join(cls.proc, "panel.csv"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_rebuild_is_byte_identical(self):
        other = os.path.join(self.tmp, "processed2")
        ingest.build(self.raw, other)
        for f in ("panel.csv", "meta.json"):
            self.assertTrue(filecmp.cmp(os.path.join(self.proc, f), os.path.join(other, f), shallow=False), f)

    def test_edited_raw_file_is_refused(self):
        bad = os.path.join(self.tmp, "raw_edit")
        shutil.copytree(self.raw, bad)
        with open(os.path.join(bad, "births_monthly.xlsx"), "ab") as f:
            f.write(b"x")
        with self.assertRaises(ingest.DataError):
            ingest.build(bad, os.path.join(self.tmp, "p_bad"))

    def test_forecast_ignores_the_future(self):
        """Changing anything dated t* or later must not change the forecast for t*,
        nor the coefficients estimated on data up to t*-1."""
        cfg = json.load(open(os.path.join(ROOT, "src", "config.json")))["model"]
        spec = {"dep": "y", "level": "cbr", "own_lags": cfg["own_lags"], "drivers": cfg["drivers"]}
        p0 = model.add_lags(self.panel, spec)
        t_star = int(p0.t.max()) - 6
        d0, names = model.design(p0, spec, t_max=t_star - 1)
        r0 = model.fit(d0, names, "y")
        rows0 = p0[p0.t == t_star].dropna(subset=names)
        f0 = model.predict(r0, rows0, names)

        future = self.panel.copy()
        rng = np.random.default_rng(3)
        mask = future.t >= t_star
        for c in ("y", "m", "w", "u", "h", "cbr"):
            future.loc[mask, c] = rng.normal(5, 3, mask.sum())
        p1 = model.add_lags(future, spec)
        d1, _ = model.design(p1, spec, t_max=t_star - 1)
        r1 = model.fit(d1, names, "y")
        rows1 = p1[p1.t == t_star].dropna(subset=names)
        f1 = model.predict(r1, rows1, names)
        np.testing.assert_allclose(r0["beta"], r1["beta"])
        np.testing.assert_allclose(f0, f1)

    def test_artifact_has_required_contents(self):
        a = self.art
        for k in ("coefficients", "std_errors", "covariance", "estimated_at", "diagnostic_flags", "benchmark"):
            self.assertIn(k, a)
        self.assertIn("sample_window", a["specification"])
        self.assertTrue(a["synthetic_data"])
        k = len(a["specification"]["regressors"])
        self.assertEqual(np.array(a["covariance"]).shape, (k, k))

    def test_contributions_match_coefficients_times_data(self):
        """Acceptance check 5, automated: three driver contributions = beta x value."""
        a = self.art
        fc = a["forecast"]["AKM"]
        names = a["specification"]["regressors"]
        for nm in [n for n in names if not n.startswith("y_")][:3]:
            j = names.index(nm)
            self.assertAlmostEqual(fc["contributions"][nm], a["coefficients"][nm] * fc["x"][j], places=12)
        total = sum(fc["contributions"].values()) + fc["region_effect"]
        self.assertAlmostEqual(total, fc["yhat"], places=10)

    def test_missing_model_message(self):
        """Acceptance check 8, automated."""
        root = os.path.join(self.tmp)
        os.rename(os.path.join(root, "model", "artifact.json"), os.path.join(root, "model", "artifact.bak"))
        try:
            s = app.state(root)
            self.assertFalse(s["ok"])
            self.assertIn("missing_model", [e["code"] for e in s["errors"]])
            self.assertIn("model is missing", s["errors"][0]["message"])
        finally:
            os.rename(os.path.join(root, "model", "artifact.bak"), os.path.join(root, "model", "artifact.json"))

    def test_server_serves_fast(self):
        """Acceptance checks 2-4: the page and its data are served in well under 3 seconds."""
        httpd = app.serve(port=0, root=self.tmp, check=False)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        try:
            t0 = time.time()
            html = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
            js = urllib.request.urlopen(f"http://127.0.0.1:{port}/app.js").read()
            st = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state").read())
            self.assertLess(time.time() - t0, 3.0)
            self.assertIn("Headline", html)
            self.assertTrue(js)
            self.assertTrue(st["ok"], st.get("errors"))
        finally:
            httpd.shutdown()

    def test_no_headline_literal_in_presentation_layer(self):
        """Acceptance check 9, automated."""
        v = self.art["national"]["latest"]["value"]
        text = "".join(open(os.path.join(ROOT, "src", p), encoding="utf-8").read()
                       for p in ("app.py", "static/app.js", "static/index.html"))
        for s in (f"{v:.1f}", f"{v:.2f}", f"{v:.3f}"):
            self.assertNotIn(s, text)
        self.assertNotIn("lstsq", text)  # no regression in the presentation layer


class Repository(unittest.TestCase):
    def test_no_credentials(self):
        """Acceptance check 10 (working tree part). Run the git-history scan in the README too."""
        pat = re.compile(r"(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"][^'\"]{6,}|BEGIN (RSA|OPENSSH) PRIVATE KEY",
                         re.I)
        for d, _, files in os.walk(ROOT):
            if ".git" in d or "__pycache__" in d:
                continue
            for f in files:
                if f.endswith((".py", ".js", ".json", ".md", ".txt", ".html", ".cfg", ".env")):
                    with open(os.path.join(d, f), encoding="utf-8", errors="ignore") as fh:
                        self.assertIsNone(pat.search(fh.read()), os.path.join(d, f))


if __name__ == "__main__":
    unittest.main()
