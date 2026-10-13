"""Pull symbol units and stated calculations out of running text."""
from __future__ import annotations

import re

from .units import UnitError, dim_to_unit, parse_unit, quantity_dim

_EQ_ENV = [re.compile(p, re.S) for p in (r"\$\$.+?\$\$", r"\\\[.+?\\\]", r"\\begin\{equation\*?\}.+?\\end\{equation\*?\}",
                                         r"\\begin\{align\*?\}.+?\\end\{align\*?\}")]
_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
_TIMES = re.compile(r"(\d(?:\.\d+)?)\s*(?:×|\\times|x)\s*10\^\{?(-?\d+)\}?")
_ASSIGN = re.compile(r"(?P<sym>\\?[A-Za-z][A-Za-z0-9_{}\\']*)\s*=\s*(?P<val>" + _NUM + r")(?:\s*(?P<unit>[A-Za-z%°][A-Za-z0-9^/·*()\-]*))?")


def norm_symbol(s: str) -> str:
    s = s.strip().strip("$").replace("\\", "").replace("{", "").replace("}", "")
    return s


def strip_math_blocks(text: str) -> str:
    for rx in _EQ_ENV:
        text = rx.sub(" ", text)
    return text


def assignments(par: str) -> dict[str, tuple[str, str]]:
    """symbol -> (value text, unit text) for 'k = 1e-6 m/s' style statements in one paragraph."""
    par = _TIMES.sub(lambda m: f"{m.group(1)}e{m.group(2)}", par.replace("$", " "))
    out = {}
    for m in _ASSIGN.finditer(par):
        unit = (m.group("unit") or "").strip()
        if unit:
            if unit in ("and", "or", "is", "to", "the", "at", "for", "with", "in", "of"):
                unit = ""
            else:
                try:
                    parse_unit(unit)
                except UnitError:
                    continue            # something like "2 k i": not a value with a unit
        out[norm_symbol(m.group("sym"))] = (m.group("val"), unit or "1")
    return out


_WHERE = re.compile(r"\bwhere\b(?P<body>.+?)(?:\.\s|\.$|\n\n|$)", re.S | re.I)
_DEF = re.compile(r"^\s*\$?(?P<s>[^\s$,=]+)\$?\s*(?:is|denotes|represents|=)\s+(?:the\s+|a\s+|an\s+)?(?P<q>[^,;()\[\]]+?)"
                  r"\s*(?:\((?P<u1>[^)]+)\)|\[(?P<u2>[^\]]+)\]|,\s*in\s+(?P<u3>[A-Za-z/^0-9·*\-]+))?\s*$", re.I)


def infer_symbols(text: str) -> dict[str, tuple[str, str]]:
    """symbol -> (unit string, how it was inferred)."""
    out: dict[str, tuple[str, str]] = {}
    for w in _WHERE.finditer(text):
        for seg in re.split(r";|\band\b|,(?=\s*\$?[A-Za-z\\])", w.group("body")):
            m = _DEF.match(seg)
            if not m:
                continue
            sym = norm_symbol(m.group("s"))
            for key in ("u1", "u2", "u3"):
                u = m.group(key)
                if u:
                    try:
                        parse_unit(u)
                        out[sym] = (u.strip(), f"stated unit in 'where' clause: {seg.strip()[:60]}")
                        break
                    except UnitError:
                        continue
            else:
                d = quantity_dim(m.group("q"))
                if d is not None:
                    try:
                        out[sym] = (dim_to_unit(d), f"quantity word '{m.group('q').strip()}'")
                    except UnitError:
                        pass
    return out


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", strip_math_blocks(text)) if p.strip()]
