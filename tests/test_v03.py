import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calcaudit.graph import Graph
from calcaudit.ingest import load_document
from calcaudit.rules import load_cards, run_all


def make(spec, text="\\begin{equation}\\label{E1} v = k i \\end{equation}\n", data=None):
    d = tempfile.mkdtemp()
    f = os.path.join(d, "d.tex")
    with open(f, "w") as fh:
        fh.write(text)
    if data:
        with open(os.path.join(d, "s.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["t", "u"])
            w.writerows(data)
    with open(os.path.join(d, "d.calcaudit.json"), "w") as fh:
        json.dump(spec, fh)
    return load_document(f)


BASE = {"glossary": {"v": "m/s", "k": "m/s", "i": "1"},
        "calculations": [{"id": "C1", "equation": "E1", "inputs": {"k": "1e-6 m/s", "i": "0.5"},
                          "reported": {"v": "5e-7 m/s"}}]}


class TraceTest(unittest.TestCase):
    def rules(self, spec, **kw):
        rep = run_all(make({**BASE, **spec}, **kw), load_cards())
        return {f.rule + ":" + f.outcome.value: f for f in rep.findings}

    def test_value_matches_calculation(self):
        r = self.rules({"reported": [{"label": "R1", "where": "Table 1", "value": "5e-7 m/s",
                                      "source": {"calculation": "C1"}}]})
        self.assertIn("D01:verified", r)

    def test_power_of_ten_slip(self):
        r = self.rules({"reported": [{"label": "R1", "where": "Table 1", "value": "5e-6 m/s",
                                      "source": {"calculation": "C1"}}]})
        self.assertIn("D02:violated", r)
        self.assertIn("10^1", r["D02:violated"].message)

    def test_sign_flip(self):
        r = self.rules({"reported": [{"label": "R", "where": "T", "value": "-5e-7 m/s", "source": {"calculation": "C1"}}]})
        self.assertIn("sign", r["D02:violated"].message)

    def test_no_source_is_not_checkable(self):
        r = self.rules({"reported": [{"label": "R", "where": "T", "value": "3 m"}]})
        self.assertIn("D01:not_checkable", r)

    def test_dataset_value(self):
        data = [(i, 10 + i) for i in range(10)]
        spec = {"datasets": [{"name": "S", "path": "s.csv", "time": "t", "columns": {"u": "kPa"}}],
                "reported": [{"label": "R", "where": "T", "value": "14 kPa",
                              "source": {"dataset": "S", "column": "u", "time": 4}},
                             {"label": "R2", "where": "T", "value": "140 kPa",
                              "source": {"dataset": "S", "column": "u", "time": 4}}]}
        rep = run_all(make({**BASE, **spec}, data=data), load_cards())
        out = {(f.object.split()[2], f.outcome.value) for f in rep.findings if f.rule.startswith("D0")}
        self.assertIn(("R", "verified"), out)
        self.assertIn(("R2", "violated"), out)


class CalibrationTest(unittest.TestCase):
    def test_good_fit_one_signal_poor_other(self):
        spec = {"fits": [{"signal": "settlement", "fitted": True, "mare_pct": 8},
                         {"signal": "pore pressure", "fitted": False, "mare_pct": 70}]}
        rep = run_all(make(spec), load_cards())
        self.assertTrue(any(f.rule == "C03" and f.outcome.value == "violated" for f in rep.findings))

    def test_two_signals_fitted(self):
        spec = {"fits": [{"signal": "a", "fitted": True, "mare_pct": 8}, {"signal": "b", "fitted": True, "mare_pct": 9}]}
        rep = run_all(make(spec), load_cards())
        self.assertTrue(any(f.rule == "C01" and f.outcome.value == "verified" for f in rep.findings))


class GraphTest(unittest.TestCase):
    def test_impact(self):
        doc = make({**BASE, "reported": [{"label": "R1", "where": "T", "value": "1 m/s",
                                          "source": {"calculation": "C1"}}]})
        hit = Graph(doc).impact("sym:k")
        self.assertIn("eq:E1", hit)
        self.assertIn("calc:C1", hit)
        self.assertIn("rep:R1", hit)

    def test_orphan(self):
        doc = make({**BASE, "reported": [{"label": "R9", "where": "T", "value": "1 m"}]})
        self.assertEqual(Graph(doc).orphans(), ["rep:R9"])


if __name__ == "__main__":
    unittest.main()
