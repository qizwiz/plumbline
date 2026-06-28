# Induction determinism — kills n=1 on the SAMPLE axis (2026-06-27)

Re-ran discover.py for the real-external transfer (held-out = StakingRewards) across 3 fresh
samples of the SAME seed (MiniTokenBug) + 1 DIFFERENT seed (AdminVaultBurn). Result: **4/4**
induced the same conservation law and mapped it correctly (totalSupply<->aggregate,
balanceOf<->per-entity holding, Delta-equality assert across stake/stakeFor + withdraw).
Zero fabrications, zero wrong mappings. The induced law is the one already proven non-vacuous +
mutant-discriminating in move #1 (discharge-idle/test/Discovered.t.sol).

## Induced RULE per run (verbatim)
### mtb_1
RULE: For any pair consisting of an aggregate accumulator and the per-entity quantities it is meant to sum over, every state-changing function that alters an entity's quantity must apply an equal and opposite-or-matching change to the aggregate, so the aggregate always equals the sum of the individual quantities.

### mtb_2
RULE: Any function that mutates an individual component of a partitioned quantity must apply an equal and simultaneous mutation to the aggregate accumulator that is defined to equal the sum of all such components, so that the aggregate's delta always equals the component's delta.

### mtb_3
RULE: Any function that mutates a holder's share of a quantity must apply an equal and opposite change to the aggregate accumulator of that quantity, so that the aggregate always equals the sum of all individual shares.

### seed2_avb
RULE: Any state variable that is defined as the running aggregate (sum) of a set of per-entity holdings must change by exactly the same signed amount as the total change across those holdings in every state-mutating function, so that no operation can alter an individual holding without an equal-and-opposite-or-matching adjustment to the aggregate.

## Honest caveats
- These are RAW emissions; per-sample end-to-end halmos was NOT re-run (the emit-path harness
  vacuity from move #1 recurs). What is shown: the INDUCED LAW + role-mapping is stable; that law
  is independently proven discriminating in move #1. n=1 on the TARGET axis (one real held-out
  contract) remains — that is the 'second real external target' swing.
- discover.py hardcodes the bug-CLASS hint ('aggregate desync') in the prompt (line 29-30); the
  model does the role-MAPPING, not class discovery. Fully-autonomous version = derive the class
  from the seed's own halmos counterexample.
