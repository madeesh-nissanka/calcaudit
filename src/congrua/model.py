"""Finding records and the three-state outcome model."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum


class Outcome(str, Enum):
    VERIFIED = "verified"            # the rule ran and passed
    VIOLATED = "violated"            # the rule ran and failed (proof attached)
    NOT_CHECKABLE = "not_checkable"  # the rule could not run (reason attached)


class Severity(str, Enum):
    INFO = "info"
    REVIEW = "review"
    SERIOUS = "serious"


@dataclass
class Finding:
    rule: str                 # e.g. "U01"
    outcome: Outcome
    object: str               # what was checked (equation id, table column, step)
    message: str              # one-sentence statement
    severity: Severity = Severity.INFO
    observed: str = ""
    expected: str = ""
    evidence: str = ""        # source text span, numbers, dimensions
    reproduce: str = ""
    id: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["outcome"] = self.outcome.value
        d["severity"] = self.severity.value
        return d


@dataclass
class Report:
    source: str
    findings: list[Finding] = field(default_factory=list)
    n_equations: int = 0
    notes: list[str] = field(default_factory=list)

    def add(self, f: Finding) -> None:
        f.id = f.id or f"{f.rule}-{len(self.findings) + 1:04d}"
        self.findings.append(f)

    def counts(self) -> dict:
        c = {o.value: 0 for o in Outcome}
        for f in self.findings:
            c[f.outcome.value] += 1
        return c

    def coverage_line(self) -> str:
        c = self.counts()
        total = sum(c.values())
        if total == 0:
            return "No checks ran."
        return (f"{total} checks: {c['verified']} verified, {c['violated']} violated, "
                f"{c['not_checkable']} not checkable "
                f"({100.0 * (total - c['not_checkable']) / total:.0f}% checkable).")

    def to_json(self) -> str:
        return json.dumps({"source": self.source, "equations": self.n_equations, "coverage": self.coverage_line(),
                           "counts": self.counts(), "notes": self.notes,
                           "findings": [f.to_dict() for f in self.findings]}, indent=2)
