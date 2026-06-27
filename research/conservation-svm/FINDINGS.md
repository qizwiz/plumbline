# Conservation-invariant SVM — first proof the auto-proposal loop fires

**2026-06-24.** Smallest-viable-magic test of the refined hypothesis: *a structural reading of a
contract can auto-propose a conservation invariant that a sound checker discharges into a real bug.*

## What was built
`conserve.py` — a regex-level extractor that reads ONLY a contract's source (not any test or answer
key), detects a deposit/withdraw inverse-operation pair over an external ERC20 asset
(`transferFrom`-in + `_mint` = deposit; `_burn` + `transfer`-out = withdraw), and AUTO-EMITS a
round-trip conservation property as a halmos test (`test/AutoConservation.t.sol`). No human writes the
property; it is derived from the in/out structure.

## Result (discrimination control — the part that separates proof from theater)
| contract | auto-derived invariant | halmos |
|---|---|---|
| buggy `dreUSD` (real planted decimals-6↔18 drain) | mint(x)→redeem round-trip returns ≤ x USDC | **FAIL** — counterexample, 0.51s |
| correct 1:1 `CleanVault` (re-derived from its structure) | identical | **PASS** — proved, 0.09s |

Same invariant, FAIL on buggy / PASS on correct → the proposed law is non-vacuous and discriminating.
The riskiest link (graph → auto-proposed invariant) is empirically real, not asserted. The discharge
half (halmos) was already proven; this closes the synthesis half on one idiom.

## Honest caveats
1. Clean control is a division-free 1:1 vault, NOT the literally-patched dreUSD: the faithful fix
   (`dreAmount / 1e12`) made halmos run 120× slower (60s) and return inconclusive with no
   counterexample printed — the symbolic-division choke the pre-build validation predicted. Non-vacuity
   was therefore shown on a division-free correct contract.
2. Extractor is regex-level and crude (misfires on interface declarations; harmless here). Day-1 of the
   build is a real AST/Slither storage-write-graph pass.
3. One contract, one idiom (deposit/withdraw round-trip over an ERC20). This is the SVM, not the engine.

## Next (the week)
- Harden the extractor to a Slither storage-write graph; add idioms: aggregate==Σcollection
  (StakePool totalStaked vs sum(staked)), monotonic supply, supply≤backing.
- Run on real scabench conservation bugs (idle/symmio/etc. are downloaded under runs/glm-bet/src/).
- Measure: of the ~35% conservation-family bugs, what fraction does auto-proposal + halmos catch?
- Address the symbolic-division limitation (bounding / halmos div flags) so faithful fixes verify clean.

## First recall@precision-1.0 measurement (2026-06-24, workflow wf_3375e499)
- **Ethos held: precision 1.0, ZERO vacuous, ZERO false positives.** Extractor honestly DECLINES
  (3 of 4 targets, exit 2) rather than emit a wrong invariant. When it speaks it's never wrong.
- **Idiom-coverage ceiling on the real 41 conservation findings in curated.json:** round_trip=11 (27%),
  +supply_backing(4)+aggregate_sum(2) = **41.5%**. Untapped mass: fee_reward=10, other_conservation=11,
  monotonic_supply=3.
- **Discharge on real external contracts = 0** — idle/symmio/axion/crestal ALL blocked at dependency
  vendoring (OZ import chains unresolved; no node_modules/lib on disk). Discharge proven only on the
  synthetic-dreusd FIXTURE (1 caught) — NOT one of the 41 external findings. So measured external
  recall is 0 so far, gated by build-setup, not by the engine.
- **Funnel:** 4 fed → 1 idiom-match → 1 caught, 0 vacuous. Bottleneck = IDIOM BREADTH at the front
  (literal-regex `_mint`/`_burn`/`.transfer` only); discharge batted 100% on matched (compile + halmos
  + real counterexample in 0.44s). Discharge is NOT the constraint.
- **Two gates (both deterministic, not research walls):** (1) widen idioms via AST — inline mint/burn
  arithmetic, SafeERC20 wrappers, mapping-sum aggregates, multi-call lifecycles; (2) vendor real
  protocols' deps so discharge runs on external bytecode. Then re-run this measurement.

