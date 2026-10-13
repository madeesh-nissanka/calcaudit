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
