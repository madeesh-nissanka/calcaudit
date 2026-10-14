# CalcAudit 1.0.0 - consistency checks for engineering documents

CALCAUDIT reads the equations in an engineering document (LaTeX, Markdown, plain text or Word with native equations),
checks them against the units you declare and against a library of standard relations, re-computes stated
calculations, and verifies each step of a written derivation. It reports every check as one of three outcomes:

| Outcome | Meaning |
|---|---|
| **verified** | the rule ran and passed |
| **violated** | the rule ran and failed; the evidence is attached |
| **not checkable** | the rule could not run; the reason is stated |

Every report ends with a coverage line, for example `20 checks: 11 verified, 7 violated, 2 not checkable (90% checkable).`
Findings are indicators for a human reviewer. The tool never states that anyone cheated.

## What v0.1 checks

| Rule | Check |
|---|---|
| U01 | both sides of an equation and all terms of a sum have the same dimension |
| U02 | arguments of exp, log, sin ... and exponents are dimensionless |
| U03 | a table column header such as `Settlement (kPa)` has a unit that fits the quantity |
| E01 | a reported result follows from the stated inputs (reports likely power-of-ten and sign errors) |
| E02 | the equation matches a standard form from the knowledge cards (reports a constant-factor difference) |
| V01 | each step of a derivation is algebraically equivalent to the previous one (reports dropped or extra factors and sign flips) |
| V02 | an approximation step has a stated assumption |

Standard library only; Python 3.10 or newer.

## Use

```bash
pip install .
calcaudit scan examples/consolidation_note.tex          # Markdown report to the terminal
calcaudit scan paper.docx --spec glossary.json --format html --out report.html
calcaudit units "kN/m^2"                                # dimension and SI factor
calcaudit cards                                         # built-in knowledge cards
```

A sidecar file `<document>.calcaudit.json` (or `--spec`) supplies the glossary of symbol units, the calculations to
re-compute, derivations and table headers. See `examples/`. Extracting calculations from prose is not part of v0.1.

## Knowledge cards

A card is a small JSON file: the equation, the unit of every variable, assumptions and a source note. Add your own
with `--cards <dir>`. The cards that ship are generic textbook relations; add a citation before relying on one in
a publication.

## Honest limits

- Equation parsing is for LaTeX-like and Word-native equations. PDFs are not read in v0.1.
- Symbol units must be declared in the glossary; undeclared symbols give "not checkable", never a pass.
- Equivalence testing is randomised numeric testing, not a formal proof; an inconclusive result is reported as such.
- The built-in mutation self-test builds its errors from the same cards the rules use, so its recall figure checks the
  plumbing, not real-world coverage. Independent test sets are planned.
- Detecting AI-written text is deliberately out of scope.

## Develop

```bash
python -m unittest discover -s tests
python -c "import sys; sys.path.insert(0,'src'); from calcaudit import mutate; print(mutate.summary(mutate.run()))"
```

MIT licence. Author: Madeesh P. Nissanka.

## v0.3.0 additions

| Rule | Check |
|---|---|
| D01 | a number reported in a table or text matches the calculation, parameter or data series it is declared to come from; no declared source is reported as "no source" |
| D02 | a mismatch that is a power of ten or a sign flip is named as such |
| C01-C03 | calibration honesty: how many measured signals were fitted, error above 25%, a good fit on one signal beside a poor fit on another |
| impact | `calcaudit impact doc.tex k`: everything that depends on a symbol, and reported values with no declared source |

The sidecar file takes `reported` (label, where, value, source) and `fits` (signal, fitted, mare_pct) entries; see `docs/RULES.md`.

## v0.4.0 additions: claims

| Rule | Check |
|---|---|
| T01 | a claimed parameter value lies inside the generic range for that quantity (`ranges.json`, unit-aware) |
| T02 | a claimed trend ("v decreases as i increases") agrees with the direction of the knowledge-card relation |
| T03 | a method is used inside the validity limits of its card (for example a Reynolds-number limit for Darcy's law) |
| T04 | absolute wording in the text ("always", "never", "proves") is listed as a review question |

Claims are given in the sidecar file under `claims`. The generic ranges are order-of-magnitude textbook values and
carry a note to add a citation before use in a publication.

## v0.5.0 additions: argument review questions

| Rule | Review question |
|---|---|
| A01 | the same symbol is given two different values in the text |
| A02 | strong certainty wording while no uncertainty, error or tolerance is stated anywhere |
| A03 | agreement or correlation and a causal claim in one sentence |
| A04 | agreement reported on the same data that was used to fit |
| A05 | one case and a general statement in the same paragraph |
| A06 | a claim with no evidence declared |

These are structural checks that quote the passage. They are written as questions for a reviewer and are never verdicts.
