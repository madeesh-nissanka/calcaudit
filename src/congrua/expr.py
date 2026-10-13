"""Parser and evaluator for a LaTeX-lite / plain infix expression language (numeric and dimensional)."""
from __future__ import annotations

import math
import random
import re
from fractions import Fraction

from .units import ONE, Dim, parse_unit

GREEK = {"alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta", "vartheta", "iota",
         "kappa", "lambda", "mu", "nu", "xi", "rho", "sigma", "tau", "phi", "varphi", "chi", "psi", "omega",
         "Gamma", "Delta", "Theta", "Lambda", "Sigma", "Phi", "Psi", "Omega"}
FUNCS = {"exp", "ln", "log", "sqrt", "sin", "cos", "tan", "abs", "tanh", "erf"}


class ParseError(ValueError):
    pass


class UnknownSymbol(KeyError):
    pass


# ----------------------------------------------------------------------------- tokenizer
_NUM = re.compile(r"\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?")


def tokenize(src: str, known: set[str]) -> list[tuple[str, str]]:
    s = src
    for junk in (r"\left", r"\right", r"\,", r"\;", r"\!", r"\ ", "$"):
        s = s.replace(junk, "")
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/").replace("·", "*").replace("×", "*")
    s = s.replace("−", "-").replace("²", "^2").replace("³", "^3").replace("≈", "=")
    toks: list[tuple[str, str]] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c.isdigit() or (c == "." and i + 1 < n and s[i + 1].isdigit()):
            m = _NUM.match(s, i)
            toks.append(("num", m.group(0)))
            i = m.end()
        elif c == "\\":
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if not m:
                raise ParseError(f"stray backslash at {i}")
            cmd = m.group(1)
            i += m.end()
            if cmd in GREEK:
                toks.append(("id", cmd))
            elif cmd == "pi":
                toks.append(("num", repr(math.pi)))
            elif cmd in FUNCS:
                toks.append(("fn", cmd))
            elif cmd in ("frac", "sqrt"):
                toks.append(("cmd", cmd))
            else:
                raise ParseError(f"unsupported command \\{cmd}")
        elif c.isalpha():
            m = re.match(r"[A-Za-z]+", s[i:])
            word = m.group(0)
            i += m.end()
            if word in FUNCS:
                toks.append(("fn", word))
            elif word == "pi" and "pi" not in known:
                toks.append(("num", repr(math.pi)))
            elif word in known or word in GREEK or len(word) == 1:
                toks.append(("id", word))
            else:
                # split into single letters (implicit product), longest known prefix first
                j = 0
                while j < len(word):
                    for k in range(len(word), j, -1):
                        if word[j:k] in known or k == j + 1:
                            toks.append(("id", word[j:k]))
                            j = k
                            break
        elif c == "_":
            i += 1
            if i < n and s[i] == "{":
                j = s.index("}", i)
                sub = s[i + 1:j]
                i = j + 1
            else:
                m = re.match(r"[A-Za-z0-9]+", s[i:])
                if not m:
                    raise ParseError("bad subscript")
                run = m.group(0)
                base = toks[-1][1] if toks and toks[-1][0] == "id" else ""
                sub = run[0]
                for k in range(len(run), 0, -1):          # longest run that makes a known symbol
                    if base + "_" + run[:k] in known:
                        sub = run[:k]
                        break
                i += len(sub)
            if not toks or toks[-1][0] != "id":
                raise ParseError("subscript without symbol")
            toks[-1] = ("id", toks[-1][1] + "_" + sub.replace(",", ""))
        elif c == "'":
            if toks and toks[-1][0] == "id":
                toks[-1] = ("id", toks[-1][1] + "'")
            i += 1
        elif c in "+-*/^()=,{}":
            toks.append(("op", c))
            i += 1
        else:
            raise ParseError(f"unexpected character {c!r}")
    return toks


