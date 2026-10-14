# CalcAudit

Consistency checks for engineering documents. CalcAudit reads the equations, tables, parameters, data series and
stated results of a report or paper, and tells you where they disagree with each other or with basic physics.

Every check ends in one of three outcomes, and every report states how much was actually checked:

| Outcome | Meaning |
|---|---|
| **verified** | the rule ran and passed |
| **violated** | the rule ran and failed; the evidence is attached |
| **not checkable** | the rule could not run; the reason is stated |

Example coverage line: `25 checks: 11 verified, 9 violated, 5 not checkable (80% checkable).`
Findings are indicators for a human reviewer. The tool never states that anyone cheated or acted in bad faith.

Standard library only; Python 3.10 or newer. MIT licence.

## Install and use

```bash
pip install .
calcaudit scan examples/consolidation_note.tex                  # Markdown report
calcaudit scan paper.docx --spec glossary.json --format html --out report.html
calcaudit impact examples/consolidation_note.tex k             # what depends on a symbol
calcaudit units "kN/m^2"                                        # dimension and SI factor
calcaudit cards                                                 # built-in knowledge cards
calcaudit selftest                                              # synthetic error-injection test
```

Inputs: LaTeX, Markdown and plain text; Word (`.docx`, native equations and table headers); PDF (equations are
reconstructed from text and always carry low confidence; needs `pdftotext` or the `pypdf` package); and a sidecar
file `<document>.calcaudit.json` (or `--spec`) with the glossary of symbol units, calculations, reported values,
datasets, parameters, claims and fit records. See `examples/`.

## Rules

| Pack | Rules | What they check |
|---|---|---|
| Units | U01 U02 U03 | dimensions of equations and sums; dimensionless arguments and exponents; units in table headers |
| Equations | E01 E02 | stated results recomputed from stated inputs (power-of-ten and sign hints); match to a standard form |
| Derivations | V01 V02 | each step equivalent to the previous one; approximation steps have a stated assumption |
| Parameters | P01-P08 | void ratio and saturation, unit weight, compression indices, OCR, permeability and unit slips, plasticity, friction angle |
| Series | F01-F04 L01 L02 | time axis, frozen sensor or steps, bounded quantities, monotonic requirements, duplicated rows and blocks |
| Traceability | D01 D02 | reported numbers match their declared source (calculation, parameter or data series) |
| Calibration | C01-C03 | how many measured signals were fitted; large errors; a good fit beside a poor one |
| Claims | T01-T04 | generic parameter ranges, trend direction against a card, validity limits, absolute wording |
| Argument | A01-A06 | review questions: contradictory values, certainty wording, correlation and cause, fit-and-validate on the same data, single case generalised, claims without evidence |

Details, tolerances and known false-alarm cases are in `docs/RULES.md`.

## Knowledge cards

A card is a small JSON file: the equation, the unit of every variable, assumptions, a source note and optional
numeric validity limits. 27 generic textbook relations ship with the package. Add your own with `--cards <dir>`.
Add a proper citation before relying on a card in a publication.

## Limits (please read)

- A clean report means the listed rules passed on what could be parsed, not that the document is correct.
- Symbol units must be declared or stated in a "where ..." clause; undeclared symbols give "not checkable", never a pass.
- Equivalence testing is randomised numeric testing, not a formal proof; an inconclusive result is reported as such.
- Equations reconstructed from PDF text are low confidence; serious findings on them are shown as review.
- Calculations are extracted from prose only when the equation, its inputs and its result appear in one paragraph.
- The generic parameter ranges are order-of-magnitude textbook values.
- The built-in self-test builds its errors from the same cards the rules use; it checks the plumbing, not real-world coverage.
- Detecting machine-written text is deliberately out of scope.

## Develop

```bash
python -m unittest discover -s tests
PYTHONPATH=src python -m calcaudit selftest
```

See `CONTRIBUTING.md`. Test data must be invented or public.

## Citation

See `CITATION.cff`. Author: Madeesh P. Nissanka. MIT licence.