## Idiom #2 PROVEN (2026-06-24) — the recall climb is demonstrated, not just argued
`conserve_agg.py` adds idiom #2: per-function AGGREGATE<->COLLECTION delta conservation. It finds a
partner pair (aggregate uint `total*/supply*` <-> `mapping(address=>uint256)`, confirmed by a credit fn
writing both `+=`) and auto-derives, for each debit fn, `Δaggregate == Δcollection[caller]`.
- MiniToken with the real "burn forgets `totalSupply -=`" desync class (ceiling: "Missing totalSupply
  reduction in burnFrom") -> halmos **FAIL/counterexample 0.24s** (caught).
- Clean twin -> halmos **PASS 0.06s** (cleared). Precision 1.0 held across BOTH idioms.
Two idioms now, both sound (FAIL buggy / PASS clean). Adding an idiom adds catches with the never-false
floor intact — the climb mechanism is real. conserve_agg.py is still regex (constructor-arg + mock-token
handling for non-self-contained targets like dreStaking is the next generalization step).

## Generalization substrate PROVEN: Slither, not regex (2026-06-24)
The regex extractors (conserve.py / conserve_agg.py) are NOT general — they read state writes as text,
so they are blind to inheritance, helper calls (`_update()`), library/SafeERC20 wrappers, storage
pointers, and rely on name guesses. This is exactly why the recall funnel declined 3/4 targets at the
PARSE stage (idiom_match 25%).
The general substrate is **Slither**, already installed and proven working via the foundry build
(`Slither('.')` in a foundry project uses forge's solc; standalone needs `solc` on PATH which is absent).
On dreUSD it resolved inheritance and returned semantic per-function state sets:
  `mint WRITES={balanceOf,totalSupply}` `redeem WRITES={balanceOf,totalSupply}` — i.e. it FOLLOWED
  `_mint`/`_burn` into the inherited solmate ERC20, which regex sees as opaque text.
NEXT BUILD (a swap, not research): rebuild `analyze()` on Slither's `function.all_state_variables_written()`
/`_read()`. This should collapse the 75% parse-stage declines; discharge already bats 100%.
RESIDUAL FRONTIER (unchanged): Slither generalizes the READING (what's co-written); deciding WHICH
co-written pair is a conservation partner is still the synthesis-relevance judgment (LLM proposes,
halmos disposes).

## Dependency wall BROKEN on a real external contract (2026-06-24)
The recall sweep's worst-blocked target — idle `StakingRewards.sol` ("import chain unresolvable") —
now compiles + discharges. Chain: fetch the real dep at the contract's era (OZ v4.5.0 tarball) → remap
→ forge build (105KB artifact) → halmos on idiom #2 `Δ_totalSupply == Δ_balances[caller]` in withdraw
→ **[PASS] 0.20s**. First discharge on REAL EXTERNAL bytecode (not a fixture).
DISCRIMINATION CONTROL (added after a PASS-only is weak / possibly vacuous): mutate withdraw to drop the
one line `_totalSupply -= amount` (the desync class) → halmos **[FAIL] counterexample 0.47s**; clean →
**[PASS]**. The flip proves the check is NON-VACUOUS + DISCRIMINATING on real external bytecode (a vacuous
test would pass both). NOTE: the build itself is routine (CI does it daily) and a bare PASS proves nothing
without this control. It CLEARED idle's real conservation (genuinely sound here) and CATCHES a synthetic
one-line desync — but has NOT caught idle's actual adjudicated bug (that lives in another contract).
The real milestone is catching a REAL (un-mutated) external conservation bug. Two real frictions surfaced + handled: (1) vendored OZ 3.4 vs needed 4.x → fetch
right era; (2) solc pin 0.8.10 EXACT vs forge-std >=0.8.13 → drop forge-std, minimal Vm interface.
Conclusion: dependency resolution is boring engineering (fetch-at-version + remap), NOT a wall; containers
are its productization (per-project toolchain isolation = exactly the solc-pin clash). Artifact +
re-fetch: research/conservation-svm/discharge-idle/ (REPRO.md). NEXT catch-on-real-buggy-external: find a
scabench contract whose conservation is actually broken (recall sweep surfaces them once all compile).

## DeFiHackLabs trainable-density (2026-06-24, wf_fa40e2a0, n=39 stratified 2017-2026)
Measured whether DHL (5,600+ real exploit PoCs) is a trainable substrate for the halmos engine.
- **Extractable invariant: 69%** (8 yes + 19 partial) — the PROPOSAL layer generalizes across all 7 families.
- **Halmos-dischargeable as-written: 5%** (2/39: Parity init-once, Compound-cTUSD sweepToken).
- **Dischargeable with Etherscan source-harvest: ~20%** (access_control + some arithmetic).
- **Family dist:** oracle_price_manipulation 14 (36%, 0/14 dischargeable), access_control 10, conservation 5,
  arithmetic 3, flashloan 3, reentrancy 2, logic 2.
TWO WALLS collapse 69%→5%: (1) MISSING SOURCE — ~17 clean single-contract access/arith bugs blocked only
because the PoC references a deployed addr (FIXABLE: fetch verified Etherscan source → +15%); (2) FORK +
FLASHLOAN + MULTI-PROTOCOL (~60%, all price-manip) — bug only exists against live forked AMM reserve state,
which SYMBOLIC EXECUTION STRUCTURALLY CANNOT MODEL (not fixable by sourcing — wrong tool).
KEY REFRAME (answers "why not generalizable"): the PROPOSER generalizes; the DISCHARGE backend is
BUG-PHYSICS-SPECIFIC. halmos = sound for single-contract laws (~20%, lower-payout slice). Price-manip (the
money family) needs a FORK-STATE verifier (foundry invariant-fuzz / differential replay), NOT halmos.
Generality = one proposer + multiple discharge backends keyed to bug physics.
VERDICT: DHL is a great LABEL corpus, poor halmos-TRAINING substrate as-is. NEXT: harvest the ~6
source-blocked single-contract bugs from Etherscan (4x the trainable slice to ~20%), prove discrimination
there; treat price-manip majority as a separate fork-state-backend problem. Clone: research/conservation-svm/dhl/.

Repro: `python research/conservation-svm/conserve.py examples/synthetic-dreusd/dreUSD.sol dreUSD`
then `cd examples/synthetic-dreusd && ../../.venv/bin/halmos --function check_autoRoundTripConserves`.

## L2 — programmatic IDIOM DISCOVERY proven (2026-06-24)
discover.py: an LLM call (opus) INDUCES the invariant class from ONE seed bug (MiniToken:
totalSupply/balanceOf/mint/burn) and TRANSFERS it to a held-out contract with DIFFERENT surface
(Vault: g_totalAssets/userShares/enter/exit) by writing a halmos test — no human writes the idiom.
halmos validates the transfer: clean Vault [PASS] 0.13s, buggy Vault [FAIL] counterexample 0.23s.
The model mapped roles itself (totalSupply->g_totalAssets etc) and emitted aggDelta==holdDelta.
SCOPE: proves transfer-ACROSS-SURFACE + sound discrimination; held-out is contrived (not real external
yet) and it's one-seed-one-idiom. Subtle: a strong model might induce from the held-out alone, so
"seed load-bearing" isn't proven — clean test is transferring a conservation idiom to an access-control
contract and watching it correctly DECLINE. NEXT RIGOR: point discover.py at idle StakingRewards (real
external, already building) + diverse-family decline test + scale to a library from DHL.
Repro: python research/conservation-svm/discover.py fixtures/MiniTokenBug.sol discovery/src/Vault.sol Vault
       then halmos --function check_invariant --contract DiscoveredTest (swap Vault.sol clean<->buggy)

## Proposer-stage DISCRIMINATION control + a false-positive fix (2026-06-27)
The precision-1.0-by-soundness claim has a hidden premise: the structural proposer must DECLINE
where conservation is the wrong law. Every fixture so far was conservation-POSITIVE, so the decline
half was never regression-guarded. Added the negative control (the $0, no-halmos, no-LLM half of the
"transfer-to-access-control should DECLINE" test that FINDINGS above asked for):
  - fixtures/AdminVault.sol      — admin contract; _mint, .transfer, transferFrom present but never
                                    paired in one function. Must DECLINE.
  - fixtures/AdminVaultBurn.sol  — same, plus an admin _burn. Must DECLINE.
  - test_proposer_discrimination.py — asserts PROPOSE on CleanVault, DECLINE on both admin contracts.
    Non-vacuous by construction (a stuck-yes detector fails the negatives, a stuck-no fails CleanVault).

Building it caught a REAL soundness bug. The `functions()` regex `function ...\)[^{]*\{` jumped across
`;`-terminated IERC20 interface method declarations and brace-matched the WHOLE contract interior under
a phantom function named after the first interface method. On AdminVaultBurn that phantom fused
transferFrom-in+_mint AND _burn+.transfer-out into a spurious inverse pair → conserve.py FALSE-PROPOSED
`a transfer(x) -> transfer() round-trip must not return more rewardToken than x` on an admin-only
contract. That is a precision-1.0 violation at the proposer stage (halmos would then vacuously pass or
spuriously fail a meaningless property).

FIX: tightened the gap class `[^{]*` -> `[^{};]*` in both conserve.py and conserve_agg.py so a
`;`-terminated declaration can't match as a definition. After the fix: AdminVault/AdminVaultBurn DECLINE;
CleanVault and dreUSDfixed still PROPOSE but now via their REAL `['mint','redeem']` (the phantom
interface-method entries are gone — cleaner, same outcome). conserve_agg.py unchanged on MiniToken
(no interface there) — fix is defensive parity.
Repro: python research/conservation-svm/test_proposer_discrimination.py   (exit 0 = discrimination holds)
