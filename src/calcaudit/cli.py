"""Command line: calcaudit scan | units | cards."""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .ingest import load_document
from .report import to_html, to_markdown
from .rules import load_cards, run_all
from .units import UnitError, parse_unit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="calcaudit", description="Consistency checks for engineering documents.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="check a document (.tex .md .txt .docx or a .calcaudit.json spec)")
    s.add_argument("path")
    s.add_argument("--spec", help="sidecar JSON with glossary, calculations, derivations, tables")
    s.add_argument("--cards", help="extra directory of knowledge cards")
    s.add_argument("--format", choices=["md", "json", "html"], default="md")
    s.add_argument("--out", help="write the report to this file")
    u = sub.add_parser("units", help="show the dimension of a unit expression")
    u.add_argument("unit")
    sub.add_parser("cards", help="list the built-in knowledge cards")
    a = ap.parse_args(argv)
    if a.cmd == "units":
        try:
            d, f = parse_unit(a.unit)
        except UnitError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"dimension {d}; factor to SI {f:g}")
        return 0
    if a.cmd == "cards":
        for c in load_cards().values():
            print(f"{c['id']:30s} {c['equation']}")
        return 0
    doc = load_document(a.path, a.spec)
    rep = run_all(doc, load_cards(a.cards))
    out = {"md": to_markdown, "json": lambda r: r.to_json(), "html": to_html}[a.format](rep)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        print(rep.coverage_line())
    else:
        print(out)
    return 1 if rep.counts()["violated"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
