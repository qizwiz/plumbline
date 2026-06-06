# Hypotheses for examples/sequence/ (DRY-RUN)

Per §5 of the goal contract.

## Dry-run framing (must read)

This is NOT a real contest. We're validating the substrate end-to-end
on a corpus where `.ANSWERS.md` ground truth is already known. To
keep LLM spend at $0 for this validation, leads.txt was derived from
.ANSWERS.md text rather than from `sol_intent --recall`. In a real
contest with no .ANSWERS, sol_intent would generate these leads
and the spend constraint would apply.

This is a deliberate substitution acknowledged here for transparency
per CLAUDE.md / "honest costing" — never auto-resolve to a guess.

## Hypothesis tree

### H-1: Chained signature path skips checkpointer (H-01 shape)
- bug class: novel — control-flow gate where a flag bypasses an entire validation chain
- confidence: high (ground truth in ANSWERS)
- evidence path: needs TLA+ FailureMode — "guard-bypassed-by-flag" structural shape
- verdict: open (substrate validation pending step 4)
- self-critique: this could be modeled as a state machine where the chained flag
  unsets the checkpointer requirement. Existing FailureModes don't cover it.
- related: H-2 (also sig-flow but distinct mechanism)

### H-2: Partial sig replay across session calls (H-02 shape)
- bug class: ReentrancyDrain/SignatureReplay variant — one-shot promise without per-call binding
- confidence: high (ground truth)
- evidence path: TLA+ via existing SignatureReplay shape, possibly needs new
- verdict: open
- self-critique: SignatureReplay models full-sig reuse; this is FRAGMENT reuse.
  Likely a new structural shape needed. Could be modeled as "shared-prefix replay."
- related: H-3 (cross-wallet sig replay)

### H-3: Session sigs replay across wallets (M-01 shape)
- bug class: ERC4337StaticSigDoS variant — caller-identity binding missing
- confidence: high
- evidence path: TLA+ via ERC4337StaticSigDoS shape (similar — both bind to wrong
  identity)
- verdict: open
- self-critique: structural fit with ERC4337StaticSigDoS not exact — that one is
  about msg.sender misread, this is about wallet-binding-omission. May need new.

### H-4: ERC-4337 static-sig DoS (M-02)
- bug class: ERC4337StaticSigDoS (existing FailureMode)
- confidence: high — already proved
- evidence path: docs/tla/ERC4337StaticSigDoS.tla
- verdict: confirmed by design (this was the original M-02 case)
- self-critique: trivial fit — almost a no-op for substrate validation.
- related: H-3

### H-5: BaseAuth.recoverSapientSignature constant return (M-03)
- bug class: novel — function-returns-constant pattern, semantically gut-removed
- confidence: high (ground truth)
- evidence path: slither dead-code detector might catch this; otherwise human_only
  (it's a code-was-stubbed-out issue, not a state-machine bug)
- verdict: open
- self-critique: TLA+ can't model "function returns wrong constant" — that's not
  a state-machine flaw. Likely human_only with slither corroboration if any.

### H-6: Factory deploy non-idempotent (M-04)
- bug class: Create2NonIdempotent (existing FailureMode)
- confidence: high — already proved
- evidence path: docs/tla/Create2NonIdempotent.tla
- verdict: confirmed by design
- self-critique: another trivial fit — substrate validation easy mode.

### H-7: Wrong accumulator state in intermediate validation (L-01)
- bug class: novel — interval-arithmetic accumulator semantic
- confidence: high
- evidence path: human_only — needs specific cumulative-rule TLA+ modeling
- verdict: likely human_only
- self-critique: TLA+ COULD model this but writing it would be high-effort for
  one finding. The bug-class shape "cumulative_state_drift" is generic.

### H-8: Session counter increments on revert (L-02)
- bug class: novel — counter-on-failed-path
- confidence: high
- evidence path: human_only or slither
- verdict: likely human_only

### H-9: Nonce reverts on inner-execution-failure → replay (L-03)
- bug class: SignatureReplay variant (nonce-only-consumed-on-success vs
  always-consumed)
- confidence: high
- evidence path: TLA+ via SignatureReplay shape (close but not exact)
- verdict: open
- self-critique: this is essentially "nonce as one-shot guard but it's not
  one-shot when the call reverts." Structural fit with SignatureReplay is
  close — might need a variant.

### H-10: Bitmask redundancy (L-04)
- bug class: gas / optimization
- confidence: high
- evidence path: slither (too-many-digits? possibly relevant) or human_only
- verdict: likely human_only (informational)

### H-11: Slot double-RMW inefficiency (L-05)
- bug class: gas
- evidence path: slither or human_only
- verdict: likely human_only

### H-12: Delegate-call validation duplicated (L-06)
- bug class: code quality
- evidence path: slither code-deduplication detector? or human_only
- verdict: likely human_only

## Self-critique summary (per §5)

**What did I miss?**

1. **Bias toward existing FailureMode shapes.** I'm preferentially mapping
   leads to the 5 existing TLA+ shapes when the actual bug-class may not fit.
   H-1 (checkpoint bypass) and H-2 (partial sig replay) likely need NEW TLA+
   modules — discipline matters more than fit.

2. **The dry-run substitution is real but limited.** Using ANSWERS as leads
   conflates "what we know exists" with "what sol_intent would surface." A real
   contest sol_intent run would have false positives, missed findings, and
   different framing. Substrate validation does NOT prove plumbline finds these.

3. **Slither has 620 results we haven't surveyed.** Some may correspond to L
   findings (especially L-04 bitmasks, L-05 inefficiency, L-06 duplication).
   Step 4 should grep slither.txt for each L finding before defaulting to
   human_only.

4. **Sapient signature finding (M-03) is the hard case.** "Function returns
   constant" is not a state-machine flaw. TLA+ doesn't help here. This is
   where slither dead-code detector OR human-review is the only path.
   This is the kind of bug-class plumbline structurally cannot help with —
   important to acknowledge.

## What to look at in Step 4 (specific actions)

For each lead, the planned verifier:

| Lead | Verifier | Expected outcome |
|------|----------|------------------|
| LEAD-1 (H-01) | new TLA+ FailureMode authoring | new shape needed |
| LEAD-2 (H-02) | new TLA+ or SignatureReplay variant | likely new shape |
| LEAD-3 (M-01) | adapt ERC4337StaticSigDoS or new | TBD |
| LEAD-4 (M-02) | existing ERC4337StaticSigDoS.tla | TLC counterexample expected |
| LEAD-5 (M-03) | human_only | TLA+ can't model |
| LEAD-6 (M-04) | existing Create2NonIdempotent.tla | TLC counterexample expected |
| LEAD-7..12 (L-*) | grep slither.txt, then human_only | substrate doesn't cover gas/quality |
