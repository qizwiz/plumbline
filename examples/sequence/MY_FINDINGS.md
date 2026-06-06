# [DRY-RUN substrate validation] sequence findings

This file would normally be JH's cold-audit findings. For substrate
validation (T9 calibration deferred), it captures the plumbline pipeline's
output for scoring against .ANSWERS.md. The `author` will be marked
distinctly in the resulting rep to avoid confusing this with a real
human-vs-model calibration result.

## H-01 Chained signature path bypasses checkpointer when chained-mode flag set
Control-flow gate where a flag bypasses signature-validation chain. Chained-sig
branch never invokes checkpointer guard. Citation: human_only (novel structural
shape; candidate for between-contest TLA+ corpus growth).

## H-02 Partial signature replay across session sub-calls
SessionSig validates each per-call signature independently without binding to
batch identity / nonce / index. Citation: TLC counterexample on new spec
PartialSignatureReplay.tla — Invariant BatchIntegrity violated at state 2 with
SubmitBuggy(c=1, b=2).

## M-01 Session signatures replay across wallets due to missing wallet binding
SessionManager-derived signing payload omits address(this) from EIP-712 domain.
Citation: human_only (close to ERC4337StaticSigDoS shape but distinct; candidate
for between-contest extension).

## M-02 Static signatures bound to caller revert under ERC-4337 EntryPoint
msg.sender check fails on 4337 path. Citation: TLC counterexample on existing
docs/tla/ERC4337StaticSigDoS.tla — Invariant Authorized4337CallsExecute violated.

## M-03 BaseAuth.recoverSapientSignature returns hard-coded constant
Function body returns sentinel instead of recovered signer image hash. Citation:
human_only (TLA+ structurally cannot model "function returns wrong constant").

## M-04 Factory.deploy reverts when contract already exists instead of returning address
CREATE2 path lacks extcodesize pre-check. Citation: TLC counterexample on
docs/tla/Create2NonIdempotent.tla — Invariant DeployedNeverReverts violated.

## L-01 Incorrect intermediate validation of cumulative parameter rules
Per-call cumulative check uses wrong accumulator state. Citation: human_only.

## L-02 Session value-spent counter increments on fallback and reverted calls
Counter-on-failed-path. Citation: human_only.

## L-03 Nonce consumption reverts on execution failure enabling signature replay
Nonce intended as one-shot guard but update reverts with inner call. Citation:
human_only (close to SignatureReplay shape; candidate for variant).

## L-04 Unnecessary bitmasking in LibBytes::readUintX
Defensive bitmasks redundant. Citation: slither incorrect-shift detector at
utils/LibBytes.sol:76.
