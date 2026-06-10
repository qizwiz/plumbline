# Pass A annotation synthesis

Produced 2026-06-09 by the pass-a-research-swarm Workflow (8 agents, ~668k tokens).

## Taxonomy (9 categories)

- conservation: sum of parts equals tracked total; no value creation/destruction across all channels (covers Money Flow + AMM k-preservation)
- solvency: contract balance >= recorded obligations at all times (covers Special Storage upper bounds)
- monotonicity: a tracked quantity (rewards accrued, supply, vest) moves in only one direction except via named ops
- authorization: any value-moving effect implies the caller was in the authorized role for that effect (covers Access Control + arbitrary-from)
- no_overflow: critical accumulators stay in bounds, casts are lossless, no silent truncation
- ordering: effects (storage writes) land before external calls or before observers can re-enter (covers CEI / wrong-checkpoint / wrong-interest-rate-order)
- share_conversion: ERC-4626 share/asset round-trip is non-profit, convertTo* deterministic, first depositor cannot inflate share price (covers vault-specific shapes)
- oracle_sanity: price reads bounded by deviation, deterministic across same-tx repeated reads, not flash-loan-manipulable
- replay_protection: each signed message / digest / nonce consumable at most once, chainId bound in hash for cross-chain msgs

## Open questions to flag in the script

