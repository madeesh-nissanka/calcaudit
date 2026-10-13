"""Rule pack P: parameter physics (soil mechanics). Rules only run when at least one of their inputs is present."""
from __future__ import annotations

import math

from ..model import Finding, Outcome, Report, Severity
from ..units import UnitError, parse_unit, value_with_unit

ALIASES = {"C_c": "Cc", "Cc": "Cc", "C_r": "Cr", "Cr": "Cr", "C_s": "Cr", "e_0": "e0", "e0": "e0", "G_s": "Gs", "Gs": "Gs",
           "w": "w", "gamma": "gamma", "gamma_sat": "gamma", "lambda": "lambda", "kappa": "kappa", "OCR": "OCR",
           "k": "k", "phi": "phi", "varphi": "phi", "PI": "PI", "LL": "LL", "PL": "PL", "sigma_p": "sigma_p",
           "sigma_v0": "sigma_v0", "sigma_vo": "sigma_v0"}
GAMMA_W = 9810.0   # N/m^3


def _val(params, name, as_si=True):
    if name not in params:
        return None
    v, u = params[name]
    try:
        x, d, f = value_with_unit(f"{v} {u}" if u not in ("", "1") else f"{v}")
    except UnitError:
        return None
    return x


def canonical(params: dict) -> dict:
    out = {}
    for k, v in params.items():
        key = ALIASES.get(k.replace("{", "").replace("}", "").replace("\\", ""))
        if key:
            out[key] = v if isinstance(v, tuple) else (str(v), "")
    return out


def _w_fraction(params):
    v, u = params["w"]
    x = float(v)
    return x / 100.0 if (u == "%" or x > 1.5) else x


