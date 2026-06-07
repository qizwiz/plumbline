You are populating a TLC model configuration for a TLA+ FailureMode spec, given a candidate audit lead.

THE SPEC: {{spec_name}}
SPEC DESCRIPTION: {{spec_description}}

THE LEAD:
{{lead}}

YOUR TASK:

Use the `populate_cfg` tool to fill in the CONSTANTS that model THIS specific lead's mechanism. The tool's input_schema defines what's valid; pick values such that the spec's invariant violation IS the bug described in the lead.

If the lead does NOT actually describe the bug-class shape this spec models, populate the CONSTANTS with default scenario values anyway — the post-processing step will detect mismatch via vocabulary analysis.

DO NOT output any text. Use the tool.
