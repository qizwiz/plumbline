"""
tlc_oracle_loop — v1 oracle loop. For each shape-matched lead:
  1. Generate .cfg via cfg_generator
  2. Run TLC (matched .tla + generated .cfg) with 30s timeout
  3. Classify:
     - violation → CONFIRMED (attach counterexample head)
     - no violation → ask LLM to revise lead (or mark NOT-A-BUG / NEEDS-LARGER-BOUND)
     - timeout/error → NEEDS-LARGER-BOUND
Unmatched leads pass through unchanged.

Usage:
    cat leads.txt | python tools/tlc_oracle_loop.py - <exclude_corpus>
"""
from __future__ import annotations
import os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, TOOLS)
import spec_retrieval
import cfg_generator
import invariant_agent as agent
import prompt_improve as pi

TLA_DIR = os.path.join(HERE, "docs", "tla")
TLA_JAR = os.path.join(TLA_DIR, "tla2tools.jar")
REVISE_PROMPT = os.path.join(HERE, "prompts", "tlc_revise.md")


def _split_leads(text):
    """Tag each line as LEAD or OTHER."""
    out = []
    for ln in text.splitlines():
        if re.match(r"^\s*-\s*\[", ln) or re.match(r"^\s*-\s*\*\*", ln):
            out.append(("LEAD", ln))
        else:
            out.append(("OTHER", ln))
    return out


def _run_tlc(spec_name, cfg_text, timeout=30):
    """Returns (violated: bool, trace_head: str, error: str|None)."""
    tla_src = os.path.join(TLA_DIR, spec_name + ".tla")
    if not os.path.isfile(tla_src):
        return False, "", "spec-missing"
    work = tempfile.mkdtemp(prefix="tlc_oracle_")
    try:
        shutil.copy(tla_src, os.path.join(work, spec_name + ".tla"))
        open(os.path.join(work, spec_name + ".cfg"), "w").write(cfg_text)
        os.symlink(TLA_JAR, os.path.join(work, "tla2tools.jar"))
        try:
            p = subprocess.run(
                ["java", "-XX:+UseParallelGC", "-cp", "tla2tools.jar",
                 "tlc2.TLC", "-config", spec_name + ".cfg",
                 "-deadlock", spec_name],
                cwd=work, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "", "timeout"
        out = p.stdout + p.stderr
        if "Invariant" in out and "is violated" in out:
            # Extract first few state lines as trace head
            head = "\n".join(
                ln for ln in out.splitlines()
                if ln.startswith("State ") or "is violated" in ln)[:1200]
            return True, head, None
        if p.returncode != 0 or "Error" in out:
            return False, "", "tlc-error"
        return False, "", None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _revise_via_llm(lead, spec_name, invariants):
    tmpl = open(REVISE_PROMPT).read()
    prompt = pi.render(tmpl, lead=lead, spec_name=spec_name,
                       invariants=invariants)
    try:
        return agent._ask(prompt, 600).strip()
    except Exception:
        return lead


def process_lead(lead, exclude_corpus, threshold=0.55):
    """Returns (revised_lead, status, attached_evidence)."""
    if len(lead.strip()) < 20:
        return lead, "no-match", ""
    try:
        results = spec_retrieval.query_top(lead, k=1)
    except Exception:
        return lead, "error", ""
    if not results or results[0]["cos"] < threshold:
        return lead, "no-match", ""
    if "/imported/" in results[0].get("path", ""):
        return lead, "no-match", ""
    shape = results[0]; spec_name = shape["name"]
    cfg, cfg_status = cfg_generator.generate(spec_name, lead)
    if cfg_status == "spec-missing":
        return lead, "no-match", ""
    violated, trace, err = _run_tlc(spec_name, cfg)
    if violated:
        return ("- [CONFIRMED via TLC on " + spec_name + "] " + lead.strip()
                + "\n  TLC counterexample: " + trace.replace("\n", " | ")[:600]), \
                "confirmed", trace
    if err in ("timeout", "tlc-error"):
        return ("- [NEEDS-LARGER-BOUND on " + spec_name + "] " + lead.strip()
                + " (TLC " + err + ")"), "needs-larger-bound", ""
    # No violation: ask LLM to revise
    inv_desc = shape.get("description_head", "")[:200]
    revised = _revise_via_llm(lead, spec_name, inv_desc)
    if revised.startswith("NOT-A-BUG"):
        return "- [NOT-A-BUG via TLC] " + revised, "not-a-bug", ""
    if revised.startswith("NEEDS-LARGER-BOUND"):
        return "- [NEEDS-LARGER-BOUND] " + revised, "needs-larger-bound", ""
    return "- [REVISED via TLC null] " + revised, "revised", ""


def main():
    if len(sys.argv) < 3:
        print("usage: tlc_oracle_loop.py <leads.txt|-> <exclude_corpus>",
              file=sys.stderr); sys.exit(1)
    src = sys.argv[1]; exclude = sys.argv[2]
    text = sys.stdin.read() if src == "-" else open(src).read()
    items = _split_leads(text)
    stats = {"confirmed": 0, "revised": 0, "needs-larger-bound": 0,
             "not-a-bug": 0, "no-match": 0, "error": 0, "other": 0}
    out_lines = []
    for kind, ln in items:
        if kind != "LEAD":
            out_lines.append(ln); stats["other"] += 1; continue
        new_ln, status, _ = process_lead(ln, exclude)
        stats[status] = stats.get(status, 0) + 1
        out_lines.append(new_ln)
    print("\n".join(out_lines))
    sys.stderr.write(f"\ntlc_oracle_loop stats: {stats}\n")


if __name__ == "__main__":
    main()