# ----------------------------------------------------------------------------- parser
class _P:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, kind=None, val=None):
        k, v = self.peek()
        if k is None or (kind and k != kind) or (val and v != val):
            raise ParseError(f"expected {val or kind}, got {v!r}")
        self.i += 1
        return k, v

    def starts_atom(self):
        k, v = self.peek()
        return k in ("num", "id", "fn", "cmd") or (k == "op" and v in ("(", "{"))

    def expr(self):
        node = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.eat()[1]
            node = ("add" if op == "+" else "sub", node, self.term())
        return node

    def term(self):
        node = self.unary()
        while True:
            if self.peek() in (("op", "*"), ("op", "/")):
                op = self.eat()[1]
                node = ("mul" if op == "*" else "div", node, self.unary())
            elif self.starts_atom():
                node = ("mul", node, self.power())
            else:
                return node

    def unary(self):
        if self.peek() == ("op", "-"):
            self.eat()
            return ("neg", self.unary())
        if self.peek() == ("op", "+"):
            self.eat()
            return self.unary()
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() == ("op", "^"):
            self.eat()
            if self.peek() == ("op", "-"):
                self.eat()
                return ("pow", base, ("neg", self.power_exp()))
            return ("pow", base, self.power_exp())
        return base

    def power_exp(self):
        if self.peek() == ("op", "{"):
            self.eat()
            e = self.expr()
            self.eat("op", "}")
            return e
        return self.atom()

    def group(self):
        k, v = self.eat("op")
        if v == "(":
            e = self.expr()
            self.eat("op", ")")
            return e
        if v == "{":
            e = self.expr()
            self.eat("op", "}")
            return e
        raise ParseError("expected group")

    def atom(self):
        k, v = self.peek()
        if k == "num":
            self.eat()
            return ("num", float(v))
        if k == "id":
            self.eat()
            return ("sym", v)
        if k == "fn":
            self.eat()
            if self.peek() == ("op", "^"):      # e.g. \sin^2 x -> handled as power of result
                self.eat()
                p = self.power_exp()
                arg = self.fn_arg()
                return ("pow", ("fn", v, arg), p)
            return ("fn", v, self.fn_arg())
        if k == "cmd":
            self.eat()
            if v == "frac":
                a = self.group()
                b = self.group()
                return ("div", a, b)
            if v == "sqrt":
                return ("fn", "sqrt", self.group())
        if k == "op" and v in ("(", "{"):
            return self.group()
        raise ParseError(f"unexpected token {v!r}")

    def fn_arg(self):
        if self.peek() in (("op", "("), ("op", "{")):
            return self.group()
        return self.power()


def parse_expr(src: str, known: set[str] | None = None):
    toks = tokenize(src, known or set())
    if any(t == ("op", "=") for t in toks):
        raise ParseError("use parse_equation for equations")
    p = _P(toks)
    node = p.expr()
    if p.i != len(toks):
        raise ParseError(f"trailing input near {toks[p.i][1]!r}")
    return node


def parse_equation(src: str, known: set[str] | None = None):
    toks = tokenize(src, known or set())
    cut = [i for i, t in enumerate(toks) if t == ("op", "=")]
    if len(cut) != 1:
        raise ParseError("an equation needs exactly one '='")
    out = []
    for part in (toks[:cut[0]], toks[cut[0] + 1:]):
        p = _P(part)
        node = p.expr()
        if p.i != len(part):
            raise ParseError("trailing input")
        out.append(node)
    return out[0], out[1]


# ----------------------------------------------------------------------------- utilities
def symbols(node, acc=None) -> set[str]:
    acc = set() if acc is None else acc
    if node[0] == "sym":
        acc.add(node[1])
    elif node[0] in ("num",):
        pass
    elif node[0] == "fn":
        symbols(node[2], acc)
    elif node[0] == "neg":
        symbols(node[1], acc)
    else:
        symbols(node[1], acc)
        symbols(node[2], acc)
    return acc


def to_str(node) -> str:
    t = node[0]
    if t == "num":
        return f"{node[1]:g}"
    if t == "sym":
        return node[1]
    if t == "neg":
        return f"-{to_str(node[1])}"
    if t == "fn":
        return f"{node[1]}({to_str(node[2])})"
    sym = {"add": "+", "sub": "-", "mul": "*", "div": "/", "pow": "^"}[t]
    return f"({to_str(node[1])} {sym} {to_str(node[2])})"


