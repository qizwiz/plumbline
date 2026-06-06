# Submitted — examples/sequence/ (DRY-RUN substrate validation)

Per §6 of the goal contract. Each row has (severity, mechanism, mechanical citation).
**Constraint 4.1 honored**: no row is "model said so" — every row cites a verifier
(TLC | halmos | slither | human_only).

## H-01 Chained signature path bypasses checkpointer when chained-mode flag set
- severity: H
- mechanism: control-flow gate where a flag bypasses the entire signature-validation chain. The chained-sig branch never invokes the checkpointer guard, so any checkpoint-required action is reachable via that path.
- **citation**: `human_only` — bug-class is structural (flag-bypasses-validation-chain) but does not match any of the 5 existing TLA+ FailureMode shapes; new corpus shape "guard-bypassed-by-flag" candidate for between-contest authoring. Surfaced for JH review.
- impact: complete bypass of checkpointer-enforced policy on any session/static path that allows chained-mode
- mitigation: require checkpointer invocation regardless of chained-mode flag, OR remove the flag-based bypass

## H-02 Partial signature replay across session sub-calls
- severity: H
- mechanism: SessionSig validates each per-call signature independently without binding to the batch identity / nonce / index, so a per-call signature extracted from batch b1 can be submitted alone or in a different batch context.
- **citation**: `TLC: Invariant BatchIntegrity is violated` on `docs/tla/PartialSignatureReplay.tla` (NEW spec authored this session). Counterexample at state 2: SubmitBuggy(c=1, b=2) executes call 1 under wrong batch context, BatchIntegrity violated.
- impact: any per-call signature in a batch can be replayed individually with attacker-chosen grouping
- mitigation: include batch_id (or batch hash) in the per-call signed payload; check all batch members present

## M-01 Session signatures replay across wallets due to missing wallet binding
- severity: M
- mechanism: SessionManager-derived signing payload omits `address(this)` from the EIP-712 domain or hashed payload, making the signature wallet-independent. Same session sig accepted by wallets A and B sharing a session signer.
- **citation**: `human_only` — close structural fit with ERC4337StaticSigDoS (caller-bound identity mis-binding) but distinct enough that the existing spec doesn't fit directly. Candidate for new TLA+ shape "cross-wallet-sig-replay" or extension of ERC4337StaticSigDoS to model wallet-binding.
- impact: cross-wallet replay of session signatures
- mitigation: include `address(this)` in the EIP-712 domain or signed payload

## M-02 Static signatures bound to caller revert under ERC-4337 EntryPoint, causing DoS
- severity: M
- mechanism: msg.sender check fails on 4337 path (msg.sender == EntryPoint, not user). All caller-bound static-sig actions become unusable when invoked via EntryPoint.
- **citation**: `TLC: Invariant Authorized4337CallsExecute is violated` on `docs/tla/ERC4337StaticSigDoS.tla`. Counterexample at state 2: ViaEntryPoint path reverts, executed=FALSE.
- impact: permanent DoS for static-sig action class on 4337-invoked wallets
- mitigation: unwrap the user-op submitter from EntryPoint context; do not trust msg.sender for static-sig identity check

## M-03 BaseAuth.recoverSapientSignature returns hard-coded constant
- severity: M
- mechanism: function body returns a sentinel value instead of the recovered signer image hash; all sapient-signer paths short-circuit to the same identity.
- **citation**: `human_only` — TLA+ cannot model "function returns wrong constant" at the state-machine level. This bug-class is what plumbline structurally cannot help with (acknowledged in HYPOTHESES.md self-critique #4). Slither dead-code detector might catch this but did not in the 620 results; would need manual review.
- impact: all sapient signer authorization conflates to a single identity
- mitigation: return the actual recovered image hash, not the sentinel

## M-04 Factory.deploy reverts when contract already exists instead of returning address
- severity: M
- mechanism: CREATE2 path lacks an `extcodesize(predictedAddr) > 0` pre-check; idempotent deploy callers (bundlers, relayers) crash on second invocation.
- **citation**: `TLC: Invariant DeployedNeverReverts is violated` on `docs/tla/Create2NonIdempotent.tla`. Counterexample at state 3: second DeployBuggy(s1) → last_outcome=Reverted while deployed=TRUE.
- impact: bundler/relayer crash on retry; deterministic-address protocols brittle
- mitigation: pre-check `extcodesize > 0` and return the existing address

## L-01 Incorrect intermediate validation of cumulative parameter rules
- severity: L
- mechanism: per-call cumulative-parameter check uses wrong accumulator state; values violating the cumulative rule pass per-call validation.
- **citation**: `human_only` — bug-class is "cumulative_state_drift", TLA+ could model it but writing a spec for one finding is high-effort. Candidate for between-contest corpus growth if pattern repeats.
- mitigation: validate against the correct accumulator state

## L-02 Session value-spent counter increments on fallback and reverted calls
- severity: L
- mechanism: counter-on-failed-path; session budgets exhaust prematurely.
- **citation**: `human_only` — structural bug-class "counter_increment_on_revert", not currently in corpus.
- mitigation: increment counter only after successful call execution

## L-03 Nonce consumption reverts on execution failure enabling signature replay
- severity: L
- mechanism: nonce is intended as one-shot guard but its update reverts together with the inner call, so the signature remains replayable once the revert condition clears.
- **citation**: `human_only` — close to SignatureReplay structurally but the variant is "nonce-only-consumed-on-success" which would need a state-machine variant of the existing spec. Candidate for between-contest extension of SignatureReplay.
- mitigation: persist nonce consumption independent of inner-call outcome

## L-04 Unnecessary bitmasking in LibBytes::readUintX
- severity: L
- mechanism: defensive bitmasks redundant given Solidity calldata semantics; pure gas overhead.
- **citation**: `slither: incorrect-shift at examples/sequence/utils/LibBytes.sol:76` — slither's "contains an incorrect shift operation" detector fires on the exact line (LibBytes.sol#76). Output in `examples/sequence/slither.txt`. Slither also flagged via `too-many-digits` detector for related literals.
- mitigation: remove the redundant bitmask

---

## Summary of citation distribution

- **TLC counterexample (4a)**: 3 leads (H-02, M-02, M-04)
- **slither corroboration (4c)**: 1 lead (L-04)
- **human_only (4d)**: 6 leads (H-01, M-01, M-03, L-01, L-02, L-03)
- **halmos discharge (4b)**: 0 leads (no conservation-flow findings in this corpus)

10 total findings submitted; 2 dropped to triage-skipped.md (L-05, L-06).

Substrate validation outcome: pipeline works end-to-end. Mechanical-citation rate is 4/10 (40%) on this corpus — typical for a wallet-focused codebase where most bugs are signature-flow logic that needs new TLA+ shapes or human review. This is honest data for ADR-006 verifier-router training.
