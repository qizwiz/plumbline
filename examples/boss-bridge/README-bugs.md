# boss-bridge — bug index

Cross-reference of `.ANSWERS.md` findings to specific line ranges across
`L1BossBridge.sol` / `L1Vault.sol` / `L1Token.sol` / `TokenFactory.sol`
(pragma `0.8.20`). One row = one finding.

| ID   | Title                                                                                                  | File                  | Line range          | Mechanism (one-liner) |
| ---- | ------------------------------------------------------------------------------------------------------ | --------------------- | ------------------- | --------------------- |
| H-1  | `L1BossBridge` token approvals can be stolen via spoofed `from` in `depositTokensToL2`                 | `L1BossBridge.sol`    | 70–78               | `depositTokensToL2(from, l2Recipient, amount)` lets the CALLER pass any `from`; if that `from` has approved the bridge, the caller drains it |
| H-2  | Calling `depositTokensToL2` from vault to vault enables infinite unbacked L2 mint                      | `L1BossBridge.sol`    | 70–78 (call); `L1Vault.sol` 19 (`approveTo`) | passing `from = address(vault)` (which has approved the bridge via `approveTo`) triggers `safeTransferFrom(vault, vault, amount)` — net zero on L1, but emits `Deposit` → L2 mint anyway |
| H-3  | Replay in `withdrawTokensToL1` — same signature drains multiple times                                  | `L1BossBridge.sol`    | 81–102              | message is `(token, 0, transferFrom(vault, to, amount))` with no nonce/expiry; the same (v,r,s) is accepted indefinitely |
| H-4  | `sendToL1` arbitrary call enables `L1Vault::approveTo` self-grant of infinite allowance                | `L1BossBridge.sol`    | 112+ (`sendToL1`); `L1Vault.sol` 19 (`approveTo`) | a signer-signed message with `target=L1Vault` + `data=approveTo(attacker, MAX)` is executed by the bridge, granting attacker unlimited vault allowance |
| H-5  | `CREATE` opcode does not work on zkSync Era                                                            | `TokenFactory.sol`    | 23–30               | `TokenFactory::deployToken` uses inline assembly with `CREATE` opcode; zkSync Era only supports `CREATE2`, so deploy reverts on zkSync |
| H-6  | `DEPOSIT_LIMIT` check enables DoS                                                                      | `L1BossBridge.sol`    | 30 (limit decl); 71 (check) | the limit is on the vault balance; an attacker can frontrun deposits to push the vault near the limit, denying others; or self-deposit to fill the limit |
| H-7  | `withdrawTokensToL1` has no validation that withdraw amount matches deposit amount                     | `L1BossBridge.sol`    | 91–102              | a signed message can declare any `amount`; the bridge enforces no correlation between deposits and withdrawals for a given user; attacker withdraws more than they deposited |
| H-8  | `TokenFactory::deployToken` locks tokens forever                                                       | `TokenFactory.sol`    | 23–30               | `deployToken` returns `addr` but stores it only in `s_tokenToAddress[symbol]`; if the bytecode constructor mints to the factory (not the deployer), tokens are stuck in `TokenFactory` |
| M-1  | Withdrawals prone to unbounded gas consumption ("return bombs")                                        | `L1BossBridge.sol`    | 112+ (`sendToL1` low-level call) | the low-level call uses `bytes` return memcpy; a malicious target can return giant data, exhausting gas |
| L-1  | Lack of event emission during withdrawals and sending tokens to L1                                     | `L1BossBridge.sol`    | 91–102; 112+        | `withdrawTokensToL1` / `sendToL1` execute on-chain effects but don't emit events for indexers / users |
| L-2  | `TokenFactory::deployToken` can create multiple tokens with same `symbol`                              | `TokenFactory.sol`    | 23–30               | no `require(s_tokenToAddress[symbol] == address(0))` — overwriting registry entries |
| L-3  | Unsupported opcode `PUSH0`                                                                             | various (compiled with 0.8.20) | n/a            | `PUSH0` opcode (Shanghai/0.8.20+) isn't supported on some L2s/older EVMs; consider pinning to a pre-Shanghai compiler |
| I-1  | Insufficient test coverage                                                                             | n/a                   | n/a                 | project-wide; critical paths (signer rotation, `sendToL1`) lack tests |

## How to use this index

Same shape as the other corpus indices. When `sol_intent` (or any proposer)
emits a finding, eyeball the cited line range against the row above.
Right-line / wrong-mechanism = labeling problem (Layer 1 should still
match via identifier overlap). Wrong-line entirely = the proposer missed.

H-3 (signature replay) has a halmos scaffold already at
`test/Properties.t.sol :: check_withdrawCannotBeReplayed` — predicted
verdict COUNTEREXAMPLE. H-2 and H-7 are queued for follow-up scaffolds.

Curated, not generated. If the contracts shift, this index drifts.
