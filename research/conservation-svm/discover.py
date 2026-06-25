#!/usr/bin/env python3
"""
discover.py — L2: programmatic IDIOM DISCOVERY.

Given ONE seed bug (a buggy contract + the halmos-confirmed violated invariant), an LLM INDUCES the
general invariant CLASS (abstracts it into a reusable rule, not a restatement), then TRANSFERS it to a
HELD-OUT contract with different surface names by writing a halmos test. halmos then validates the
transfer (catches the held-out bug / clears the clean version). The human writes no idiom; the model
induces it and the sound checker validates it.

Usage: discover.py <seed_buggy.sol> <heldout.sol> <HeldoutContractName>
Writes: <heldout_dir>/test/Discovered.t.sol  and prints the INDUCED RULE.
"""
import sys, re, subprocess
from pathlib import Path

seed_path, heldout_path, heldout_name = sys.argv[1], sys.argv[2], sys.argv[3]
seed = Path(seed_path).read_text()
heldout = Path(heldout_path).read_text()
MODEL = "openrouter/anthropic/claude-opus-4.8"

PROMPT = f"""You are the IDIOM-INDUCTION stage of an automated bug-finding engine. You will be shown ONE
seed bug, then must GENERALIZE it and apply the generalization to a different, held-out contract.

# SEED (a contract with a halmos-confirmed bug)
```solidity
{seed}
```
halmos confirmed: `burn()` lets the aggregate desync from the sum of holdings — the contract destroys a
holder's balance WITHOUT a matching change to the aggregate total. A real conservation violation.

# YOUR TASK
1. INDUCE the general invariant CLASS this bug belongs to. Abstract it into a reusable rule about a
   RELATIONSHIP BETWEEN STATE VARIABLES and how functions must preserve it — do NOT mention
   totalSupply/balanceOf or this specific contract. One sentence, prefixed exactly with `RULE:`.
2. Apply that induced rule to the HELD-OUT contract below (note its variable/function names are
   DIFFERENT — you must map the roles, not copy). Write a halmos symbolic test that checks the induced
   invariant on it. Requirements for the test (it must compile under solc 0.8.20 and run under halmos):
   - forge-std-free: declare `interface Vm {{ function assume(bool) external; }}` and
     `Vm constant vm = Vm(0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);`
   - `import {{{heldout_name}}} from "../src/{Path(heldout_path).name}";`
   - contract named `DiscoveredTest`, with `setUp()` deploying the held-out contract, and one
     `function check_invariant(uint256 a, uint256 b) public` that uses `vm.assume` to bound inputs,
     exercises the state-changing functions with symbolic amounts, and `assert`s the induced invariant
     (compare the aggregate delta to the holding delta using int256 casts).
   Output the test inside a single ```solidity fenced block and nothing else after the RULE line.

# HELD-OUT contract (different surface — induce + transfer)
```solidity
{heldout}
```
"""

print(f"[discover] inducing idiom from {Path(seed_path).name} -> transferring to {Path(heldout_path).name} (model {MODEL})", flush=True)
r = subprocess.run(["uvx", "--quiet", "--with", "llm-openrouter", "llm", "-m", MODEL],
                   input=PROMPT, capture_output=True, text=True, timeout=240)
out = (r.stdout or "").strip()
rule = next((ln for ln in out.splitlines() if ln.strip().startswith("RULE:")), "(no RULE line found)")
m = re.search(r"```(?:solidity)?\s*(.*?)```", out, re.S)
print("\n=== INDUCED RULE (the discovered idiom, abstracted from the seed) ===")
print(" ", rule.strip())
if not m:
    print("\n[discover] no fenced test produced. Raw output:\n", out[:1500]); sys.exit(2)
test = m.group(1).strip()
dest = Path(heldout_path).parent.parent / "test" / "Discovered.t.sol"
dest.write_text(test)
print(f"\n=== EMITTED test -> {dest} ===")
print(test)
