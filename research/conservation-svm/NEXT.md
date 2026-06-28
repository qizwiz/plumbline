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
- **L2 HARDENED to real-external + decline control** (2026-06-27, adversarially re-verified). discover.py
  induced a name-agnostic conservation law from MiniTokenBug and transferred it to held-out **StakingRewards**
  (Synthetix/Idle): clean **[PASS] non-vacuous** (skeptic proved it with a false-assert probe: 2 real paths) +
  **1-line-mutant Counterexample** (witness a=b=0x8000…), artifact `discharge-idle/test/Discovered.t.sol`.
  Decline control on access-control **AdminVault** → **principled soft-decline** (engine recognized "no
  conservation pair" in prose + emitted only an inert 0==0 test; halmos `paths:1/bounds:[]` confirms vacuity).
  ASTERISKS: (a) raw auto-emit was VACUOUS (mocked staking token but `_stake`/`withdraw` call `safeTransferFrom`
  unconditionally → all paths reverted) — soundness gate fired, fake PASS not counted, repaired harness-only
  with a MockERC20 (induced RULE + asserts preserved verbatim); the INDUCTION is sound, the EMIT path is the
  weak link. (b) decline is SOFT — only reads correctly if the scorer enforces non-vacuity. (c) DETERMINISM
  shown: **4/4** inductions (3 re-samples + different seed AdminVaultBurn) produced the SAME law + correct
  role-mapping, zero fabrications (discovery/resample/) → n=1-on-SAMPLE killed; n=1-on-TARGET (one real
  held-out contract) remains; still mutation-not-wild-bug. (d) discover.py HARDCODES the bug-class hint
  ("aggregate desync", line 29-30) — the model maps roles, a human named the class; fully-autonomous version
  = derive the class from the seed's own halmos counterexample.

## The MAP (from the DeFiHackLabs density measurement, n=39)
- The **proposer generalizes** (69% of real exploits have an extractable single-contract law, all families).
- The **discharge backend is bug-physics-specific**: halmos = single-contract laws only (~20% reachable
  slice: access/arith/accounting). The **money family — price manipulation (36%) — is 0% halmos-reachable**
  (lives in forked cross-protocol AMM state; symbolic exec can't model it → needs a FORK-STATE verifier).
- DHL (5,600 PoCs, cloned at dhl/) = excellent LABEL corpus, poor halmos-TRAINING substrate as-is
  (~5% dischargeable, ~20% with Etherscan source-harvest).

## NEXT MOVES (ranked)
✅ DONE 2026-06-27: (1) real-external idiom transfer to StakingRewards + (2) diverse-family decline on
AdminVault — both adversarially verified (see "What's PROVEN"). New top moves, surfaced by that pass:
1. **FIRST: harden discover.py's EMIT PATH** so raw emissions are non-vacuous *by construction*. The
   induction is sound but the auto-emitted harness reverted-all-paths (didn't mock the unconditional
   `safeTransferFrom`/`safeTransfer` the staked contract calls). Auto-detect external token calls and emit a
   MockERC20 (mint+approve) by default — kill the manual-repair step that this pass needed.
2. **Enforce the non-vacuity scoring rule** end-to-end: a halmos `[PASS]` counts ONLY if `paths>1` and the
   symbolic inputs actually constrain state. Without this the soft-decline (move #2) mis-reads as a success.
3. **Second seed+target pair** to kill n=1: show the transfer AND the decline aren't one lucky LLM sample
   (re-sample; different seed family; different real held-out contract).
4. **Swap regex → Slither** in conserve.py/conserve_agg.py (`all_state_variables_written()`) — collapses
   the 75% parse-stage declines; Slither proven working via foundry build.
4. **Harvest source-blocked single-contract DHL bugs from Etherscan** (Shadowfi/NovaExchange/Compound) →
   the first REAL un-mutated external catch (the genuinely-special milestone).
5. **Scale discovery to a library** from the DHL dischargeable slice (many seeds → cluster → induce idiom
   library → halmos-validate on held-out). This is L2 at scale = the self-extending engine.

## Also ready (not engine work)
- LinkedIn post drafted (in chat) — honest, novelty-safe (cites Tellegen), holds only on a lit-check.
- Demo is LIVE at qizwiz--plumbline-verification-web.modal.run with tonight's 6 UX fixes + t-swap swap.
