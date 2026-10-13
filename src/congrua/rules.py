"""Rule packs U (units), E (equations), V (derivations)."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from .expr import (ParseError, UnknownSymbol, dim_eval, equivalent, evaluate, parse_equation, parse_expr,
                   symbols, to_str)
from .ingest import Document
from .model import Finding, Outcome, Report, Severity
from .units import UnitError, parse_unit, quantity_dim, value_with_unit

CARD_DIR = Path(__file__).parent / "cards"


def load_cards(extra: str | None = None) -> dict[str, dict]:
    cards = {}
    for d in [CARD_DIR] + ([Path(extra)] if extra else []):
        for f in sorted(d.glob("*.json")):
            c = json.loads(f.read_text(encoding="utf-8"))
            cards[c["id"]] = c
    return cards


def _known(doc: Document) -> set[str]:
    return set(doc.glossary)


# ----------------------------------------------------------------------------- U: units
def rule_units(doc: Document, rep: Report) -> None:
    try:
        dims = {k: parse_unit(v)[0] for k, v in doc.glossary.items()}
    except UnitError as e:
        rep.add(Finding("U00", Outcome.NOT_CHECKABLE, "glossary", f"glossary unit not readable: {e}",
                        reproduce="congrua units '<unit>'"))
        dims = {}
    for eq in doc.equations:
        obj = f"equation {eq.id}"
        if not eq.text:
            rep.add(Finding("U01", Outcome.NOT_CHECKABLE, obj, f"equation not readable ({eq.where})"))
            continue
        try:
            lhs, rhs = parse_equation(eq.text, _known(doc))
        except ParseError as e:
            rep.add(Finding("U01", Outcome.NOT_CHECKABLE, obj, f"could not parse: {e}", evidence=eq.text))
            continue
        unknown = sorted((symbols(lhs) | symbols(rhs)) - set(dims))
        if unknown:
            rep.add(Finding("U01", Outcome.NOT_CHECKABLE, obj,
                            "no unit given for: " + ", ".join(unknown), evidence=eq.text,
                            reproduce="add the symbols to the glossary"))
            continue
        issues: list[dict] = []
        dl = dim_eval(lhs, dims, issues)
        dr = dim_eval(rhs, dims, issues)
        trans = [i for i in issues if i["kind"] in ("transcendental", "exponent", "variable_exponent")]
        sums = [i for i in issues if i["kind"] == "sum"]
        bad = False
        if dl != dr:
            bad = True
            rep.add(Finding("U01", Outcome.VIOLATED, obj, "left and right side have different dimensions",
                            Severity.SERIOUS, observed=f"left {dl}, right {dr}", expected="equal dimensions",
                            evidence=eq.text, reproduce=f"congrua scan {doc.source}"))
        for i in sums:
            bad = True
            rep.add(Finding("U01", Outcome.VIOLATED, obj, "terms of a sum have different dimensions",
                            Severity.SERIOUS, observed=f"{i['left']} + {i['right']}", expected="equal dimensions",
                            evidence=i["where"]))
        for i in trans:
            bad = True
            what = {"transcendental": "argument of a function must be dimensionless",
                    "exponent": "exponent must be dimensionless",
                    "variable_exponent": "variable exponent on a dimensional base"}[i["kind"]]
            rep.add(Finding("U02", Outcome.VIOLATED, obj, what, Severity.SERIOUS, observed=i["dim"],
                            expected="1", evidence=i["where"]))
        if not bad:
            rep.add(Finding("U01", Outcome.VERIFIED, obj, f"dimensionally consistent ({dl})", evidence=eq.text))
    # U03: table headers
    for t in doc.tables:
        for col in t.get("columns", []):
            m = re.match(r"\s*(.+?)\s*\((.+)\)\s*$", col)
            obj = f"table {t.get('name', '?')}, column {col!r}"
            if not m:
                rep.add(Finding("U03", Outcome.NOT_CHECKABLE, obj, "header has no unit in parentheses"))
                continue
            q, u = m.group(1), m.group(2)
            expected = quantity_dim(q)
            if expected is None:
                rep.add(Finding("U03", Outcome.NOT_CHECKABLE, obj, f"quantity {q!r} not in the quantity table"))
                continue
            try:
                got = parse_unit(u)[0]
            except UnitError as e:
                rep.add(Finding("U03", Outcome.NOT_CHECKABLE, obj, f"unit not readable: {e}"))
                continue
            if got != expected:
                rep.add(Finding("U03", Outcome.VIOLATED, obj, "unit does not fit the quantity", Severity.REVIEW,
                                observed=f"{u} = {got}", expected=f"{q} = {expected}"))
            else:
                rep.add(Finding("U03", Outcome.VERIFIED, obj, "unit fits the quantity"))


# ----------------------------------------------------------------------------- E: equations
def _si_inputs(d: dict[str, str]) -> dict[str, float]:
    return {k: value_with_unit(v)[0] for k, v in d.items()}


def _magnitude_hint(ratio: float) -> str:
    if ratio == 0 or not math.isfinite(ratio):
        return ""
    if ratio < 0:
        return " (sign flipped)" if math.isclose(abs(ratio), 1.0, rel_tol=0.02) else ""
    p = math.log10(ratio)
    if math.isclose(p, round(p), abs_tol=0.02) and round(p) != 0:
        return f" (reported value is off by a factor of 10^{round(p)})"
    return ""


def rule_substitution(doc: Document, rep: Report) -> None:
    eqs = {e.id: e for e in doc.equations}
    for k, c in enumerate(doc.calculations, 1):
        obj = f"calculation {c.get('id', k)} (equation {c.get('equation')})"
        eq = eqs.get(c.get("equation"))
        if eq is None or not eq.text:
            rep.add(Finding("E01", Outcome.NOT_CHECKABLE, obj, "equation not found or not readable"))
            continue
        try:
            lhs, rhs = parse_equation(eq.text, _known(doc))
            if lhs[0] != "sym":
                raise ParseError("left side is not a single symbol")
            env = _si_inputs(c["inputs"])
            want = c["reported"]
            if isinstance(want, dict):
                if lhs[1] not in want:
                    raise KeyError(f"no reported value for {lhs[1]}")
                want = want[lhs[1]]
            tol = float(c.get("tolerance", 0.02))
            val = evaluate(rhs, env)
            rv, rdim, _ = value_with_unit(want)
            ld = dim_eval(rhs, {k: value_with_unit(v)[1] for k, v in c["inputs"].items()}, [])
        except (ParseError, UnknownSymbol, UnitError, KeyError, ZeroDivisionError, ValueError) as e:
            rep.add(Finding("E01", Outcome.NOT_CHECKABLE, obj, f"cannot evaluate: {e}", evidence=eq.text))
            continue
        if ld != rdim:
            rep.add(Finding("E01", Outcome.VIOLATED, obj, "reported unit has a different dimension from the result",
                            Severity.SERIOUS, observed=str(rdim), expected=str(ld), evidence=eq.text))
            continue
        if math.isclose(val, rv, rel_tol=tol, abs_tol=1e-300):
            rep.add(Finding("E01", Outcome.VERIFIED, obj, f"reported value reproduces within {tol:.0%}",
                            observed=f"{rv:.4g}", expected=f"{val:.4g}", evidence=eq.text))
        else:
            ratio = rv / val if val else float("nan")
            rep.add(Finding("E01", Outcome.VIOLATED, obj,
                            "reported value does not follow from the inputs" + _magnitude_hint(ratio),
                            Severity.SERIOUS, observed=f"{rv:.4g} (SI)", expected=f"{val:.4g} (SI)", evidence=eq.text))


def rule_standard_forms(doc: Document, rep: Report, cards: dict[str, dict]) -> None:
    for eq in doc.equations:
        obj = f"equation {eq.id}"
        if not eq.text:
            continue
        try:
            lhs, rhs = parse_equation(eq.text, _known(doc) | {s for c in cards.values() for s in c["variables"]})
        except ParseError:
            continue
        mapping = doc.symbol_map.get(eq.id, {})
        syms = {mapping.get(s, s) for s in symbols(lhs) | symbols(rhs)}
        forced = doc.card_map.get(eq.id)
        cand = [cards[forced]] if forced in cards else [c for c in cards.values() if set(c["variables"]) == syms]
        if not cand:
            rep.add(Finding("E02", Outcome.NOT_CHECKABLE, obj, "no knowledge card with these symbols",
                            Severity.INFO, evidence=eq.text))
            continue
        best = None
        for c in cand:
            try:
                cl, cr = parse_equation(c["equation"], set(c["variables"]))
            except ParseError:
                continue
            ren = lambda n: ("sym", mapping.get(n[1], n[1]))
            # compare "lhs - rhs" forms: (lhs/rhs) must be 1 at every point; use residual-free ratio test
            doc_expr = ("div", lhs, rhs)
            card_expr = ("div", cl, cr)
            doc_expr = _rename(doc_expr, mapping)
            kind, ratio = equivalent(doc_expr, card_expr)
            if kind == "inconclusive":
                continue
            best = (c, kind, ratio)
            if kind == "equal":
                break
        if best is None:
            rep.add(Finding("E02", Outcome.NOT_CHECKABLE, obj, "comparison inconclusive", evidence=eq.text))
            continue
        c, kind, ratio = best
        if kind == "equal":
            rep.add(Finding("E02", Outcome.VERIFIED, obj, f"matches the standard form: {c['name']}",
                            evidence=eq.text, expected=c["equation"]))
        elif kind == "factor":
            rep.add(Finding("E02", Outcome.VIOLATED, obj,
                            f"differs from the standard form ({c['name']}) by a constant factor",
                            Severity.REVIEW, observed=f"ratio {ratio:.6g}", expected=c["equation"], evidence=eq.text))
        else:
            rep.add(Finding("E02", Outcome.VIOLATED, obj, f"differs from the standard form: {c['name']}",
                            Severity.REVIEW, expected=c["equation"], evidence=eq.text))


def _rename(node, mapping):
    t = node[0]
    if t == "sym":
        return ("sym", mapping.get(node[1], node[1]))
    if t == "num":
        return node
    if t == "neg":
        return ("neg", _rename(node[1], mapping))
    if t == "fn":
        return ("fn", node[1], _rename(node[2], mapping))
    return (t, _rename(node[1], mapping), _rename(node[2], mapping))


# ----------------------------------------------------------------------------- V: derivations
def rule_derivations(doc: Document, rep: Report) -> None:
    for d in doc.derivations:
        did = d.get("id", "?")
        steps = d.get("steps", [])
        assumptions = d.get("assumptions", [])
        for i in range(len(steps) - 1):
            a, b = steps[i], steps[i + 1]
            obj = f"derivation {did}, step {i + 1} to {i + 2}"
            approx = "≈" in b or "\\approx" in b
            try:
                ea = parse_expr(a.split("=")[-1] if "=" in a else a, _known(doc))
                eb = parse_expr(b.replace("≈", "").replace("\\approx", "").split("=")[-1] if "=" in b else b,
                                _known(doc))
            except ParseError as e:
                rep.add(Finding("V01", Outcome.NOT_CHECKABLE, obj, f"could not parse: {e}"))
                continue
            if approx:
                ok = bool(assumptions)
                rep.add(Finding("V02", Outcome.VERIFIED if ok else Outcome.VIOLATED, obj,
                                "approximation step with a stated assumption" if ok
                                else "approximation step with no stated assumption",
                                Severity.INFO if ok else Severity.REVIEW, evidence=f"{a}  ->  {b}"))
                continue
            kind, ratio = equivalent(ea, eb)
            ev = f"{a}  ->  {b}"
            if kind == "equal":
                rep.add(Finding("V01", Outcome.VERIFIED, obj, "step is algebraically equivalent", evidence=ev))
            elif kind == "factor":
                hint = "sign flip" if math.isclose(ratio, -1.0) else f"constant factor {ratio:.6g} gained or dropped"
                rep.add(Finding("V01", Outcome.VIOLATED, obj, f"step is not equivalent: {hint}", Severity.SERIOUS,
                                observed=f"ratio {ratio:.6g}", expected="1", evidence=ev))
            elif kind == "different":
                rep.add(Finding("V01", Outcome.VIOLATED, obj, "step is not equivalent (different functions)",
                                Severity.SERIOUS, evidence=ev))
            else:
                rep.add(Finding("V01", Outcome.NOT_CHECKABLE, obj, "equivalence test inconclusive", evidence=ev))


def run_all(doc: Document, cards: dict[str, dict]) -> Report:
    rep = Report(source=doc.source, n_equations=len(doc.equations))
    rule_units(doc, rep)
    rule_substitution(doc, rep)
    rule_standard_forms(doc, rep, cards)
    rule_derivations(doc, rep)
    return rep
