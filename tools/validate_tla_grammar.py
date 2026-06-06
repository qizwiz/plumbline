"""
validate_tla_grammar — does our Lark CFG accept all 5 hand-authored
FailureMode specs?

The grammar at grammar/tla_failuremode.lark is the CFG that T8 will
wire into a constrained decoder (llguidance or XGrammar) so the LLM
cannot emit a structurally-malformed module.

Per LTLGuard (docs/research/ltlguard-notes.md):
  V3 (G+S = grammar prompt + constrained decode) takes Mistral-7B
  syntactic validity from 5.7% to 15.7%; V4 (+ retrieval) reaches
  87.1%. The CFG is the S lever.

This script is the gate: if it can't parse our own hand-authored
specs, no chance it works for generation. Pass before touching T8.

Run:
  pip install lark
  python tools/validate_tla_grammar.py
"""
from __future__ import annotations

import glob
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAMMAR_PATH = os.path.join(HERE, "grammar/tla_failuremode.lark")
TLA_GLOB = os.path.join(HERE, "docs/tla/*.tla")


def main() -> int:
    try:
        from lark import Lark, exceptions  # type: ignore
    except ImportError:
        print("lark not installed. Install: pip install lark")
        print("(this script is the gate for T8 constrained decoding)")
        return 2

    with open(GRAMMAR_PATH, encoding="utf-8") as f:
        grammar_src = f.read()

    try:
        parser = Lark(grammar_src, parser="earley", start="start")
    except Exception as e:
        print(f"grammar/tla_failuremode.lark FAILED to compile: {e}")
        return 3

    specs = sorted(glob.glob(TLA_GLOB))
    if not specs:
        print(f"no TLA+ specs at {TLA_GLOB}")
        return 4

    pass_count = 0
    fail_count = 0
    for path in specs:
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        try:
            parser.parse(text)
            print(f"  PASS  {name}")
            pass_count += 1
        except exceptions.UnexpectedInput as e:
            print(f"  FAIL  {name}")
            print(f"    {type(e).__name__}: line {e.line} col {e.column}")
            # Show a few lines of context
            lines = text.splitlines()
            lo = max(0, e.line - 2)
            hi = min(len(lines), e.line + 1)
            for i in range(lo, hi):
                marker = " >> " if (i + 1) == e.line else "    "
                print(f"    {marker}{i+1:4d}  {lines[i]}")
            fail_count += 1
        except Exception as e:
            print(f"  FAIL  {name}  ({type(e).__name__}: {e})")
            fail_count += 1

    print()
    print(f"summary: {pass_count} pass, {fail_count} fail (of {len(specs)} total)")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
