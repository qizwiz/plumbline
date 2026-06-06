# TLA+ FailureMode shapes backlog (use with CORPUS_GROWTH.goal.md)

When you run CORPUS_GROWTH.goal.md, pick one of these candidates as
the target. Each was surfaced as a real bug-class from contest corpora
where the existing 6 FailureModes don't structurally fit.

Use load.sh to set the goal:

```bash
./prompts/goals/load.sh CORPUS_GROWTH | pbcopy
# in Claude Code: /goal <paste>
# then point me at the row below you want to author
```

## Backlog (ranked by reach × ease)

### S-1 — Flag-bypasses-validation-chain  (HIGH reach, MED effort)

**Source**: sequence H-01 (Chained signature with checkpoint usage
disabled can bypass all checkpointer validation).

**Structural shape**: a binary flag selects between two code paths,
one of which omits a critical validation step. Generalizes to any
"feature flag that disables a guard" — flash-loan recursion guard,
sandbox mode, "trusted" path.

**Suggested TLA+ model**: two actions (BuggyPath, CorrectPath), guard
present in CorrectPath only. Invariant: every executed action passed
the guard.

**Related**: ReentrancyDrain (guard misplaced) is similar — there the
guard is present but in wrong position. Here the guard is structurally
absent on one path.

### S-2 — Cross-wallet-sig-replay-no-domain-binding  (HIGH reach, LOW effort)

**Source**: sequence M-01 (Session signatures replay across wallets
due to missing wallet binding).

**Structural shape**: a signature payload omits the wallet/contract
identity from its hashed/signed content, so the same signature is
valid against any wallet that shares the same session signer.
Generalizes to any cross-instance replay — cross-chain, cross-protocol,
cross-network.

**Suggested TLA+ model**: two wallets sharing one session signer; one
session signature created against wallet A but accepted by wallet B.
Invariant: a signature created for wallet W only executes against W.

**Related**: SignatureReplay (no nonce) and ERC4337StaticSigDoS
(caller-bound misread) are siblings. This one is "no identity
binding" — structurally distinct enough to warrant its own shape.

### S-3 — Counter-increment-on-revert  (MED reach, LOW effort)

**Source**: sequence L-02 (Session value-spent counter increments
for fallback and aborted calls). Also adjacent to L-03 (nonce only
consumed on success, not on revert).

**Structural shape**: state mutation that should be conditional on
successful call execution is applied unconditionally — counter
increments before the inner call, never rolled back on revert.
Generalizes to any "fail-open accounting" bug.

**Suggested TLA+ model**: an outer action that increments a counter
then calls an inner action that may abort; the counter doesn't roll
back. Invariant: counter equals number of SUCCESSFUL inner calls.

### S-4 — Cumulative-state-drift  (MED reach, MED effort)

**Source**: sequence L-01 (Incorrect intermediate validation of
cumulative parameter rules).

**Structural shape**: per-call validation uses wrong accumulator
state, so individually-valid calls violate the cumulative invariant
when summed. Generalizes to any "interval arithmetic done wrong" or
"rate limit applied wrong" bug.

**Suggested TLA+ model**: a per-call check that uses pre-state
accumulator instead of post-state; a sequence that satisfies each
per-call check but violates the cumulative bound.

### S-5 — Function-returns-constant  (LOW reach, NOT-TLA+)

**Source**: sequence M-03 (BaseAuth.recoverSapientSignature returns
a constant instead of signer image hash).

**This shape is NOT TLA+-modelable.** It's a data-flow bug — wrong
return value, not a state-machine flaw. Listed here so we DON'T
accidentally try to model it. Verifier path for this class is
slither dead-code detector + manual review.

## Priority advice

For contest-day impact in the immediate term:
- **Do S-2 first** (cross-wallet sig replay) — low effort, high reach,
  closes a gap that already cost us recall on sequence.
- **Do S-1 second** (flag-bypasses-validation-chain) — higher effort
  but the shape is broadly applicable to most wallet codebases.

Skip S-5 entirely (not TLA+-shaped).
