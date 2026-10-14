"""Rule pack A: structural argument checks. Every result is a review question quoting the passage, never a verdict."""
from __future__ import annotations

import re

from ..model import Finding, Outcome, Report, Severity
from ..prose import assignments, paragraphs

CERTAIN = re.compile(r"\b(clearly|obviously|definitely|undoubtedly|conclusively|proves?|demonstrates?|establishes?)\b", re.I)
UNCERT = re.compile(r"\b(uncertaint\w*|error bars?|standard deviation|confidence|tolerance|scatter|variability|"
                    r"sensitivity|±|\+/-)\b", re.I)
CAUSAL = re.compile(r"\b(causes?|caused by|leads? to|results? in|due to|because of|responsible for)\b", re.I)
CORREL = re.compile(r"\b(correlat\w*|associated with|corresponds? to|coincides? with|agrees? with)\b", re.I)
SINGLE = re.compile(r"\b(a single|one|only one|single)\s+(case|test|site|specimen|sample|borehole|project|model)\b", re.I)
GENERAL = re.compile(r"\b(all|any|general(ly)?|universal(ly)?|every|always|in practice)\b", re.I)


def _sentences(text: str):
    for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text)):
        if len(s) > 20:
            yield s


def run(doc, rep: Report) -> None:
    text = doc.text
    # A01 the same quantity given two different values in the text
    seen: dict[str, tuple[str, str, int]] = {}
    for pi, par in enumerate(paragraphs(text), 1) if text else []:
        for sym, (val, unit) in assignments(par).items():
            try:
                v = float(val)
            except ValueError:
                continue
            if sym in seen and unit == seen[sym][1] and abs(v - float(seen[sym][0])) > 1e-9 * max(1.0, abs(v)):
                rep.add(Finding("A01", Outcome.VIOLATED, f"quantity {sym}", "the same symbol is given two different values",
                                Severity.REVIEW, observed=f"{seen[sym][0]} {seen[sym][1]} (paragraph {seen[sym][2]}) and {val} {unit} (paragraph {pi})",
                                expected="one value, or different symbols for different cases"))
            seen.setdefault(sym, (val, unit, pi))
    if text:
        has_uncert = bool(UNCERT.search(text))
        for s in _sentences(text):
            if CERTAIN.search(s) and not has_uncert:
                rep.add(Finding("A02", Outcome.VIOLATED, "certainty wording",
                                "strong certainty wording and no uncertainty, error or tolerance statement anywhere in the text",
                                Severity.INFO, evidence=s[:200]))
            if CAUSAL.search(s) and CORREL.search(s):
                rep.add(Finding("A03", Outcome.VIOLATED, "causal wording",
                                "agreement or correlation and a causal claim in one sentence: is causation shown?",
                                Severity.INFO, evidence=s[:200]))
        for par in paragraphs(text):
            if SINGLE.search(par) and GENERAL.search(par):
                m = SINGLE.search(par)
                rep.add(Finding("A05", Outcome.VIOLATED, "generalisation",
                                "one case and a general statement in the same paragraph: does the evidence support the scope?",
                                Severity.INFO, evidence=m.group(0)))
    # A04 fitted and validated on the same data
    for f in doc.fits:
        if f.get("fitted_on") and f.get("validated_on") and f["fitted_on"] == f["validated_on"]:
            rep.add(Finding("A04", Outcome.VIOLATED, f"fit of {f.get('signal')}",
                            "agreement is reported on the same data that was used to fit", Severity.REVIEW,
                            observed=f"fitted_on = validated_on = {f['fitted_on']}",
                            expected="validation on data not used for fitting, or the agreement stated as a fit quality"))
    # A06 claims with no evidence declared
    for i, c in enumerate(doc.claims, 1):
        if not c.get("evidence") and c.get("type") not in ("range", "trend", "validity"):
            rep.add(Finding("A06", Outcome.VIOLATED, f"claim {c.get('id', i)}", "claim with no evidence declared",
                            Severity.INFO, evidence=str(c.get("text", ""))[:200]))
