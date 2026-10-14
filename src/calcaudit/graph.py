"""Evidence graph: quantities, equations, calculations, data columns and reported values, with impact analysis."""
from __future__ import annotations

from collections import defaultdict

from .expr import ParseError, parse_equation, symbols
from .ingest import Document


class Graph:
    def __init__(self, doc: Document):
        self.edges: dict[str, set[str]] = defaultdict(set)   # node -> neighbours (undirected)
        self.kind: dict[str, str] = {}
        known = set(doc.glossary)
        for eq in doc.equations:
            en = f"eq:{eq.id}"
            self.kind[en] = "equation"
            if not eq.text:
                continue
            try:
                l, r = parse_equation(eq.text, known)
            except ParseError:
                continue
            for s in symbols(l) | symbols(r):
                self._link(en, f"sym:{s}", "quantity")
        for c in doc.calculations:
            cn = f"calc:{c.get('id', '?')}"
            self.kind[cn] = "calculation"
            self._link(cn, f"eq:{c.get('equation')}", None)
            for s in list(c.get("inputs", {})) + list(c.get("reported", {})):
                self._link(cn, f"sym:{s}", "quantity")
        for i, rv in enumerate(doc.reported):
            rn = f"rep:{rv.get('label', i)}"
            self.kind[rn] = "reported value"
            src = rv.get("source", {})
            if "calculation" in src:
                self._link(rn, f"calc:{src['calculation']}", None)
            if "symbol" in src:
                self._link(rn, f"sym:{src['symbol']}", "quantity")
            if "dataset" in src:
                self._link(rn, f"data:{src['dataset']}:{src.get('column', '')}", "data series")
            if "parameter" in src:
                self._link(rn, f"sym:{src['parameter']}", "quantity")
        for ds in doc.datasets:
            for col in ds.get("columns", {}):
                self._link(f"data:{ds.get('name', ds.get('path'))}:{col}", f"sym:{col}", "quantity")

    def _link(self, a, b, bkind):
        self.edges[a].add(b)
        self.edges[b].add(a)
        if bkind:
            self.kind.setdefault(b, bkind)

    def impact(self, node: str, depth: int = 4) -> dict[str, int]:
        """Everything reachable from a node, with its distance."""
        seen = {node: 0}
        frontier = [node]
        for d in range(1, depth + 1):
            nxt = []
            for n in frontier:
                for m in self.edges.get(n, ()):
                    if m not in seen:
                        seen[m] = d
                        nxt.append(m)
            frontier = nxt
        seen.pop(node)
        return seen

    def orphans(self) -> list[str]:
        """Reported values with no declared source."""
        return [n for n, k in self.kind.items() if k == "reported value" and len(self.edges.get(n, ())) == 0]
