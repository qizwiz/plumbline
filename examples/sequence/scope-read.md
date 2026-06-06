# Scope read — examples/sequence/

Step 1 of the plumbline contest goal. Read before any tool runs.

## Framing
DRY-RUN target — not an active contest. Used to validate the substrate works
end-to-end on a corpus where ground truth (`.ANSWERS.md`) exists. Stage flag:
`MODE=dryrun`. `MY_FINDINGS.md` not authored (no cold-audit; the calibration
drill T9 is deferred per JH constraint).

## In-scope (4854 SLOC total)

Top-level wallet + factory + ERC-4337 surface:
- `Wallet.sol`, `Wallet.huff` (Huff fallback — out of plumbline's TLA+ reach)
- `ERC4337FactoryWrapper.sol`
- `Factory.sol`
- `Estimator.sol`, `Simulator.sol`, `Guest.sol`
- `Stage1Module.sol`, `Stage2Module.sol`

modules/ (auth + ERC4337 logic):
- `auth/` (signer/sapient logic)
- `Calls.sol`
- `ERC4337v07.sol`  ← M-02 entrypoint candidate
- `Hooks.sol`, `Implementation.sol`
- `Nonce.sol`, `Payload.sol`
- `ReentrancyGuard.sol`, `Storage.sol`

extensions/:
- `passkeys/`, `recovery/`, `sessions/`

utils/:
- `Base64.sol`, `LibBytes.sol`, `LibOptim.sol`
- `P256.sol`, `WebAuthn.sol`

## Out of scope (false-positive trap)

- `Wallet.huff` — Huff inline assembly. Plumbline's TLA+ FailureModes are
  written for Solidity semantics; mapping Huff opcodes back to TLA+ guards
  is high-effort, low-confidence. Out of scope this session.
- Anything in `test/`, `script/`, `lib/` (none of which appear; sequence's
  package layout is contracts-only at this level).

## Declared assumptions (from README)

The README is mostly build/test setup. No explicit assumption section. The
relevant implicit assumptions reading the contract names:

- ERC-2470 deterministic deployment is trusted (`Factory.sol` uses CREATE2).
- ERC-4337 v0.7 EntryPoint is trusted (`modules/ERC4337v07.sol`).
- Sessions/passkeys/recovery extensions are optional capability surfaces
  layered on top of the base wallet.
- The Wallet.huff fallback handles raw execute paths.

## Prize-pool weighting

Not declared (this is a past corpus, not an active contest). Treating
HIGH > MED > LOW as default order for triage prioritization. The known
findings in `.ANSWERS.md` are predominantly MED — sequence v3 was relatively
clean by Cantina contest standards.

## My time budget for this session

- Goal: validate the 8 DONE-WHEN steps cycle end-to-end on this corpus.
- Step 4 (citation per lead) is the longest pole — expecting 30-60 min.
- Hard ceiling: $20 LLM spend (constraint 4.4).
- If session ends mid-step 4, RESUME.md handoff per §7.

## Recall floor (constraint check, per Step 3)

leads.txt must have ≥ 4854 / 200 ≈ **24 leads** as the recall floor. Without
`.ANSWERS.md` cross-check (because this is supposed to be a contest, not a
calibration drill — though .ANSWERS.md does exist here for dry-run scoring),
the 24-lead floor is the bar.

## Hypothesis preview (informs Step 4 verifier routing)

Two known shapes already covered by existing TLA+ FailureModes:
- `ERC4337StaticSigDoS.tla` ↔ M-02 (ERC4337v07.sol)
- `Create2NonIdempotent.tla` ↔ M-04 (Factory.sol)

Open candidate bug-classes to look for (per knowledge of wallet codebases):
- Nonce reuse / replay (Nonce.sol)
- Signature malleability / passkey verification gaps
- Session expiry / scope drift
- Reentrancy in execute path (ReentrancyGuard.sol — does it cover everything?)
- Recovery-mode authorization gaps
- ERC-1271 isValidSignature spoofability

## Done

Step 1 complete. Moving to Step 2: slither baseline.
