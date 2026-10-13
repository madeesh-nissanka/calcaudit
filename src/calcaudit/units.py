"""Dimensional analysis with a small explicit unit table (no third-party dependency)."""
from __future__ import annotations

import re
from fractions import Fraction

BASE = ("M", "L", "T", "I", "K", "N", "J")   # mass, length, time, current, temperature, amount, luminosity


class Dim(tuple):
    """Dimension vector of Fractions over BASE."""

    def __new__(cls, *exps):
        v = [Fraction(0)] * len(BASE)
        for i, e in enumerate(exps):
            v[i] = Fraction(e)
        return super().__new__(cls, v)

    def __mul__(self, o):
        return Dim(*[a + b for a, b in zip(self, o)])

    def __truediv__(self, o):
        return Dim(*[a - b for a, b in zip(self, o)])

    def __pow__(self, p):
        p = Fraction(p)
        return Dim(*[a * p for a in self])

    def is_dimensionless(self) -> bool:
        return all(a == 0 for a in self)

    def __str__(self):
        if self.is_dimensionless():
            return "1"
        parts = []
        for n, e in zip(BASE, self):
            if e != 0:
                parts.append(n if e == 1 else f"{n}^{e}")
        return "·".join(parts)


ONE = Dim()
M_, L_, T_ = Dim(1), Dim(0, 1), Dim(0, 0, 1)
FORCE = M_ * L_ / (T_ ** 2)
PRESSURE = FORCE / (L_ ** 2)
ENERGY = FORCE * L_
POWER = ENERGY / T_

# symbol -> (dimension, factor to SI)
UNITS: dict[str, tuple[Dim, float]] = {
    "1": (ONE, 1.0), "-": (ONE, 1.0), "%": (ONE, 0.01), "rad": (ONE, 1.0), "deg": (ONE, 0.017453292519943295),
    "m": (L_, 1.0), "mm": (L_, 1e-3), "cm": (L_, 1e-2), "km": (L_, 1e3), "in": (L_, 0.0254), "ft": (L_, 0.3048),
    "s": (T_, 1.0), "ms": (T_, 1e-3), "min": (T_, 60.0), "h": (T_, 3600.0), "hr": (T_, 3600.0),
    "day": (T_, 86400.0), "d": (T_, 86400.0), "yr": (T_, 31557600.0), "year": (T_, 31557600.0),
    "g": (M_, 1e-3), "kg": (M_, 1.0), "t": (M_, 1e3), "Mg": (M_, 1e3),
    "N": (FORCE, 1.0), "kN": (FORCE, 1e3), "MN": (FORCE, 1e6),
    "Pa": (PRESSURE, 1.0), "kPa": (PRESSURE, 1e3), "MPa": (PRESSURE, 1e6), "GPa": (PRESSURE, 1e9),
    "bar": (PRESSURE, 1e5), "psi": (PRESSURE, 6894.757),
    "J": (ENERGY, 1.0), "kJ": (ENERGY, 1e3), "W": (POWER, 1.0), "kW": (POWER, 1e3),
    "Hz": (ONE / T_, 1.0), "K": (Dim(0, 0, 0, 0, 1), 1.0), "L": (L_ ** 3, 1e-3),
}

# quantity words -> expected dimension (used for table headers and glossaries)
QUANTITIES: dict[str, Dim] = {
    "length": L_, "width": L_, "height": L_, "depth": L_, "thickness": L_, "displacement": L_, "settlement": L_,
    "deflection": L_, "diameter": L_, "radius": L_,
    "time": T_, "duration": T_,
    "mass": M_, "force": FORCE, "load": FORCE,
    "stress": PRESSURE, "pressure": PRESSURE, "modulus": PRESSURE, "strength": PRESSURE,
    "velocity": L_ / T_, "speed": L_ / T_, "permeability": L_ / T_, "conductivity": L_ / T_,
    "acceleration": L_ / (T_ ** 2), "density": M_ / (L_ ** 3), "unit weight": FORCE / (L_ ** 3),
    "energy": ENERGY, "power": POWER, "frequency": ONE / T_, "strain": ONE, "ratio": ONE,
    "coefficient of consolidation": L_ ** 2 / T_, "area": L_ ** 2, "volume": L_ ** 3,
    "moment": ENERGY, "second moment of area": L_ ** 4,
}

