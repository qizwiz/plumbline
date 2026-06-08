"""
render_report — fill the audit report template from plumbline data.

Pipeline:
  reps.jsonl + TLC counterexamples → finding objects → Jinja2 render → report.md

Per-platform per-finding mapping (Code4rena default):

  finding object field           ← plumbline internal source
  ──────────────────────────────  ──────────────────────────────────────
  id ("H-01", "M-02", ...)         severity bucket + autoincrement
  severity                         router verdict + ANSWERS H/M tier mapping
  title                            invariant_name + spec_name + contract
  source_issue_url                 plumbline rep_id link (or per-platform URL)
  attribution.primary              author of the rep (proposer.author)
  description (optional)           matched FailureMode spec's description_head
  impact                           sol_intent lead text + TLC first-violation state
  poc                              TLC counterexample state-trace formatted
  poc_diff_path (optional)         path to runnable Foundry .t.sol test
  mitigation                       matched FailureMode spec's "correct" action description
  tools_used                       "TLC on <SpecName> + Anthropic Sonnet via sol_intent + RAG"
  severity_rationale               weak_confirm STRONG vs WEAK explanation
  references                       RAG-retrieved past .ANSWERS findings
  code_citations                   sol_intent lead's file:line refs

Usage:
  python tools/render_report.py --reps reps.jsonl --target code4rena \\
                                --slug 2026-06-sequence \\
                                --sponsor Sequence \\
                                --out reports/2026-06-sequence.md
"""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(HERE, "templates")


def load_reps(path: str) -> list[dict]:
    return [json.loads(l) for l in open(path) if l.strip()]


def rep_to_finding(rep: dict, idx: int, severity: str) -> dict:
    """Map one plumbline rep → finding object per schemas/finding.json."""
    spec = rep.get("plumbline_provenance", {}).get("matched_spec", "")
    invariant = rep.get("plumbline_provenance", {}).get("tlc_invariant", "")
    contract = (rep.get("contract", {}).get("path", "") or "").split("/")[-1]
    title = f"{invariant} violated in {spec}-shaped flow on {contract}" if spec else (
        rep.get("note") or f"Finding from rep {rep.get('rep_id', '?')[:8]}")
    severity_num_id = f"{severity[0]}-{idx:02d}"
    lead = (rep.get("leads") or [""])[0] if rep.get("leads") else ""
    return {
        "id": severity_num_id,
        "severity": severity,
        "title": title[:200],
        "source_issue_url": (
            f"https://github.com/qizwiz/plumbline/blob/main/reps.jsonl#"
            f"{rep.get('rep_id', '')[:8]}"),
        "attribution": {
            "primary": rep.get("proposer", {}).get("author", "anonymous"),
            "duplicates": [],
        },
        "description": rep.get("plumbline_provenance", {}).get(
            "shape_description", ""),
        "impact": lead[:600] if lead else "(impact derived from TLC counterexample)",
        "poc": rep.get("plumbline_provenance", {}).get(
            "tlc_trace_head", "(TLC counterexample trace pending)"),
        "mitigation": rep.get("plumbline_provenance", {}).get(
            "mitigation", "Apply the matched FailureMode shape's CORRECT branch."),
        "tools_used": (
            f"TLC on {spec or 'matched FailureMode'} + "
            "Anthropic Sonnet via plumbline sol_intent + RAG."),
        "severity_rationale": (
            f"Confirmation strength: "
            f"{rep.get('plumbline_provenance', {}).get('weak_confirm_strength', 'unknown')}."),
        "references": [],
        "code_citations": [],
        "plumbline_provenance": rep.get("plumbline_provenance", {}),
    }


def render_codearena(report_data: dict, out_path: str):
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        sys.stderr.write("install jinja2: pip install jinja2\n"); sys.exit(1)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR),
                      trim_blocks=False, lstrip_blocks=False)
    tmpl = env.get_template("audit_report.j2")
    output = tmpl.render(report=report_data)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").write(output)
    print(f"rendered → {out_path}")
    print(f"  {len(report_data['findings']['high'])} H, "
          f"{len(report_data['findings']['medium'])} M, "
          f"{len(report_data['findings']['qa'])} QA, "
          f"{len(report_data['findings']['gas'])} Gas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", required=True)
    ap.add_argument("--target", default="code4rena",
                    choices=["code4rena", "sherlock", "cantina", "spearbit", "tob"])
    ap.add_argument("--slug", required=True,
                    help="Contest slug, e.g., 2026-06-sequence")
    ap.add_argument("--sponsor", required=True)
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    reps = load_reps(args.reps)
    # Bucket by severity. Plumbline default: STRONG-confirms → H/M decided by
    # mapping confidence; WEAK and unconfirmed → QA.
    high, medium, qa, gas = [], [], [], []
    h_idx = m_idx = 1
    for rep in reps:
        strength = rep.get("plumbline_provenance", {}).get(
            "weak_confirm_strength", "WEAK")
        if strength == "STRONG":
            high.append(rep_to_finding(rep, h_idx, "High")); h_idx += 1
        elif (rep.get("score") or {}).get("recall") and (rep.get("score") or {}).get("recall", 0) > 0.5:
            medium.append(rep_to_finding(rep, m_idx, "Medium")); m_idx += 1
        else:
            qa.append({
                "title": rep.get("note", "QA-tier finding"),
                "url": rep.get("source_url", ""),
            })

    report_data = {
        "sponsor": args.sponsor,
        "slug": args.slug,
        "date": __import__("datetime").date.today().isoformat(),
        "title": args.title or f"{args.sponsor} audit competition",
        "findings_url": f"https://github.com/qizwiz/plumbline/issues?q=label:{args.slug}",
        "contest": "plumbline-solo",
        "contest_id": 0,
        "start_date": "TBD",
        "end_date": "TBD",
        "wardens": ["jonathanhill"],
        "judge": "TBD",
        "assembler": "jonathanhill",
        "high_count": len(high),
        "medium_count": len(medium),
        "qa_count": len(qa),
        "gas_count": len(gas),
        "sloc_count": 0,
        "sloc": 0,
        "findings": {"high": high, "medium": medium, "qa": qa, "gas": gas},
    }

    if args.target == "code4rena":
        render_codearena(report_data, args.out)
    elif args.target == "sherlock":
        # Same template, post-render PDF conversion
        render_codearena(report_data, args.out)
        sys.stderr.write(
            "Sherlock targets PDF — convert via "
            f"`pandoc {args.out} -o {args.out.replace('.md', '.pdf')}`\n")
    else:
        sys.stderr.write(
            f"Target {args.target} stub: render falls back to code4rena. "
            "Per-platform diff implementation pending follow-up research.\n")
        render_codearena(report_data, args.out)


if __name__ == "__main__":
    main()
