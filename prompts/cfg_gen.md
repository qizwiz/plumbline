You are generating a TLC model-checker configuration (.cfg) for a TLA+ FailureMode spec, instantiated for a specific candidate bug from Solidity audit.

THE TLA+ SPEC: {{spec_name}}
THE EXISTING DEFAULT .cfg (used as template):
```
{{default_cfg}}
```

THE CANDIDATE BUG LEAD:
```
{{lead}}
```

YOUR TASK:

Produce a .cfg that instantiates the spec's CONSTANTS to encode the SPECIFIC bug scenario the lead describes. The result must:

1. Use the same SPECIFICATION / INVARIANTS / PROPERTIES lines from the default .cfg (don't change what is being checked)
2. Override CONSTANTS to encode this lead's specific values (e.g., for ERC4337StaticSigDoS, set ExpectedSigner = 1, MsgSender = 0 to encode "msg.sender differs from expected" — the spec's own conventions)
3. Keep model bounded — small enough to run in 30 seconds (typically 1-3 of each parameter)
4. Be valid TLA+ .cfg syntax (CONSTANTS, INVARIANTS, PROPERTIES, SPECIFICATION keywords)

If the lead doesn't clearly map to the spec's CONSTANTS, output the DEFAULT .cfg unchanged.

OUTPUT FORMAT:

Output ONLY the .cfg file contents. No preamble, no commentary, no markdown code fences. Just the raw .cfg text starting with `SPECIFICATION` or `CONSTANTS`.
