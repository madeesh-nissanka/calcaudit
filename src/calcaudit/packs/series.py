"""Rule packs F (field monitoring series) and L (laboratory data tables) on CSV files."""
from __future__ import annotations

import csv
import datetime as dt
import statistics
from pathlib import Path

from ..model import Finding, Outcome, Report, Severity


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _time(s):
    v = _num(s)
    if v is not None:
        return v
    try:
        return dt.datetime.fromisoformat(s.strip()).timestamp() / 86400.0   # days
    except (ValueError, AttributeError):
        return None


def run(ds: dict, base: Path, rep: Report) -> None:
    name = ds.get("name", ds.get("path", "?"))
    path = Path(ds["path"])
    if not path.is_absolute():
        path = base / path
    obj = f"dataset {name}"
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except OSError as e:
        rep.add(Finding("F00", Outcome.NOT_CHECKABLE, obj, f"file not readable: {e}"))
        return
    if len(rows) < 5:
        rep.add(Finding("F00", Outcome.NOT_CHECKABLE, obj, "fewer than 5 rows"))
        return
    tcol = ds.get("time")
    cols = [c for c in ds.get("columns", {}) if c in rows[0]]
    kind = ds.get("kind", "field")
    # F01 time axis
    if tcol and tcol in rows[0]:
        ts = [_time(r[tcol]) for r in rows]
        if any(t is None for t in ts):
            rep.add(Finding("F01", Outcome.NOT_CHECKABLE, obj, f"time column {tcol!r} has unreadable values"))
        else:
            back = [i for i in range(1, len(ts)) if ts[i] < ts[i - 1]]
            dup = [i for i in range(1, len(ts)) if ts[i] == ts[i - 1]]
            diffs = [b - a for a, b in zip(ts, ts[1:]) if b > a]
            med = statistics.median(diffs) if diffs else 0
            gaps = [i for i in range(1, len(ts)) if med and ts[i] - ts[i - 1] > 5 * med]
            if back:
                rep.add(Finding("F01", Outcome.VIOLATED, obj, "time goes backwards", Severity.SERIOUS,
                                observed=f"{len(back)} reversals, first at row {back[0] + 2}", expected="non-decreasing"))
            elif dup or gaps:
                rep.add(Finding("F01", Outcome.VIOLATED, obj, "duplicate timestamps or gaps", Severity.REVIEW,
                                observed=f"{len(dup)} duplicates, {len(gaps)} gaps > 5x median interval",
                                evidence=f"first gap rows: {[g + 2 for g in gaps[:3]]}"))
            else:
                rep.add(Finding("F01", Outcome.VERIFIED, obj, "time axis regular and increasing"))
    # F02 frozen sensor and steps, per column
    for c in cols:
        vals = [_num(r[c]) for r in rows]
        if any(v is None for v in vals):
            rep.add(Finding("F02", Outcome.NOT_CHECKABLE, f"{obj}, column {c}", "non-numeric values"))
            continue
        run_len = best = 1
        for a, b in zip(vals, vals[1:]):
            run_len = run_len + 1 if a == b else 1
            best = max(best, run_len)
        limit = max(5, len(vals) // 20)
        d = [b - a for a, b in zip(vals, vals[1:])]
        mad = statistics.median(abs(x - statistics.median(d)) for x in d) * 1.4826
        thr = max(8 * mad, 1e-12)
        steps = [i for i, x in enumerate(d) if abs(x - statistics.median(d)) > thr and mad > 0]
        problems = []
        if best >= limit:
            problems.append(f"{best} identical consecutive values (limit {limit})")
        if mad > 0 and len(steps) > 0 and len(steps) <= max(3, len(d) // 50):
            problems.append(f"{len(steps)} abrupt step(s), first at row {steps[0] + 3}")
        if problems:
            rep.add(Finding("F02", Outcome.VIOLATED, f"{obj}, column {c}", "possible frozen sensor or abrupt step",
                            Severity.REVIEW, observed="; ".join(problems)))
        else:
            rep.add(Finding("F02", Outcome.VERIFIED, f"{obj}, column {c}", "no flat run or abrupt step"))
        # monotonic requirement (settlement under constant load, e-log p loading branch)
        want = ds.get("monotone", {}).get(c)
        if want:
            sgn = 1 if want == "increasing" else -1
            bad = [i for i, x in enumerate(d) if sgn * x < -1e-12 * (abs(vals[i]) + 1)]
            if bad:
                rep.add(Finding("F04" if kind == "field" else "L01", Outcome.VIOLATED, f"{obj}, column {c}",
                                f"not monotone {want}", Severity.REVIEW,
                                observed=f"{len(bad)} reversals, first at row {bad[0] + 3}"))
            else:
                rep.add(Finding("F04" if kind == "field" else "L01", Outcome.VERIFIED, f"{obj}, column {c}",
                                f"monotone {want}"))
    # F03 pore pressure bounded by total stress
    for pair in ds.get("bounded_by", []):
        a, b = pair["value"], pair["limit"]
        if a in rows[0] and b in rows[0]:
            over = [i for i, r in enumerate(rows) if _num(r[a]) is not None and _num(r[b]) is not None
                    and _num(r[a]) > _num(r[b]) + 1e-9]
            if over:
                rep.add(Finding("F03", Outcome.VIOLATED, obj, f"{a} exceeds {b}", Severity.SERIOUS,
                                observed=f"{len(over)} rows, first at row {over[0] + 2}", expected=f"{a} <= {b}"))
            else:
                rep.add(Finding("F03", Outcome.VERIFIED, obj, f"{a} never exceeds {b}"))
    # L02 duplicated rows and repeated blocks
    body = [tuple(v for k, v in r.items() if k != tcol) for r in rows]
    consec = sum(1 for a, b in zip(body, body[1:]) if a == b)
    seen = {}
    block = 4
    repeats = 0
    for i in range(len(body) - block + 1):
        key = body[i:i + block]
        key = tuple(key)
        if key in seen and i - seen[key] >= block:
            repeats += 1
        seen.setdefault(key, i)
    if consec >= 3 or repeats:
        rep.add(Finding("L02", Outcome.VIOLATED, obj, "duplicated rows or repeated blocks", Severity.REVIEW,
                        observed=f"{consec} identical consecutive rows, {repeats} repeated {block}-row blocks"))
    else:
        rep.add(Finding("L02", Outcome.VERIFIED, obj, "no duplicated rows or repeated blocks"))