def evaluate(node, env: dict[str, float]) -> float:
    t = node[0]
    if t == "num":
        return node[1]
    if t == "sym":
        if node[1] not in env:
            raise UnknownSymbol(node[1])
        return env[node[1]]
    if t == "neg":
        return -evaluate(node[1], env)
    if t == "fn":
        f = {"exp": math.exp, "ln": math.log, "log": math.log10, "sqrt": math.sqrt, "sin": math.sin,
             "cos": math.cos, "tan": math.tan, "abs": abs, "tanh": math.tanh, "erf": math.erf}[node[1]]
        return f(evaluate(node[2], env))
    a, b = evaluate(node[1], env), evaluate(node[2], env)
    if t == "add":
        return a + b
    if t == "sub":
        return a - b
    if t == "mul":
        return a * b
    if t == "div":
        return a / b
    if t == "pow":
        return a ** b
    raise ParseError(f"unknown node {t}")


def equivalent(a, b, trials: int = 12, seed: int = 7):
    """Randomised numeric comparison. Returns ('equal'|'factor'|'different'|'inconclusive', ratio)."""
    rng = random.Random(seed)
    names = sorted(symbols(a) | symbols(b))
    ratios = []
    for _ in range(trials):
        env = {n: rng.uniform(0.6, 1.8) for n in names}
        try:
            x, y = evaluate(a, env), evaluate(b, env)
        except (ZeroDivisionError, ValueError, OverflowError):
            continue
        if isinstance(x, complex) or isinstance(y, complex) or not (math.isfinite(x) and math.isfinite(y)):
            continue
        ratios.append((x, y))
    if len(ratios) < max(4, trials // 3):
        return "inconclusive", None
    if all(math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12) for x, y in ratios):
        return "equal", 1.0
    if all(abs(y) > 1e-300 for _, y in ratios):
        rs = [x / y for x, y in ratios]
        if all(math.isclose(r, rs[0], rel_tol=1e-8) for r in rs):
            return "factor", rs[0]
    return "different", None


# ----------------------------------------------------------------------------- dimensions
def dim_eval(node, dims: dict[str, Dim], issues: list[dict]) -> Dim:
    """Infer the dimension of an expression; append inconsistencies to issues."""
    t = node[0]
    if t == "num":
        return ONE
    if t == "sym":
        if node[1] not in dims:
            raise UnknownSymbol(node[1])
        return dims[node[1]]
    if t == "neg":
        return dim_eval(node[1], dims, issues)
    if t == "fn":
        d = dim_eval(node[2], dims, issues)
        if node[1] == "sqrt":
            return d ** Fraction(1, 2)
        if node[1] == "abs":
            return d
        if not d.is_dimensionless():
            issues.append({"kind": "transcendental", "where": to_str(node), "dim": str(d)})
        return ONE
    a = dim_eval(node[1], dims, issues)
    if t in ("add", "sub"):
        b = dim_eval(node[2], dims, issues)
        if a != b:
            issues.append({"kind": "sum", "where": to_str(node), "left": str(a), "right": str(b)})
        return a
    if t == "mul":
        return a * dim_eval(node[2], dims, issues)
    if t == "div":
        return a / dim_eval(node[2], dims, issues)
    if t == "pow":
        e = node[2]
        try:
            ev = evaluate(e, {})
        except (UnknownSymbol, ParseError):
            ed = dim_eval(e, dims, issues)
            if not ed.is_dimensionless():
                issues.append({"kind": "exponent", "where": to_str(node), "dim": str(ed)})
            if not a.is_dimensionless():
                issues.append({"kind": "variable_exponent", "where": to_str(node), "dim": str(a)})
            return ONE
        return a ** Fraction(ev).limit_denominator(64)
    raise ParseError(f"unknown node {t}")


def dims_from_units(units: dict[str, str]) -> dict[str, Dim]:
    return {k: parse_unit(v)[0] for k, v in units.items()}
