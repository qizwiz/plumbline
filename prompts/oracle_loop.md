You are reviewing a candidate audit lead against a structurally-matching bug-class shape from a TLA+ FailureMode library.

THE LEAD:
{{lead}}

THE MATCHED SHAPE:
Name: {{shape_name}}
Description: {{shape_description}}

YOUR TASK:

Decide whether this shape's bug-class actually applies to the lead. The shape match is a structural-similarity hint, not a guarantee.

If the shape APPLIES, REWRITE the lead in 3-5 lines:
(a) GROUND: identify the SPEC's variables (e.g., ExpectedSigner, NonceTable, accepted[s][w]) AS THEY APPEAR in this code. Name the concrete Solidity identifiers that play the role of each spec variable.
(b) VIOLATION: state the specific invariant that is violated by which sequence of operations on this code. Reference the invariant by name (e.g., NoOverpayment, EnforcementHonored).
(c) ATTACK: one-line attack path. Who calls what with what input to make the invariant violation manifest.

Example of a well-grounded rewrite:
- Lead: "validateUserOp called by EntryPoint may bypass static-sig check"
- Shape: ERC4337StaticSigDoS (require msg.sender == ExpectedSigner)
- Rewrite:
  GROUND: ExpectedSigner = wallet.staticSigConfig.signer; msg.sender = ENTRY_POINT during validateUserOp; the user-op's actual submitter is userOp.sender (different from msg.sender).
  VIOLATION: invariant CallerBoundAuthRespected fails — static-sig accepts when msg.sender = ENTRY_POINT instead of the configured ExpectedSigner.
  ATTACK: any user-op submitted through ENTRY_POINT triggers validateUserOp, the static-sig check evaluates `msg.sender == ExpectedSigner` against ENTRY_POINT (not the submitter), and either always-fails (DoS) or always-passes (auth bypass) depending on whether ENTRY_POINT equals ExpectedSigner.

If the shape DOES NOT APPLY (e.g., the code path doesn't actually involve the spec's mechanism), return:
- Original: {{lead}}
- NOTE: shape {{shape_name}} does not apply — <one-line reason>.

Output only the rewrite or the NOTE. No preamble. No commentary outside the structure above.
