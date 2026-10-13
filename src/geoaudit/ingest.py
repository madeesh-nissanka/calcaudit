"""Read equations and a sidecar specification from .tex/.md/.txt/.docx files."""
from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class Equation:
    id: str
    text: str
    where: str = ""


@dataclass
class Document:
    source: str
    equations: list[Equation] = field(default_factory=list)
    glossary: dict = field(default_factory=dict)        # symbol -> unit string
    calculations: list[dict] = field(default_factory=list)
    derivations: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    card_map: dict = field(default_factory=dict)        # equation id -> card id
    symbol_map: dict = field(default_factory=dict)      # equation id -> {doc symbol: card symbol}


# ----------------------------------------------------------------------------- OMML
def omml_to_text(el) -> str:
    tag = el.tag.replace(M, "")
    ch = list(el)

    def kids(name):
        return [c for c in ch if c.tag == M + name]

    def one(name):
        k = kids(name)
        return "".join(omml_to_text(x) for x in k[0]) if k else ""

    if tag == "t":
        return el.text or ""
    if tag == "f":
        return "\\frac{" + one("num") + "}{" + one("den") + "}"
    if tag == "sSup":
        return "{" + one("e") + "}^{" + one("sup") + "}"
    if tag == "sSub":
        return "{" + one("e") + "}_{" + one("sub") + "}"
    if tag == "sSubSup":
        return "{" + one("e") + "}_{" + one("sub") + "}^{" + one("sup") + "}"
    if tag == "rad":
        deg = one("deg")
        if deg and deg != "2":
            raise ValueError("root of degree other than 2 is not supported")
        return "\\sqrt{" + one("e") + "}"
    if tag == "d":
        inner = "".join(omml_to_text(x) for x in kids("e"))
        return "(" + inner + ")"
    if tag in ("nary", "m", "eqArr", "groupChr", "limLow", "limUpp"):
        raise ValueError(f"OMML element {tag} is not supported")
    if tag in ("fName",):
        return "".join(omml_to_text(x) for x in ch)
    if tag == "func":
        return one("fName") + "(" + one("e") + ")"
    return "".join(omml_to_text(x) for x in ch)


def _docx_equations(path: Path) -> list[Equation]:
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("word/document.xml"))
    eqs: list[Equation] = []
    for n, el in enumerate(root.iter(M + "oMath"), 1):
        try:
            txt = omml_to_text(el).strip()
        except ValueError as e:
            eqs.append(Equation(f"E{n}", "", f"unsupported: {e}"))
            continue
        eqs.append(Equation(f"E{n}", txt, f"equation {n} in document order"))
    return eqs


# ----------------------------------------------------------------------------- plain text / TeX
_BLOCKS = [
    re.compile(r"\$\$(.+?)\$\$", re.S),
    re.compile(r"\\\[(.+?)\\\]", re.S),
    re.compile(r"\\begin\{equation\*?\}(.+?)\\end\{equation\*?\}", re.S),
    re.compile(r"\\begin\{align\*?\}(.+?)\\end\{align\*?\}", re.S),
]
_INLINE = re.compile(r"(?<!\$)\$([^$\n]+=[^$\n]+)\$(?!\$)")
_LINE = re.compile(r"^\s*(?:Eq\.?\s*)?\(?([A-Za-z]?\d+[A-Za-z]?)\)?[:.)]\s+(.+=.+)$", re.M)


def _text_equations(text: str) -> list[Equation]:
    found: list[tuple[int, str]] = []
    for rx in _BLOCKS:
        for m in rx.finditer(text):
            found.append((m.start(), m.group(1)))
    for m in _INLINE.finditer(text):
        found.append((m.start(), m.group(1)))
    eqs: list[Equation] = []
    for k, (pos, body) in enumerate(sorted(found), 1):
        label = re.search(r"\\label\{([^}]+)\}", body)
        body = re.sub(r"\\label\{[^}]+\}|\\tag\{[^}]+\}|&|\\\\", " ", body).strip()
        line = text.count("\n", 0, pos) + 1
        eqs.append(Equation(label.group(1) if label else f"E{k}", body, f"line {line}"))
    if not eqs:
        for m in _LINE.finditer(text):
            eqs.append(Equation(m.group(1), m.group(2).strip(), f"line {text.count(chr(10), 0, m.start()) + 1}"))
    return eqs


def load_document(path: str, spec: str | None = None) -> Document:
    p = Path(path)
    doc = Document(source=str(p))
    if p.suffix.lower() == ".docx":
        doc.equations = _docx_equations(p)
    elif p.suffix.lower() == ".json":
        spec = spec or str(p)
    else:
        doc.equations = _text_equations(p.read_text(encoding="utf-8", errors="replace"))
    sp = Path(spec) if spec else p.with_suffix(".geoaudit.json")
    if sp.exists():
        d = json.loads(sp.read_text(encoding="utf-8"))
        doc.glossary = d.get("glossary", {})
        doc.calculations = d.get("calculations", [])
        doc.derivations = d.get("derivations", [])
        doc.tables = d.get("tables", [])
        doc.card_map = d.get("cards", {})
        doc.symbol_map = d.get("symbol_map", {})
        for e in d.get("equations", []):
            doc.equations.append(Equation(e["id"], e["text"], e.get("where", "spec")))
    return doc
