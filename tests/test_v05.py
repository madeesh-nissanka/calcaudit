import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calcaudit.ingest import load_document
from calcaudit.rules import load_cards, run_all


def run(text, spec=None):
    d = tempfile.mkdtemp()
    f = os.path.join(d, "d.md")
    open(f, "w").write(text)
    open(os.path.join(d, "d.calcaudit.json"), "w").write(json.dumps(spec or {}))
    return {x.rule for x in run_all(load_document(f), load_cards()).findings if x.outcome.value == "violated"}


class ArgumentTest(unittest.TestCase):
    def test_two_values(self):
        self.assertIn("A01", run("For the first test k = 1e-6 m/s.\n\nLater the permeability k = 3e-6 m/s was used."))

    def test_same_value_ok(self):
        self.assertNotIn("A01", run("k = 1e-6 m/s here.\n\nAnd again k = 1e-6 m/s there."))

    def test_certainty_without_uncertainty(self):
        self.assertIn("A02", run("This clearly demonstrates the model is right."))
        self.assertNotIn("A02", run("This clearly demonstrates the trend, within the stated tolerance."))

    def test_correlation_causation(self):
        self.assertIn("A03", run("The settlement correlates with the load, which is due to creep."))

    def test_single_case_generalised(self):
        self.assertIn("A05", run("A single test was run. The result is generally valid for all soils."))

    def test_fit_and_validate_same_data(self):
        self.assertIn("A04", run("text", {"fits": [{"signal": "s", "fitted_on": "D1", "validated_on": "D1", "mare_pct": 5}]}))
        self.assertNotIn("A04", run("text", {"fits": [{"signal": "s", "fitted_on": "D1", "validated_on": "D2", "mare_pct": 5}]}))

    def test_claim_without_evidence(self):
        self.assertIn("A06", run("text", {"claims": [{"id": "c", "type": "general", "text": "the design is safe"}]}))


if __name__ == "__main__":
    unittest.main()
