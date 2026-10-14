import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calcaudit.ingest import load_document
from calcaudit.rules import load_cards, run_all


def rules(spec, text="\\begin{equation}\\label{E1} v = k i \\end{equation}\n"):
    d = tempfile.mkdtemp()
    f = os.path.join(d, "d.tex")
    open(f, "w").write(text)
    open(os.path.join(d, "d.calcaudit.json"), "w").write(json.dumps({"glossary": {"v": "m/s", "k": "m/s", "i": "1"}, **spec}))
    rep = run_all(load_document(f), load_cards())
    return {f.rule + ":" + f.outcome.value: f for f in rep.findings}


class ClaimsTest(unittest.TestCase):
    def test_range(self):
        r = rules({"claims": [{"type": "range", "quantity": "Cc", "value": "4.5", "text": "Cc was 4.5"},
                              {"type": "range", "quantity": "phi", "value": "30 deg", "text": "phi 30"}]})
        self.assertIn("T01:violated", r)
        self.assertIn("T01:verified", r)

    def test_range_unit_aware(self):
        r = rules({"claims": [{"type": "range", "quantity": "k", "value": "5e-3 mm/s", "text": "k"}]})
        self.assertIn("T01:verified", r)

    def test_trend_contradiction(self):
        r = rules({"claims": [{"type": "trend", "card": "darcy_law", "dependent": "v", "independent": "i",
                               "direction": "decreases", "text": "v falls as gradient rises"}]})
        self.assertIn("T02:violated", r)

    def test_trend_supported(self):
        r = rules({"claims": [{"type": "trend", "card": "hydrostatic_pressure", "dependent": "p",
                               "independent": "h", "direction": "increases", "text": "p rises with depth"}]})
        self.assertIn("T02:verified", r)

    def test_validity_limit(self):
        r = rules({"claims": [{"type": "validity", "card": "darcy_law", "conditions": {"Re": 500}, "text": "Darcy at Re 500"}]})
        self.assertIn("T03:violated", r)

    def test_absolute_wording(self):
        r = rules({}, text="The method always works in every soil.\n\\begin{equation}v = k i\\end{equation}")
        self.assertIn("T04:violated", r)


if __name__ == "__main__":
    unittest.main()