def run(params_raw: dict, rep: Report) -> None:
    p = canonical(params_raw)
    if not p:
        return

    def need(rule, obj, names):
        miss = [n for n in names if n not in p]
        if miss:
            rep.add(Finding(rule, Outcome.NOT_CHECKABLE, obj, "missing: " + ", ".join(miss)))
            return False
        return True

    # P01 void ratio vs water content (saturated: e = Gs w; e below Gs w is impossible)
    if any(n in p for n in ("e0", "Gs", "w")) and need("P01", "void ratio / water content", ["e0", "Gs", "w"]):
        e, gs, w = float(p["e0"][0]), float(p["Gs"][0]), _w_fraction(p)
        s_r = gs * w / e
        if s_r > 1.05:
            rep.add(Finding("P01", Outcome.VIOLATED, "void ratio / water content",
                            "degree of saturation above 100%: e0 is smaller than Gs x w", Severity.SERIOUS,
                            observed=f"Sr = Gs w / e0 = {s_r:.2f}", expected="Sr at most 1.0",
                            evidence=f"e0={e}, Gs={gs}, w={w:.3f}"))
        elif s_r < 0.90:
            rep.add(Finding("P01", Outcome.VIOLATED, "void ratio / water content",
                            "implied saturation below 90%; a saturated-soil assumption would not hold", Severity.REVIEW,
                            observed=f"Sr = {s_r:.2f}", expected="about 1.0 for saturated soil",
                            evidence=f"e0={e}, Gs={gs}, w={w:.3f}"))
        else:
            rep.add(Finding("P01", Outcome.VERIFIED, "void ratio / water content",
                            f"consistent with saturation (Sr = {s_r:.2f})"))
    # P02 saturated unit weight from e and Gs
    if "gamma" in p and ("Gs" in p or "e0" in p) and need("P02", "unit weight", ["gamma", "Gs", "e0"]):
        g = _val(p, "gamma")
        if g is None:
            rep.add(Finding("P02", Outcome.NOT_CHECKABLE, "unit weight", "unit of gamma not readable"))
        else:
            gs, e = float(p["Gs"][0]), float(p["e0"][0])
            calc = (gs + e) * GAMMA_W / (1 + e)
            rel = abs(g - calc) / calc
            if rel > 0.05:
                rep.add(Finding("P02", Outcome.VIOLATED, "unit weight", "unit weight inconsistent with Gs and e0",
                                Severity.REVIEW, observed=f"{g/1000:.2f} kN/m3", expected=f"{calc/1000:.2f} kN/m3",
                                evidence=f"Gs={gs}, e0={e}"))
            else:
                rep.add(Finding("P02", Outcome.VERIFIED, "unit weight", f"within 5% of {calc/1000:.2f} kN/m3"))
    # P03 compression vs recompression index
    if "Cc" in p and "Cr" in p:
        cc, cr = float(p["Cc"][0]), float(p["Cr"][0])
        if cr >= cc:
            rep.add(Finding("P03", Outcome.VIOLATED, "Cc and Cr", "recompression index is not smaller than compression index",
                            Severity.SERIOUS, observed=f"Cc={cc}, Cr={cr}", expected="Cr < Cc"))
        elif not (0.02 <= cr / cc <= 0.5):
            rep.add(Finding("P03", Outcome.VIOLATED, "Cc and Cr", "Cr/Cc is outside the usual 0.02 to 0.5",
                            Severity.INFO, observed=f"Cr/Cc={cr/cc:.3f}", expected="0.05 to 0.2 typical"))
        else:
            rep.add(Finding("P03", Outcome.VERIFIED, "Cc and Cr", f"Cr/Cc = {cr/cc:.3f}"))
    # P04 lambda, kappa vs Cc, Cr (factor 2.303)
    for lam, cc in (("lambda", "Cc"), ("kappa", "Cr")):
        if lam in p and cc in p:
            a, b = float(p[cc][0]), float(p[lam][0])
            ratio = a / b if b else float("nan")
            if math.isclose(ratio, math.log(10), rel_tol=0.05):
                rep.add(Finding("P04", Outcome.VERIFIED, f"{lam} and {cc}", "ratio equals ln 10 as expected"))
            elif math.isclose(ratio, 1.0, rel_tol=0.05):
                rep.add(Finding("P04", Outcome.VIOLATED, f"{lam} and {cc}",
                                "values are equal: the factor ln 10 = 2.303 is probably missing", Severity.REVIEW,
                                observed=f"{cc}/{lam}={ratio:.3f}", expected="2.303"))
            else:
                rep.add(Finding("P04", Outcome.VIOLATED, f"{lam} and {cc}", "ratio is not ln 10", Severity.INFO,
                                observed=f"{cc}/{lam}={ratio:.3f}", expected="2.303 if both describe the same soil"))
    # P05 OCR
    if "OCR" in p:
        o = float(p["OCR"][0])
        if o < 1.0:
            rep.add(Finding("P05", Outcome.VIOLATED, "OCR", "OCR below 1", Severity.SERIOUS, observed=str(o), expected="at least 1"))
        elif "sigma_p" in p and "sigma_v0" in p:
            r = float(p["sigma_p"][0]) / float(p["sigma_v0"][0])
            if math.isclose(r, o, rel_tol=0.05):
                rep.add(Finding("P05", Outcome.VERIFIED, "OCR", "equals preconsolidation / overburden stress"))
            else:
                rep.add(Finding("P05", Outcome.VIOLATED, "OCR", "does not equal sigma_p / sigma_v0", Severity.REVIEW,
                                observed=str(o), expected=f"{r:.2f}"))
        else:
            rep.add(Finding("P05", Outcome.VERIFIED, "OCR", "at least 1"))
    # P06 permeability magnitude and unit slip
    if "k" in p:
        k = _val(p, "k")
        if k is None:
            rep.add(Finding("P06", Outcome.NOT_CHECKABLE, "permeability", "unit of k not readable"))
        elif 1e-13 <= k <= 1e-1:
            rep.add(Finding("P06", Outcome.VERIFIED, "permeability", f"{k:.3g} m/s is within the range of soils"))
        else:
            hints = []
            for lab, f in (("m/day", 86400.0), ("m/year", 31557600.0), ("mm/s", 1e3)):
                if 1e-13 <= k / f <= 1e-1:
                    hints.append(f"would be {k/f:.3g} m/s if the value were in {lab}")
            rep.add(Finding("P06", Outcome.VIOLATED, "permeability", "value outside the range of soils (1e-13 to 1e-1 m/s)",
                            Severity.SERIOUS, observed=f"{k:.3g} m/s", expected="1e-13 to 1e-1 m/s",
                            evidence="; ".join(hints)))
    # P07 Atterberg limits
    if all(n in p for n in ("LL", "PL")):
        ll, pl = float(p["LL"][0]), float(p["PL"][0])
        if pl >= ll:
            rep.add(Finding("P07", Outcome.VIOLATED, "Atterberg limits", "plastic limit is not below liquid limit",
                            Severity.SERIOUS, observed=f"LL={ll}, PL={pl}", expected="PL < LL"))
        elif "PI" in p and abs(float(p["PI"][0]) - (ll - pl)) > 1.0:
            rep.add(Finding("P07", Outcome.VIOLATED, "Atterberg limits", "PI differs from LL - PL by more than 1 point",
                            Severity.REVIEW, observed=p["PI"][0], expected=f"{ll - pl:.1f}"))
        else:
            rep.add(Finding("P07", Outcome.VERIFIED, "Atterberg limits", "consistent"))
    # P08 friction angle
    if "phi" in p:
        v, u = p["phi"]
        x = float(v)
        deg = math.degrees(x) if u == "rad" else x
        if 5 <= deg <= 50:
            rep.add(Finding("P08", Outcome.VERIFIED, "friction angle", f"{deg:.1f} degrees is plausible"))
        else:
            rep.add(Finding("P08", Outcome.VIOLATED, "friction angle", "outside 5 to 50 degrees", Severity.REVIEW,
                            observed=f"{deg:.1f} degrees", expected="5 to 50"))
