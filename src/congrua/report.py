"""Render a Report as Markdown or HTML."""
from __future__ import annotations

import html

from .model import Outcome, Report

ORDER = {Outcome.VIOLATED: 0, Outcome.NOT_CHECKABLE: 1, Outcome.VERIFIED: 2}
SEV = {"serious": 0, "review": 1, "info": 2}


def _sorted(rep: Report):
    return sorted(rep.findings, key=lambda f: (ORDER[f.outcome], SEV[f.severity.value], f.id))


def to_markdown(rep: Report) -> str:
    L = [f"# CONGRUA report", "", f"Source: `{rep.source}`", f"Equations found: {rep.n_equations}", "",
         f"**{rep.coverage_line()}**", "",
         "Findings are indicators for human review, each with its evidence. A verdict from this tool is a "
         "statement about the checked rule only.", ""]
    for o in (Outcome.VIOLATED, Outcome.NOT_CHECKABLE, Outcome.VERIFIED):
        fs = [f for f in _sorted(rep) if f.outcome == o]
        if not fs:
            continue
        L += [f"## {o.value.replace('_', ' ').title()} ({len(fs)})", ""]
        for f in fs:
            L.append(f"- **{f.id}** [{f.severity.value}] {f.object}: {f.message}")
            if f.observed or f.expected:
                L.append(f"  - observed: {f.observed or '-'}; expected: {f.expected or '-'}")
            if f.evidence:
                L.append(f"  - evidence: `{f.evidence}`")
            if f.reproduce:
                L.append(f"  - reproduce: `{f.reproduce}`")
        L.append("")
    return "\n".join(L)


def to_html(rep: Report) -> str:
    rows = []
    for f in _sorted(rep):
        rows.append("<tr class='%s'><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            f.outcome.value, html.escape(f.id), html.escape(f.outcome.value), html.escape(f.severity.value),
            html.escape(f.object), html.escape(f.message + (" | " + f.observed + " vs " + f.expected
                                                           if f.observed or f.expected else ""))))
    return ("<!doctype html><meta charset=utf-8><title>CONGRUA report</title><style>"
            "body{font:14px Georgia,serif;max-width:1000px;margin:2rem auto}table{border-collapse:collapse;width:100%}"
            "td,th{border:1px solid #bbb;padding:4px 6px;text-align:left}.violated{background:#fde8e8}"
            ".not_checkable{background:#fff6dd}.verified{background:#e9f7ec}</style>"
            f"<h1>CONGRUA report</h1><p>Source: {html.escape(rep.source)}</p><p><b>{html.escape(rep.coverage_line())}</b></p>"
            "<table><tr><th>ID</th><th>Outcome</th><th>Severity</th><th>Object</th><th>Message</th></tr>"
            + "".join(rows) + "</table>")
