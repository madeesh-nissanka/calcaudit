"""Rule packs D (document to source traceability) and C (calibration honesty)."""
from __future__ import annotations

import csv
import math
from pathlib import Path

from ..expr import ParseError, UnknownSymbol, evaluate, parse_equation
from ..model import Finding, Outcome, Report, Severity
from ..units import UnitError, parse_unit, value_with_unit


def _hint(ratio: float) -> str:
    if ratio == 0 or not math.isfinite(ratio):
        return ""
    if ratio < 0 and math.isclose(abs(ratio), 1.0, rel_tol=0.02):
        return "the sign is flipped"
    if ratio > 0:
        p = math.log10(ratio)
        if math.isclose(p, round(p), abs_tol=0.02) and round(p) != 0:
            return f"the reported value is 10^{round(p)} times the source value"
    return ""


def _source_value(src: dict, doc, base: Path):
    """Return (value in SI, description) or raise LookupError with the reason."""
    if "calculation" in src:
        c = next((x for x in doc.calculations if x.get("id") == src["calculation"]), None)
        if c is None:
            raise LookupError("calculation not found")
        sym = src.get("symbol") or next(iter(c.get("reported", {})), None)
        eq = next((e for e in doc.equations if e.id == c.get("equation")), None)
        if eq is None:
            raise LookupError("equation of the calculation not found")
        try:
            l, r = parse_equation(eq.text, set(doc.glossary))
            env = {k: value_with_unit(v)[0] for k, v in c["inputs"].items()}
            return evaluate(r, env), f"recomputed from calculation {c.get('id')}"
        except (ParseError, UnknownSymbol, UnitError, KeyError, ZeroDivisionError) as e:
            raise LookupError(f"calculation cannot be evaluated: {e}")
    if "parameter" in src:
        p = doc.parameters.get(src["parameter"])
        if p is None:
            raise LookupError("parameter not found")
        v, u = (p if isinstance(p, (list, tuple)) else (p, ""))
        return value_with_unit(f"{v} {u}".strip())[0], f"parameter {src['parameter']}"
    if "dataset" in src:
        ds = next((d for d in doc.datasets if d.get("name") == src["dataset"]), None)
        if ds is None:
            raise LookupError("dataset not found")
        path = Path(ds["path"])
        path = path if path.is_absolute() else base / path
        try:
            rows = list(csv.DictReader(open(path, newline="", encoding="utf-8-sig")))
        except OSError as e:
            raise LookupError(f"dataset not readable: {e}")
        col, tcol, at = src.get("column"), ds.get("time"), float(src.get("time", "nan"))
        if col not in rows[0] or tcol not in rows[0] or math.isnan(at):
            raise LookupError("column or time not given")
        best = min(rows, key=lambda r: abs(float(r[tcol]) - at))
        if abs(float(best[tcol]) - at) > float(src.get("time_tolerance", 0.5)):
            raise LookupError("no row at that time")
        unit = ds.get("columns", {}).get(col, "1")
        factor = parse_unit(unit)[1]                      # column values are in the declared unit
        return float(best[col]) * factor, f"{src['dataset']}.{col} at t={best[tcol]}"
    raise LookupError("no source declared")


def run(doc, base: Path, rep: Report) -> None:
    for i, rv in enumerate(doc.reported):
        obj = f"reported value {rv.get('label', i)} ({rv.get('where', '?')})"
        src = rv.get("source")
        if not src:
            rep.add(Finding("D01", Outcome.NOT_CHECKABLE, obj, "no source declared: the number cannot be traced",
                            Severity.REVIEW, evidence=str(rv.get("value"))))
            continue
        try:
            want, wd, _ = value_with_unit(str(rv["value"]))
            got, how = _source_value(src, doc, base)
        except (LookupError, UnitError, KeyError, ValueError) as e:
            rep.add(Finding("D01", Outcome.NOT_CHECKABLE, obj, f"cannot trace: {e}"))
            continue
        tol = float(rv.get("tolerance", 0.03))
        if math.isclose(want, got, rel_tol=tol, abs_tol=1e-12):
            rep.add(Finding("D01", Outcome.VERIFIED, obj, f"matches {how}", observed=f"{want:.4g}", expected=f"{got:.4g}"))
        else:
            ratio = want / got if got else float("nan")
            h = _hint(ratio)
            rep.add(Finding("D02" if h else "D01", Outcome.VIOLATED, obj,
                            "value does not match its declared source" + (f" ({h})" if h else ""),
                            Severity.SERIOUS, observed=f"{want:.4g} (SI)", expected=f"{got:.4g} (SI) from {how}"))
    # C: calibration honesty
    if doc.fits:
        fitted = [f for f in doc.fits if f.get("fitted")]
        for f in doc.fits:
            m = f.get("mare_pct")
            if m is not None and m > 25:
                rep.add(Finding("C02", Outcome.VIOLATED, f"fit of {f.get('signal')}", "mean relative error above 25%",
                                Severity.REVIEW, observed=f"{m}%", expected="25% or less"))
        if len(doc.fits) > 1 and len(fitted) == 1:
            others = [f for f in doc.fits if not f.get("fitted")]
            bad = [f for f in others if (f.get("mare_pct") or 0) > 40]
            good = fitted[0].get("mare_pct", 100) <= 15
            if bad and good:
                rep.add(Finding("C03", Outcome.VIOLATED, "calibration", "good fit on the fitted signal, poor fit on another measured signal",
                                Severity.REVIEW, observed=", ".join(f"{b.get('signal')} {b.get('mare_pct')}%" for b in bad),
                                expected="agreement on all measured signals, or a stated reason",
                                evidence=f"fitted: {fitted[0].get('signal')} {fitted[0].get('mare_pct')}%"))
            else:
                rep.add(Finding("C01", Outcome.VIOLATED, "calibration", "only one measured signal was used for fitting",
                                Severity.INFO, observed=fitted[0].get("signal", "?")))
        elif len(fitted) >= 2:
            rep.add(Finding("C01", Outcome.VERIFIED, "calibration", f"{len(fitted)} signals used for fitting"))
