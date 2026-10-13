import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calcaudit import mutate
from calcaudit.expr import ParseError, dim_eval, equivalent, evaluate, parse_equation, parse_expr
from calcaudit.ingest import load_document
from calcaudit.rules import load_cards, run_all
from calcaudit.units import ONE, UnitError, parse_unit, value_with_unit


class UnitsTest(unittest.TestCase):
    def test_compound(self):
        d, f = parse_unit("kN/m^2")
        d2, f2 = parse_unit("kPa")
        self.assertEqual(d, d2)
        self.assertAlmostEqual(f, f2)

    def test_exponent_forms(self):
        self.assertEqual(parse_unit("m3/s")[0], parse_unit("m^3/s")[0])
        self.assertEqual(parse_unit("kg/(m·s^2)")[0], parse_unit("Pa")[0])

    def test_per_year_factor(self):
        self.assertAlmostEqual(parse_unit("m/yr")[1], 1 / 31557600.0)

    def test_unknown_unit(self):
        with self.assertRaises(UnitError):
            parse_unit("furlong")

    def test_value(self):
        v, d, _ = value_with_unit("5 mm")
        self.assertAlmostEqual(v, 0.005)


class ExprTest(unittest.TestCase):
    def test_precedence(self):
        self.assertAlmostEqual(evaluate(parse_expr("2 + 3 * 4 ^ 2"), {}), 50)

    def test_frac_and_subscript(self):
        e = parse_expr(r"\frac{c_v t}{H_{dr}^2}", {"c_v", "t", "H_dr"})
        self.assertAlmostEqual(evaluate(e, {"c_v": 2, "t": 3, "H_dr": 2}), 1.5)

    def test_equivalence_levels(self):
        a = parse_expr("k i")
        self.assertEqual(equivalent(a, parse_expr("i k"))[0], "equal")
        self.assertEqual(equivalent(a, parse_expr("3 k i"))[0], "factor")
        self.assertEqual(equivalent(a, parse_expr("k + i"))[0], "different")

    def test_bad_equation(self):
        with self.assertRaises(ParseError):
            parse_equation("a + b")

    def test_dimension_issues(self):
        from calcaudit.units import PRESSURE
        issues = []
        dim_eval(parse_expr("sigma + epsilon"), {"sigma": PRESSURE, "epsilon": ONE}, issues)
        self.assertEqual(issues[0]["kind"], "sum")


class RulesTest(unittest.TestCase):
    def doc(self, eq, gl, **kw):
        p = tempfile.mkdtemp()
        f = os.path.join(p, "d.tex")
        open(f, "w").write("\\begin{equation}" + eq + "\\end{equation}")
        open(os.path.join(p, "d.calcaudit.json"), "w").write(json.dumps({"glossary": gl, **kw}))
        return load_document(f)

    def test_clean_equation_verified(self):
        d = self.doc("v = k i", {"v": "m/s", "k": "m/s", "i": "1"})
        rep = run_all(d, load_cards())
        self.assertEqual(rep.counts()["violated"], 0)
        self.assertGreaterEqual(rep.counts()["verified"], 2)

    def test_unit_error_found(self):
        d = self.doc("v = k i", {"v": "m/s", "k": "kPa", "i": "1"})
        self.assertGreater(run_all(d, load_cards()).counts()["violated"], 0)

    def test_unknown_symbol_is_not_checkable(self):
        d = self.doc("v = k i", {"v": "m/s"})
        c = run_all(d, load_cards()).counts()
        self.assertEqual(c["violated"], 0)
        self.assertGreater(c["not_checkable"], 0)

    def test_substitution_magnitude_hint(self):
        d = self.doc("v = k i", {"v": "m/s", "k": "m/s", "i": "1"},
                     calculations=[{"equation": "E1", "inputs": {"k": "1e-6 m/s", "i": "0.5"},
                                    "reported": {"v": "5e-6 m/s"}}])
        msgs = [f.message for f in run_all(d, load_cards()).findings if f.rule == "E01"]
        self.assertTrue(any("10^1" in m for m in msgs))

    def test_derivation_sign_flip(self):
        d = self.doc("a = b", {"a": "1", "b": "1"},
                     derivations=[{"id": "D", "steps": ["x = a + b", "x = -(a + b)"]}])
        msgs = [f.message for f in run_all(d, load_cards()).findings if f.rule == "V01"]
        self.assertTrue(any("sign flip" in m for m in msgs))


class IngestTest(unittest.TestCase):
    def test_docx_omml(self):
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
               'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><w:body><w:p><m:oMath>'
               '<m:r><m:t>v=</m:t></m:r><m:f><m:num><m:r><m:t>k</m:t></m:r></m:num><m:den><m:r><m:t>H</m:t></m:r>'
               '</m:den></m:f></m:oMath></w:p></w:body></w:document>')
        p = os.path.join(tempfile.mkdtemp(), "t.docx")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", xml)
        d = load_document(p)
        self.assertEqual(len(d.equations), 1)
        self.assertIn("\\frac{k}{H}", d.equations[0].text)

    def test_tex_blocks(self):
        p = os.path.join(tempfile.mkdtemp(), "t.tex")
        open(p, "w").write("text $$a = b$$ and \\begin{equation}c = d\\end{equation}")
        self.assertEqual(len(load_document(p).equations), 2)


class MutationTest(unittest.TestCase):
    def test_recall_and_clean(self):
        s = mutate.summary(mutate.run())
        caught, total = s["clean"]
        self.assertEqual(caught, total, "clean equations must not be flagged")
        for kind in ("unit_error", "extra_factor", "sign_flip", "wrong_exponent"):
            c, t = s[kind]
            self.assertGreaterEqual(c / t, 0.9, kind)


if __name__ == "__main__":
    unittest.main()
