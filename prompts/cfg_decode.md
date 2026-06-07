You are populating a TLC model configuration for a TLA+ FailureMode spec, given a candidate audit lead.

THE SPEC: {{spec_name}}
SPEC DESCRIPTION: {{spec_description}}

THE LEAD:
{{lead}}

YOUR TASK:

Use the `populate_cfg` tool to fill in the CONSTANTS that model THIS specific lead's mechanism. The tool's input_schema defines what's valid; pick values such that the spec's invariant violation IS the bug described in the lead.

If the lead does NOT actually describe the bug-class shape this spec models, populate the CONSTANTS with default scenario values anyway — the post-processing step will detect mismatch via vocabulary analysis.

**SPECIAL INSTRUCTION FOR PathChoice (if present in the schema):**

If the spec has a `PathChoice` constant:
- If the lead mentions **EntryPoint, msg.sender forwarding, validateUserOp, UserOperation, ERC-4337, 4337 EntryPoint, bundler in a 4337 context, or account abstraction with EntryPoint**, set `PathChoice = "ViaEntryPoint"`.
- Otherwise (unrelated bug class like reentrancy, overflow, underflow, replay without 4337 context, uint64 issues, create2 issues, etc.), set `PathChoice = "Direct"`.

This ensures the spec only explores the bug-triggering path when the lead's vocabulary matches the spec's bug class.

DO NOT output any text. Use the tool.
