"""
cfg_decode — Anthropic-native constrained decoding for TLA+ .cfg generation.

Uses tool-use + JSON Schema to force the LLM to emit values that are
syntactically valid for the spec's CONSTANTS by construction. For each
spec with a schema in schemas/<SpecName>.json, the LLM populates the
schema via tool-use, and we convert the JSON output to .cfg syntax.

Specs without a schema fall back to cfg_generator's free-form LLM path.

Honest scope (per CFG_DECODE.goal.md): this makes generation
deterministic and syntactically clean; it does NOT, on its own, fix
the v1 noise problem (specs' BuggyAction fires regardless of cfg).
The expected v0 outcome is "cleaner cfg, same TLC behavior."

Usage:
    from cfg_decode import generate
    cfg_text, status = generate(spec_name, lead_text)
"""
from __future__ import annotations
import json, os, re, sys
from typing import Any

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMAS = os.path.join(HERE, "schemas")
TLA_DIR = os.path.join(HERE, "docs", "tla")
PROMPT_PATH = os.path.join(HERE, "prompts", "cfg_decode.md")
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "tools"))
import cfg_generator  # for fallback
import prompt_improve as pi
import invariant_agent as agent  # has _CLIENT + _MODEL


def schema_path(spec_name: str) -> str:
    return os.path.join(SCHEMAS, f"{spec_name}.json")


def has_schema(spec_name: str) -> bool:
    return os.path.isfile(schema_path(spec_name))


def _spec_description(spec_name: str, schema: dict) -> str:
    return schema.get("description", "")


def _json_to_cfg(spec_name: str, values: dict) -> str:
    """Convert JSON values to TLA+ .cfg syntax.
    Preserves SPECIFICATION/INVARIANTS/PROPERTIES from the default .cfg."""
    default_cfg_path = os.path.join(TLA_DIR, spec_name + ".cfg")
    if not os.path.isfile(default_cfg_path):
        default_cfg_path = os.path.join(TLA_DIR, "imported", spec_name + ".cfg")
    default = open(default_cfg_path).read()
    # Extract the non-CONSTANTS lines (SPECIFICATION/INVARIANTS/PROPERTIES)
    non_const_lines = []
    in_constants = False
    for ln in default.splitlines():
        if ln.strip().startswith("CONSTANTS"):
            in_constants = True; continue
        if in_constants and (re.match(r"^\s+\w", ln) or ln.strip() == ""):
            if ln.strip() == "":
                in_constants = False; non_const_lines.append(ln)
            continue
        non_const_lines.append(ln); in_constants = False
    # Build new CONSTANTS block
    constants_lines = ["", "CONSTANTS"]
    for k, v in values.items():
        if isinstance(v, list):
            inner = ", ".join(str(x) for x in v)
            constants_lines.append(f"    {k} = {{{inner}}}")
        else:
            constants_lines.append(f"    {k} = {v}")
    return "\n".join(non_const_lines + constants_lines + [""])


def _call_with_tool(spec_name: str, schema: dict, lead: str) -> dict | None:
    """Use Anthropic tool-use to populate the schema. Returns the tool's
    input dict if successful, else None."""
    desc = _spec_description(spec_name, schema)
    tmpl = open(PROMPT_PATH).read()
    prompt = pi.render(tmpl, spec_name=spec_name,
                       spec_description=desc, lead=lead)
    tool = {
        "name": "populate_cfg",
        "description": (
            "Populate the TLA+ .cfg CONSTANTS for spec " + spec_name +
            " given the candidate lead. Pick values that model the lead's"
            " specific mechanism."),
        "input_schema": {k: v for k, v in schema.items() if k != "$schema"},
    }
    try:
        r = agent._CLIENT.messages.create(
            model=agent._MODEL, max_tokens=600,
            tools=[tool], tool_choice={"type": "tool", "name": "populate_cfg"},
            messages=[{"role": "user", "content": prompt}])
    except Exception as e:
        sys.stderr.write(f"cfg_decode tool call failed: {e}\n")
        return None
    for block in (r.content or []):
        if getattr(block, "type", None) == "tool_use" and block.name == "populate_cfg":
            return dict(block.input)
    return None


def generate(spec_name: str, lead: str) -> tuple[str, str]:
    """Returns (cfg_text, status).
    status in {'schema-decoded', 'llm-fallback', 'spec-missing'}."""
    if not has_schema(spec_name):
        # Fall back to existing free-form cfg_generator
        cfg, st = cfg_generator.generate(spec_name, lead)
        return cfg, "llm-fallback" if st == "generated" else st
    schema = json.load(open(schema_path(spec_name)))
    values = _call_with_tool(spec_name, schema, lead)
    if values is None:
        cfg, st = cfg_generator.generate(spec_name, lead)
        return cfg, "llm-fallback"
    try:
        cfg = _json_to_cfg(spec_name, values)
    except Exception as e:
        sys.stderr.write(f"json->cfg conversion failed: {e}\n")
        cfg, st = cfg_generator.generate(spec_name, lead)
        return cfg, "llm-fallback"
    return cfg, "schema-decoded"


def main():
    if len(sys.argv) < 3:
        print("usage: cfg_decode.py <spec_name> <lead_text>", file=sys.stderr)
        sys.exit(1)
    spec, lead = sys.argv[1], sys.argv[2]
    cfg, status = generate(spec, lead)
    sys.stderr.write(f"# cfg_decode status: {status}\n")
    print(cfg)


if __name__ == "__main__":
    main()