_TOKEN = re.compile(r"\s*([A-Za-z%]+\d*|\d+|-|[\^/()·*])")


class UnitError(ValueError):
    pass


def parse_unit(text: str) -> tuple[Dim, float]:
    """Parse e.g. 'kN/m^2', 'm3/s', 'kg/(m·s^2)', 'm/yr' -> (dimension, SI factor)."""
    s = text.strip().replace("²", "^2").replace("³", "^3").replace("−", "-").replace("⋅", "·")
    s = s.replace("per ", "/")
    if s in ("", "1"):
        return ONE, 1.0
    pos = 0
    toks = []
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m:
            raise UnitError(f"cannot read unit text near {s[pos:pos+6]!r}")
        toks.append(m.group(1))
        pos = m.end()
    i = 0

    def atom():
        nonlocal i
        if i >= len(toks):
            raise UnitError("unit text ended early")
        t = toks[i]
        if t == "(":
            i += 1
            d, f = expr()
            if i >= len(toks) or toks[i] != ")":
                raise UnitError("missing )")
            i += 1
        elif t in ("1", "-"):
            i += 1
            d, f = ONE, 1.0
        elif re.fullmatch(r"[A-Za-z%]+\d?", t) or t in UNITS:
            m = re.fullmatch(r"([A-Za-z%]+?)(\d)?", t)
            name, tail = (t, None)
            if name not in UNITS and m and m.group(1) in UNITS and m.group(2):
                name, tail = m.group(1), int(m.group(2))
            if name not in UNITS:
                raise UnitError(f"unknown unit {t!r}")
            d, f = UNITS[name]
            i += 1
            if tail:
                d, f = d ** tail, f ** tail
        else:
            raise UnitError(f"unexpected {t!r}")
        if i < len(toks) and toks[i] == "^":
            i += 1
            sign = 1
            if i < len(toks) and toks[i] == "-":
                sign = -1
                i += 1
            if i >= len(toks) or not toks[i].isdigit():
                raise UnitError("bad exponent")
            p = sign * int(toks[i])
            i += 1
            d, f = d ** p, f ** p
        return d, f

    def term():
        nonlocal i
        d, f = atom()
        while i < len(toks) and toks[i] in ("·", "*", "/"):
            op = toks[i]
            i += 1
            d2, f2 = atom()
            if op == "/":
                d, f = d / d2, f / f2
            else:
                d, f = d * d2, f * f2
        return d, f

    def expr():
        return term()

    d, f = expr()
    if i != len(toks):
        raise UnitError(f"trailing text {toks[i:]!r}")
    return d, f


def quantity_dim(word: str) -> Dim | None:
    w = word.strip().lower()
    if w in QUANTITIES:
        return QUANTITIES[w]
    for k, v in QUANTITIES.items():
        if k in w:
            return v
    return None


def value_with_unit(text: str) -> tuple[float, Dim, float]:
    """'5.0e-10 m/s' -> (SI value, dim, factor)."""
    m = re.match(r"\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(.*)$", text)
    if not m:
        raise UnitError(f"no number in {text!r}")
    v = float(m.group(1))
    d, f = parse_unit(m.group(2) or "1")
    return v * f, d, f


def dim_to_unit(d: Dim) -> str:
    """A unit string with the given dimension (used for symbols inferred from a quantity word)."""
    for name in ("m", "s", "kg", "N", "kPa", "J", "W", "Hz", "K", "1"):
        if UNITS[name][0] == d and UNITS[name][1] == 1.0:
            return name
    if d.is_dimensionless():
        return "1"
    pieces = []
    for n, e in zip(("kg", "m", "s", "A", "K", "mol", "cd"), d):
        if e != 0:
            pieces.append(f"{n}^{e}" if e.denominator == 1 else None)
    if any(p is None for p in pieces):
        raise UnitError("fractional dimension has no unit string")
    return "·".join(pieces)
