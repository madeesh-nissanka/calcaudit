import csv
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calcaudit.ingest import load_document
from calcaudit.model import Report
from calcaudit.packs import series, soil
from calcaudit.prose import assignments, infer_symbols
from calcaudit.rules import load_cards, run_all


class ProseTest(unittest.TestCase):
    def test_assignments_skip_products(self):
        a = assignments("With k = 1e-6 m/s and i = 0.5, v = 1.0e-6 m/s. Also 2 k i.")
        self.assertEqual(set(a), {"k", "i", "v"})

    def test_times_ten_notation(self):
        self.assertEqual(assignments(r"k = 1.5 \times 10^{-7} m/s")["k"][0], "1.5e-7")

    def test_where_clause_units(self):
        s = infer_symbols("where $H$ is the layer thickness, and $t$ is the elapsed time (s).")
        self.assertIn("H", s)
        self.assertEqual(s["t"][0], "s")


class ExtractionTest(unittest.TestCase):
    def test_calculation_from_prose(self):
        p = tempfile.mkdtemp()
        f = os.path.join(p, "d.tex")
        open(f, "w").write("\\begin{equation}\\label{a} v = k i \\end{equation}\n\n"
                           "where $v$ is the velocity (m/s), $k$ is the permeability (m/s) and $i$ is the gradient (-).\n\n"
                           "For k = 1e-6 m/s and i = 0.5 the velocity is v = 5e-6 m/s.")
        rep = run_all(load_document(f), load_cards())
        e01 = [x for x in rep.findings if x.rule == "E01"]
        self.assertEqual(len(e01), 1)
        self.assertEqual(e01[0].outcome.value, "violated")
        self.assertIn("10^1", e01[0].message)


class SoilTest(unittest.TestCase):
    def run_pack(self, params):
        rep = Report("t")
        soil.run({k: (str(v[0]), v[1]) for k, v in params.items()}, rep)
        return {f.rule: f for f in rep.findings}

    def test_cc_below_cr(self):
        r = self.run_pack({"Cc": (0.04, ""), "Cr": (0.09, "")})
        self.assertEqual(r["P03"].outcome.value, "violated")

    def test_saturation_above_one(self):
        r = self.run_pack({"e0": (0.6, ""), "Gs": (2.7, ""), "w": (40, "%")})
        self.assertEqual(r["P01"].outcome.value, "violated")
        self.assertEqual(r["P01"].severity.value, "serious")

    def test_permeability_unit_slip(self):
        r = self.run_pack({"k": (3.0, "m/s")})
        self.assertEqual(r["P06"].outcome.value, "violated")
        self.assertIn("m/year", r["P06"].evidence)

    def test_ocr_and_lambda_factor(self):
        r = self.run_pack({"OCR": (0.5, ""), "Cc": (0.5, ""), "lambda": (0.5, "")})
        self.assertEqual(r["P05"].outcome.value, "violated")
        self.assertEqual(r["P04"].outcome.value, "violated")


class SeriesTest(unittest.TestCase):
    def make(self, rows, **kw):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "s.csv")
        with open(p, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["t", "u", "sig"])
            w.writerows(rows)
        rep = Report("t")
        series.run({"name": "S", "path": p, "time": "t", "columns": {"u": "kPa"},
                    "bounded_by": [{"value": "u", "limit": "sig"}], **kw}, __import__("pathlib").Path(d), rep)
        return {f.rule + ":" + f.outcome.value for f in rep.findings}

    def test_clean_series(self):
        rows = [(i, 50 + 0.37 * i + (i % 3) * 0.11, 200) for i in range(40)]
        self.assertTrue(all(r.endswith("verified") for r in self.make(rows)))

    def test_frozen_sensor_and_bound(self):
        rows = [(i, 50 + 0.4 * i, 200) for i in range(15)] + [(i, 56.0, 200) for i in range(15, 40)]
        rows[5] = (5, 210, 200)
        out = self.make(rows)
        self.assertIn("F02:violated", out)
        self.assertIn("F03:violated", out)

    def test_time_reversal(self):
        rows = [(i, 50 + 0.4 * i, 200) for i in range(20)]
        rows[10] = (3, 54, 200)
        self.assertIn("F01:violated", self.make(rows))


if __name__ == "__main__":
    unittest.main()
