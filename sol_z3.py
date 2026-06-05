"""
sol_z3 — the SOUND disposer (arithmetic subset). For a narrowing-cast candidate uintN(operand), ask z3:
given the function's `require` constraints and the operand's local derivation, CAN the value exceed
2^N-1? Asymmetric & sound: we DROP a candidate only when z3 PROVES it cannot truncate (UNSAT) — that only
ever removes provably-safe noise, never a real finding. Anything z3 can't decide (non-local provenance,
unparseable expr) is KEPT. This is the precision engine for the formalizable claims; vague oracle/economic
claims aren't z3-expressible and pass through untouched.

  verdict in {"SAFE" (drop, proven), "TRUNCATABLE" (keep, witness), "UNDECIDED" (keep)}
"""
from __future__ import annotations

import re

import z3

_SAFE_TOKENS = re.compile(r"^[\w\s.+\-*/%()<>=!&|]+$")


def _vars(expr):
    # identifiers, including dotted (block.timestamp) flattened to a single opaque var
    toks = re.findall(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", expr)
    return {t.replace(".", "_") for t in toks if not re.fullmatch(r"\d+", t)}


def _to_z3(expr, env):
    """Eval a sanitized Solidity arithmetic expression into a z3 Int, with identifiers bound in env."""
    e = expr.replace(".", "_").replace("2**", "2**")  # dotted -> flat var name
    if not _SAFE_TOKENS.match(expr) or "**" in e and not re.search(r"2\*\*\d+", e):
        raise ValueError("unsafe/complex expr")
    # neutralise solidity-only bits we don't model
    e = re.sub(r"\btype\s*\(\s*\w+\s*\)\s*\.\s*max\b", "MAXU", e)
    try:
        return eval(e, {"__builtins__": {}}, env)  # env holds z3 Ints; ops lift to z3
    except Exception as exc:  # noqa: BLE001
        raise ValueError(str(exc))


def check_cast(body, bits, operand, is_int=False):
    """Return (verdict, witness|None). SAFE only if z3 proves no truncation under the function's requires."""
    bound = (2 ** (bits - (1 if is_int else 0))) - 1
    # collect local require conditions and the operand's assignment (one level)
    reqs = re.findall(r"require\s*\(\s*(.*?)\s*(?:,|\))", body, re.S)
    assign = re.search(rf"\b{re.escape(operand)}\s*=\s*([^;]+);", body)
    val_expr = assign.group(1).strip() if assign else operand
    # build env: a z3 Int (>=0, unsigned) for every identifier we see
    idents = _vars(val_expr) | set().union(*[_vars(r) for r in reqs]) if reqs else _vars(val_expr)
    env = {}
    s = z3.Solver()
    for v in idents:
        z = z3.Int(v)
        env[v] = z
        s.add(z >= 0)                       # uint
    env["MAXU"] = z3.IntVal(2 ** 256 - 1)
    # apply require constraints we can translate (skip the ones we can't, soundly — fewer constraints
    # only makes truncation EASIER to satisfy, so we never wrongly prove SAFE)
    for r in reqs:
        for clause in re.split(r"&&", r):
            m = re.match(r"\s*(.+?)\s*(<=|>=|<|>|==|!=)\s*(.+?)\s*$", clause)
            if not m:
                continue
            try:
                lhs, op, rhs = _to_z3(m.group(1), env), m.group(2), _to_z3(m.group(3), env)
            except ValueError:
                continue
            s.add({"<": lhs < rhs, "<=": lhs <= rhs, ">": lhs > rhs, ">=": lhs >= rhs,
                   "==": lhs == rhs, "!=": lhs != rhs}[op])
    # the value reaching the cast
    try:
        val = _to_z3(val_expr, env)
    except ValueError:
        return "UNDECIDED", None
    s.add(val > bound)
    r = s.check()
    if r == z3.unsat:
        return "SAFE", None                 # PROVEN: cannot truncate -> drop (sound)
    if r == z3.sat:
        m = s.model()
        wit = {}
        for d in m.decls():
            v = m[d]
            if z3.is_int_value(v):
                wit[str(d)] = v.as_long()
        return "TRUNCATABLE", wit
    return "UNDECIDED", None
