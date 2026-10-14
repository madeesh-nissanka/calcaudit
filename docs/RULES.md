# Rule reference

Each rule has an ID, a deterministic test, and a documented false-alarm case.

| ID | Test | Known false alarms |
|---|---|---|
| U01 | dimension(lhs) equals dimension(rhs); every sum has equal dimensions | symbols that are intentionally dimensionless parameters declared with a unit |
| U02 | function arguments and exponents are dimensionless | empirical formulas that hide a reference unit (declare it in the glossary) |
| U03 | unit in a header matches the quantity word | quantity words outside the built-in table are reported as not checkable |
| E01 | recomputed value within tolerance of the reported value (default 2%) | rounding in the source; raise the tolerance per calculation |
| E02 | numeric equivalence to a standard card with the same symbols | alternative sign conventions; supply a `symbol_map` or a custom card |
| V01 | equivalence of consecutive derivation steps by random numeric testing | steps that are only valid under a domain restriction |
| V02 | an approximation step needs a stated assumption | none known |
| D01 | declared source value within tolerance (default 3%) | rounding in the source; set `tolerance` per value |
| D02 | mismatch that equals 10^n times, or minus one times, the source | unit change not declared |
| C01 | only one of several measured signals was fitted | a single measured signal exists |
| C02 | reported mean relative error above 25% | metric defined differently |
| C03 | good fit (15% or less) on the fitted signal and above 40% on another | the second signal is out of scope for the study |
| T01 | claimed value inside the generic range after unit conversion | unusual soils legitimately outside the generic range |
| T02 | sign of the partial derivative of the card relation over positive values | relations that change direction (reported as not checkable) |
| T03 | stated condition values inside the numeric validity of the card | validity limits are approximate |
| T04 | absolute words in a sentence | quoted or mathematical uses |
