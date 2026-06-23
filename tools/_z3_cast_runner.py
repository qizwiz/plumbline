"""Subprocess shim so z3 flows through verifier.run_verifier like every other tool.
Reads JSON {body, bits, operand} on stdin, runs sol_z3.check_cast, prints a parseable
result to stdout. The witness it prints is the literal substring the soundness firewall
checks for a CONFIRMED. Run: echo '<json>' | python tools/_z3_cast_runner.py"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sol_z3

req = json.load(sys.stdin)
status, wit = sol_z3.check_cast(req["body"], int(req.get("bits", 64)), req["operand"],
                                is_int=req.get("is_int", False))
if status == "SAFE":
    print("z3 result: unsat — the cast provably cannot truncate under the function's constraints")
elif status == "TRUNCATABLE":
    print("z3 result: sat — truncation witness: " + str(wit))
else:
    print("z3 result: undecided (bit-blast inconclusive / no clean cast extracted)")
