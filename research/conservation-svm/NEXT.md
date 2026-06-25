# Conservation engine — cold-start handoff (2026-06-24 night)

Branch: `conservation-engine-night` (committed locally, NOT pushed). Full record: FINDINGS.md.

## What the engine is
`graph → auto-propose an invariant → halmos discharges it (counterexample=bug, proof=holds)`.
Ethos: **never false** — precision pinned at 1.0 by soundness; recall is the dial we climb.

## What's PROVEN (all with FAIL-buggy / PASS-clean discrimination controls, precision 1.0)
- **Idiom #1** round-trip conservation (conserve.py) — caught dreUSD decimal drain.
- **Idiom #2** aggregate↔collection delta (conserve_agg.py) — caught burn-forgets-totalSupply.
- **Real external discharge** — idle StakingRewards compiled (deps resolved, OZ v4.5 fetched) + halmos
  cleared its sound conservation + caught a 1-line mutation. (discharge-idle/, REPRO.md)
- **L2 idiom DISCOVERY** (discover.py) — an LLM INDUCES the invariant class from one seed bug and
  TRANSFERS it to a different-surface held-out contract; halmos validates. No human writes the idiom.

## The MAP (from the DeFiHackLabs density measurement, n=39)
- The **proposer generalizes** (69% of real exploits have an extractable single-contract law, all families).
- The **discharge backend is bug-physics-specific**: halmos = single-contract laws only (~20% reachable
  slice: access/arith/accounting). The **money family — price manipulation (36%) — is 0% halmos-reachable**
  (lives in forked cross-protocol AMM state; symbolic exec can't model it → needs a FORK-STATE verifier).
- DHL (5,600 PoCs, cloned at dhl/) = excellent LABEL corpus, poor halmos-TRAINING substrate as-is
  (~5% dischargeable, ~20% with Etherscan source-harvest).

## NEXT MOVES (ranked)
1. **FIRST: real-external idiom transfer.** Point discover.py at idle StakingRewards (real, already
   building in discharge-idle/) — induce from MiniToken, transfer to real bytecode, halmos-validate.
   Hardens L2 from contrived held-out → real external.
2. **Diverse-family decline test.** Transfer a CONSERVATION idiom to an ACCESS-CONTROL contract; the
   engine should correctly DECLINE. Proves the seed is load-bearing + idioms are family-specific (kills
   the "the model would induce it anyway" objection).
3. **Swap regex → Slither** in conserve.py/conserve_agg.py (`all_state_variables_written()`) — collapses
   the 75% parse-stage declines; Slither proven working via foundry build.
4. **Harvest source-blocked single-contract DHL bugs from Etherscan** (Shadowfi/NovaExchange/Compound) →
   the first REAL un-mutated external catch (the genuinely-special milestone).
5. **Scale discovery to a library** from the DHL dischargeable slice (many seeds → cluster → induce idiom
   library → halmos-validate on held-out). This is L2 at scale = the self-extending engine.

## Also ready (not engine work)
- LinkedIn post drafted (in chat) — honest, novelty-safe (cites Tellegen), holds only on a lit-check.
- Demo is LIVE at qizwiz--plumbline-verification-web.modal.run with tonight's 6 UX fixes + t-swap swap.
