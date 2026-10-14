"""Rule pack T: claims against generic ranges, knowledge-card relations and validity limits."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

from ..expr import ParseError, equivalent, evaluate, parse_equation
from ..model import Finding, Outcome, Report, Severity
from ..units import UnitError, value_with_unit

RANGES = json.loads((Path(__file__).parent.parent / "ranges.json").read_text())["ranges"]
UNIVERSAL = re.compile(r"\b(always|never|all|every|proves?|proven|guarantees?|certainly|undoubtedly|impossible|"
                       r"in all cases|without exception)\b", re.I)


def _monotone_sign(card: dict, dep: str, indep: str):
    """+1 / -1 if the card relation is monotone in indep over positive values, 0 if not, None if unknown."""
    try:
        l, r = parse_equation(card["equation"], set(card["variables"]))
    except ParseError:
        return None
    if l[0] != "sym" or l[1] != dep:
        return None
    rng = random.Random(3)
    signs = set()
    names = [v for v in card["variables"] if v != dep]
    if indep not in names:
        return None
    for _ in range(25):
        env = {n: rng.uniform(0.6, 1.8) for n in names}
        h = 1e-4
        try:
            a = evaluate(r, env)
            env[indep] += h
            b = evaluate(r, env)
        except (ZeroDivisionError, ValueError, OverflowError):
            continue
        if b > a:
            signs.add(1)
        elif b < a:
            signs.add(-1)
    if len(signs) == 1:
        return signs.pop()
    return 0 if signs else None


def run(doc, cards: dict, rep: Report) -> None:
    for i, c in enumerate(doc.claims, 1):
        obj = f"claim {c.get('id', i)}: {str(c.get('text', ''))[:70]}"
        kind = c.get("type")
        if kind == "range":
            q = c.get("quantity")
            r = RANGES.get(q)
            if r is None:
                rep.add(Finding("T01", Outcome.NOT_CHECKABLE, obj, f"no generic range for {q!r}"))
                continue
            try:
                v, d, _ = value_with_unit(str(c.get("value")))
                lo, hi = value_with_unit(f"{r['min']} {r['unit']}")[0], value_with_unit(f"{r['max']} {r['unit']}")[0]
            except UnitError as e:
                rep.add(Finding("T01", Outcome.NOT_CHECKABLE, obj, f"value or unit not readable: {e}"))
                continue
            if lo <= v <= hi:
                rep.add(Finding("T01", Outcome.VERIFIED, obj, f"within the generic range for {q}"))
            else:
                rep.add(Finding("T01", Outcome.VIOLATED, obj, f"outside the generic range for {q}", Severity.REVIEW,
                                observed=str(c.get("value")), expected=f"{r['min']} to {r['max']} {r['unit']}"))
        elif kind == "trend":
            card = cards.get(c.get("card", ""))
            dep, ind, want = c.get("dependent"), c.get("independent"), c.get("direction")
            if card is None:
                rep.add(Finding("T02", Outcome.NOT_CHECKABLE, obj, "no knowledge card named for this claim"))
                continue
            s = _monotone_sign(card, dep, ind)
            if s is None:
                rep.add(Finding("T02", Outcome.NOT_CHECKABLE, obj, "card does not relate these quantities"))
            elif s == 0:
                rep.add(Finding("T02", Outcome.NOT_CHECKABLE, obj, "relation is not monotone over the tested range"))
            else:
                claimed = 1 if want in ("increases", "increase", "rises") else -1
                if claimed == s:
                    rep.add(Finding("T02", Outcome.VERIFIED, obj, f"{dep} {'increases' if s > 0 else 'decreases'} with {ind} in the card"))
                else:
                    rep.add(Finding("T02", Outcome.VIOLATED, obj, "direction contradicts the knowledge card", Severity.SERIOUS,
                                    observed=f"claim: {dep} {want} with {ind}",
                                    expected=f"card {card['id']}: {card['equation']}"))
        elif kind == "validity":
            card = cards.get(c.get("card", ""))
            if card is None or "validity" not in card:
                rep.add(Finding("T03", Outcome.NOT_CHECKABLE, obj, "card has no numeric validity limits"))
                continue
            bad = []
            for k, v in c.get("conditions", {}).items():
                lim = card["validity"].get(k)
                if lim is None:
                    continue
                if not (lim[0] <= float(v) <= lim[1]):
                    bad.append(f"{k}={v} outside {lim}")
            if bad:
                rep.add(Finding("T03", Outcome.VIOLATED, obj, f"used outside the validity of {card['name']}",
                                Severity.REVIEW, observed="; ".join(bad)))
            else:
                rep.add(Finding("T03", Outcome.VERIFIED, obj, f"conditions inside the validity of {card['name']}"))
    # T04: absolute wording in prose becomes a review question
    if doc.text:
        for m in re.finditer(r"[^.!?\n]*\b(always|never|all|every|proves?|proven|guarantees?|certainly|undoubtedly|"
                             r"impossible|in all cases|without exception)\b[^.!?\n]*[.!?]", doc.text, re.I):
            sent = re.sub(r"\s+", " ", m.group(0)).strip()
            if len(sent) > 15 and "\\" not in sent[:3]:
                rep.add(Finding("T04", Outcome.VIOLATED, "wording", "absolute wording: is it supported for every case?",
                                Severity.INFO, evidence=sent[:200]))