- The 9-category taxonomy (pact's 5 + 4 additions) is a SUBSET of Trace2Inv's 8 + ERC-4626 obligations + GPTScan's 10. We dropped: atomicity, front_running_resistance (covered by HYPER tag), preview_fidelity, round_trip_non_profit, slippage_protection, gas_control, time_lock (covered by ordering / TRUST tags). If Pass A produces >15% of CLEAN_SAFETY annotations that don't fit the 9 categories, expand — but the kill criterion is the validation rate, not coverage anxiety.
- The 'none' / UNKNOWN rate is the validation signal. The literature (Bartoletti et al. 2025, arXiv 2509.19153) measured 26-62% of audit properties as inexpressible in symbolic-only languages. If our combined LIVENESS+TRUST+HYPER+EXTERNAL+UNKNOWN exceeds ~50% on the --sample 50, restrict --full run to High/Medium severity only.
- Halmos invariant_* (stateful) mode is v0.3+. Confirm the installed halmos version supports targetContract and --invariant-depth before Pass B generates stateful_invariant tests. Pact's existing prompts assume check_* only.
- ROLE NAMES in solidity_expr (user, attacker, vault) require Pass B to perform binding to the candidate contract's actual identifiers. PropertyGPT's anti-leakage instruction is in the prompt — but if Pass A LLMs ignore it and emit contract-specific names from the finding body, Pass B will pattern-match on those names and degenerate. Hand-grade 20 CLEAN_SAFETY records for role-name discipline before --full run.
- The 'extraction_raw' field MUST be persisted to enable v2 re-parse at zero API cost. If raw output is dropped, a schema bug forces a full re-run ($5-7 + several hours). Confirm pickle write includes extraction_raw for every record, including UNKNOWN/error rows.
- STORAGE_LAYOUT findings (Thunder Loan H-1 family) cannot be discharged by halmos at all. Pass B must route these to a forge-inspect-diff static check OR drop them. Currently they're tag-only; revisit if the corpus has more than ~5% storage-layout findings.
- Cost projection: 1240 findings * ~800 input + 400 output tokens. At claude-3-5-haiku ($0.80/$4.00 per Mtok): ~$1.50/Mtok in + ~$2.00/Mtok out / 1240 = roughly $3-6 total. Verify pricing against the actual OpenRouter model id before --full run; use --sample 50 to extrapolate.
- The driver_shape classifier is load-bearing for Pass B. If LLM judgment on driver_shape is unreliable (e.g. classifies all replay bugs as single_tx_check when stateful_invariant is correct), Pass B emits the wrong halmos pattern. Validate by spot-checking 10 CLEAN_SAFETY records: does the driver_shape match what an expert auditor would pick?
- share_conversion category bundles ERC-4626 round-trip + first-depositor + preview fidelity. If the corpus has many distinct vault shapes, split into share_conversion_roundtrip / first_depositor_inflation / preview_fidelity. Defer until validation data justifies the split.
- Kill criterion: if Pass A produces <10% CLEAN_SAFETY records on the --full run, OR if Pass B's halmos generation has <30% compile rate on CLEAN_SAFETY records, the structural signal is not reaching halmos cleanly. Revert structural_proposer to sol_intent text-only baseline and ship that.

## Noisy-title decision protocol

```
NEVER skip a finding. Every record in findings_index.pkl gets an annotation entry in findings_index_annotated.pkl — UNKNOWN is the safe fallback, NOT omission. Losing the title->NN-rank link is more expensive than carrying a noisy UNKNOWN row.

Decision tree (apply in order, first match wins):

1. Title regex /grief|DoS|halt|stuck|block.*(withdraw|claim|repay)|selfdestruct|unbounded loop|brick/i
   -> extractable=LIVENESS, driver_shape=none, structural_invariants=[], resistant_reason=requires_fairness
   -> Pass B routes to TLA+ shape match (does NOT generate halmos check_*)

2. Title regex /centraliz|rugpull|owner can (steal|drain|change)|admin can|trusted (owner|admin)|backdoor/i
   -> extractable=TRUST, driver_shape=none, structural_invariants=[], resistant_reason=documented_trust_assumption
   -> Pass B emits attention tag only

3. Title regex /front[- ]?run|sandwich|\\bMEV\\b|back[- ]?run|priority gas/i
   -> extractable=HYPER, driver_shape=none, structural_invariants=[], resistant_reason=requires_multi_tx_ordering
   -> Pass B emits attention tag only

4. Title regex /oracle (stale|manipulat)|TWAP|Chainlink (stale|circuit)|price feed/i
   -> extractable=EXTERNAL, driver_shape=none, structural_invariants=[], resistant_reason=requires_external_oracle
   -> Pass B emits attention tag only

5. Title regex /storage (collision|layout)|upgrade.*slot|proxy.*storage/i
   -> extractable=STORAGE_LAYOUT, driver_shape=none, structural_invariants=[], resistant_reason=requires_upgrade_diff
   -> Pass B routes to forge-inspect-diff static check

6. Title regex /cross[- ]?chain|chainId (missing|absent)|signature replay across/i
   -> extractable=PARTIAL, driver_shape=stateful_invariant or single_tx_check
   -> Extract the LOCAL invariant (chainId-in-hash, nonce check) into structural_invariants
   -> resistant_reason=requires_cross_chain_state

7. LLM judges title+body too vague to commit to a single-state boolean over storage
   -> extractable=UNKNOWN, driver_shape=none, structural_invariants=[], resistant_reason=title_too_vague

8. Otherwise -> extractable=CLEAN_SAFETY, driver_shape from {single_tx_check, stateful_invariant, custom_attacker, scripted_trace} per LLM judgment, structural_invariants populated.

Error handling (in Python):
  try:
      rec = llm_extract(finding)
      jsonschema.validate(rec, INVARIANT_SCHEMA)
  except (JSONDecodeError, ValidationError, OpenRouterError) as e:
      rec = {
          'extractable': 'UNKNOWN',
          'driver_shape': 'none',
          'resistant_reason': f'llm_extraction_failed',
          'structural_invariants': [],
          'confidence': 0.0,
          'extraction_raw': raw_response[:2000] if raw_response else str(e)[:500],
          'schema_version': 1,
          'extraction_model': MODEL_ID,
          'extraction_cost_usd': call_cost,
      }
  annotated[finding['finding_id']] = rec   # ALWAYS persist.

Validation gate: after a --sample 50 run, count the extractable distribution. If LIVENESS+TRUST+HYPER+EXTERNAL+UNKNOWN > 50% combined, the corpus is the wrong substrate — restrict to High/Medium severity only or abort. JH hand-grades 20 CLEAN_SAFETY records for faithful/partial/wrong before committing to the --full run.
```

## Few-shot examples

### Example 1

Title: TSwapPool::_swap gives extra tokens every SWAP_COUNT_MAX swaps, breaking x*y=k

Invariant:
```json
{"extractable":"CLEAN_SAFETY","driver_shape":"single_tx_check","resistant_reason":null,"structural_invariants":[{"category":"conservation","name":"constant_product_preserved","solidity_expr":"reserveA_after * reserveB_after >= reserveA_before * reserveB_before","quantities_involved":["reserveA","reserveB"],"violation_pattern":"every Nth swap mints free output tokens to caller without taking matching input","actions_required":["swap"],"scope":"function_postcondition","halmos_directives":[]}],"confidence":0.95}
```

### Example 2

Title: PuppyRaffle::refund sends ETH before zeroing players[idx], allowing reentrancy drain

Invariant:
```json
{"extractable":"CLEAN_SAFETY","driver_shape":"custom_attacker","resistant_reason":null,"structural_invariants":[{"category":"ordering","name":"effect_before_external_call","solidity_expr":"address(vault).balance == balance_before - entranceFee","quantities_involved":["address(vault).balance","entranceFee","players"],"violation_pattern":"external sendValue executes before players[idx] is zeroed; attacker fallback re-enters and drains","actions_required":["enter","refund","fallback_reenter"],"scope":"function_postcondition","halmos_directives":["--loop 4"]}],"confidence":0.9}
```

### Example 3

Title: L1BossBridge::depositTokensToL2 accepts arbitrary from parameter, anyone with allowance can be drained

Invariant:
```json
{"extractable":"CLEAN_SAFETY","driver_shape":"single_tx_check","resistant_reason":null,"structural_invariants":[{"category":"authorization","name":"from_must_be_msg_sender","solidity_expr":"from == msg.sender","quantities_involved":["from","msg.sender"],"violation_pattern":"depositTokensToL2 trusts caller-supplied from address; combined with vault's open allowance any approver is drainable","actions_required":["depositTokensToL2"],"scope":"function_postcondition","halmos_directives":[]}],"confidence":0.95}
```

### Example 4

Title: L1BossBridge::sendToL1 has no nonce or used-digest mapping, signature replayable until vault drained

Invariant:
```json
{"extractable":"CLEAN_SAFETY","driver_shape":"stateful_invariant","resistant_reason":null,"structural_invariants":[{"category":"replay_protection","name":"digest_consumed_at_most_once","solidity_expr":"usedDigest[keccak256(message)] == true","quantities_involved":["usedDigest","keccak256(message)"],"violation_pattern":"sendToL1 recovers signer over (v,r,s,message) with no replay guard; same signature can be re-submitted","actions_required":["sendToL1","sendToL1_replay"],"scope":"contract_invariant","halmos_directives":["--invariant-depth 3"]}],"confidence":0.95}
```

### Example 5

Title: dreUSDs vault allows first depositor to inflate share price via vested-rewards donation

Invariant:
```json
{"extractable":"CLEAN_SAFETY","driver_shape":"scripted_trace","resistant_reason":null,"structural_invariants":[{"category":"share_conversion","name":"victim_recovers_fair_share","solidity_expr":"redeemed_assets * (1 + victim_deposit) >= victim_deposit * total_capital","quantities_involved":["totalAssets","totalSupply","balanceOf"],"violation_pattern":"vested-rewards channel inflates totalAssets without minting matching shares; sharePrice jumps before victim deposit, victim's shares round to zero","actions_required":["attacker_first_deposit","add_rewards","warp","victim_deposit","redeem"],"scope":"cross_function","halmos_directives":["--solver-timeout-assertion 10000"]}],"confidence":0.9}
```

### Example 6

Title: PuppyRaffle::totalFees uses uint64 cast in solc 0.7, truncates fee silently

Invariant:
```json
{"extractable":"CLEAN_SAFETY","driver_shape":"single_tx_check","resistant_reason":null,"structural_invariants":[{"category":"no_overflow","name":"lossless_cast","solidity_expr":"uint256(uint64(fee)) == fee","quantities_involved":["totalFees","fee"],"violation_pattern":"fee accumulator narrows to uint64; values above 2^64-1 truncate and totalFees stops tracking real fee total","actions_required":["selectWinner"],"scope":"function_postcondition","halmos_directives":[]}],"confidence":0.95}
```

### Example 7

Title: PuppyRaffle::selectWinner _safeMint reverts if winner is contract without onERC721Received, bricking raffle

Invariant:
```json
{"extractable":"LIVENESS","driver_shape":"none","resistant_reason":"requires_fairness","structural_invariants":[],"confidence":0.85}
```

### Example 8

Title: Centralization risk: owner can pause vault indefinitely and rugpull deposits

Invariant:
```json
{"extractable":"TRUST","driver_shape":"none","resistant_reason":"documented_trust_assumption","structural_invariants":[],"confidence":1.0}
```

