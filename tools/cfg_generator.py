"""
cfg_generator — LLM-generated TLC .cfg from a candidate bug lead.

Takes (spec_name, lead_text), reads the spec's existing default .cfg
as a template, asks LLM (via invariant_agent._ask) to produce a .cfg
that encodes the lead's specific values in the spec's CONSTANTS. Falls
back to default .cfg on parse-fail or non-cfg-shaped output.
"""
from __future__ import annotations
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import invariant_agent as agent
import prompt_improve as pi

TLA_DIR = os.path.join(HERE, "docs", "tla")
PROMPT_PATH = os.path.join(HERE, "prompts", "cfg_gen.md")


def _is_cfg_shaped(text: str) -> bool:
    """Quick syntax sanity: must have SPECIFICATION or CONSTANTS keyword."""
    return bool(re.search(r"^\s*(SPECIFICATION|CONSTANTS|INVARIANTS)\b",
                          text, re.M))


def generate(spec_name: str, lead_text: str) -> tuple[str, str]:
    """Returns (cfg_text, status) where status in
    {'schema-decoded', 'generated', 'default-fallback', 'spec-missing'}.

    Tries cfg_decode (schema-constrained tool-use) FIRST for specs
    with a schema in schemas/<SpecName>.json. Falls back to the
    free-form LLM path if no schema or if tool-use fails."""
    # Schema-first path via cfg_decode
    try:
        import cfg_decode
        if cfg_decode.has_schema(spec_name):
            cfg, status = cfg_decode.generate(spec_name, lead_text)
            if status == "schema-decoded":
                return cfg, "schema-decoded"
    except Exception:
        pass
    spec_dir = TLA_DIR
    default_cfg_path = os.path.join(spec_dir, spec_name + ".cfg")
    if not os.path.isfile(default_cfg_path):
        # Try imported/ subdir
        alt = os.path.join(TLA_DIR, "imported", spec_name + ".cfg")
        if os.path.isfile(alt):
            default_cfg_path = alt
        else:
            return "", "spec-missing"
    default_cfg = open(default_cfg_path).read()
    tmpl = open(PROMPT_PATH).read()
    prompt = pi.render(tmpl, spec_name=spec_name, default_cfg=default_cfg,
                       lead=lead_text)
    try:
        out = agent._ask(prompt, 1000)
    except Exception:
        return default_cfg, "default-fallback"
    # Strip code fences if model added them
    out = re.sub(r"^```\w*\n", "", out.strip())
    out = re.sub(r"\n```$", "", out)
    if not _is_cfg_shaped(out):
        return default_cfg, "default-fallback"
    return out, "generated"


def main():
    if len(sys.argv) < 3:
        print("usage: cfg_generator.py <spec_name> <lead_text>", file=sys.stderr)
        sys.exit(1)
    spec_name = sys.argv[1]
    lead = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
    cfg, status = generate(spec_name, lead)
    sys.stderr.write(f"# cfg status: {status}\n")
    print(cfg)


if __name__ == "__main__":
    main()
