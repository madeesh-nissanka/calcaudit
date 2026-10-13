"""Synthetic mutation test: inject known errors into equations built from the knowledge cards and
measure how many the rules catch. Uses no outside data."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .ingest import Document, Equation
from .rules import load_cards, run_all


@dataclass
class Result:
    kind: str
    card: str
    caught: bool


def _doc(eq_text: str, units: dict) -> Document:
    d = Document(source="synthetic")
    d.equations = [Equation("S1", eq_text, "synthetic")]
    d.glossary = dict(units)
    return d


def _violated(doc, cards) -> bool:
    rep = run_all(doc, cards)
    return any(f.outcome.value == "violated" for f in rep.findings)


WRONG_UNIT = {"1": "m", "m": "s", "m^2": "m^3", "m^4": "m^3", "s": "m", "kPa": "m", "Pa": "kg", "kN": "m", "m/s": "m",
              "J": "kPa", "kg": "s", "kg/m^3": "kg", "m/s^2": "m/s", "rad": "m", "kN*m": "kN", "1/kPa": "kPa",
              "Pa*s": "Pa"}


def run(cards: dict | None = None) -> list[Result]:
    cards = cards or load_cards()
    out: list[Result] = []
    for cid, c in cards.items():
        eq, units = c["equation"], c["variables"]
        lhs, rhs = [x.strip() for x in eq.split("=", 1)]
        if lhs not in units:          # composite left side: not used by the single-symbol mutations
            continue
        clean_viol = _violated(_doc(eq, units), cards)
        out.append(Result("clean", cid, not clean_viol))            # "caught" here means: correctly not flagged
        # (a) unit error: change the unit of one variable that appears on the right side
        for v in [k for k in units if re.search(rf"\b{re.escape(k)}\b", rhs)][:1]:
            bad = dict(units)
            bad[v] = WRONG_UNIT.get(units[v], "s" if units[v] != "s" else "m")
            out.append(Result("unit_error", cid, _violated(_doc(eq, bad), cards)))
        # (b) dropped / extra factor
        out.append(Result("extra_factor", cid, _violated(_doc(f"{lhs} = 2 * ({rhs})", units), cards)))
        # (c) sign flip
        out.append(Result("sign_flip", cid, _violated(_doc(f"{lhs} = -({rhs})", units), cards)))
        # (d) wrong exponent
        if re.search(r"\^\d", rhs):
            mut = re.sub(r"\^(\d)", lambda m: "^" + str(int(m.group(1)) + 1), rhs, count=1)
            out.append(Result("wrong_exponent", cid, _violated(_doc(f"{lhs} = {mut}", units), cards)))
        # (e) a term of the wrong dimension added
        other = next((k for k in units if units[k] != units[lhs] and k not in rhs), None)
        if other:
            out.append(Result("bad_sum", cid, _violated(_doc(f"{lhs} = {rhs} + {other}", units), cards)))
    return out


def summary(res: list[Result]) -> dict:
    kinds: dict[str, list[bool]] = {}
    for r in res:
        kinds.setdefault(r.kind, []).append(r.caught)
    return {k: (sum(v), len(v)) for k, v in kinds.items()}
