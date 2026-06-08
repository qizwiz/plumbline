"""
sol_intent_cascade — sol_intent with cascade pre-filter.

Closes the precision gap between sol_intent (75.6% recall, 13.7% precision)
and the corpus ceiling (93.7%). The cascade compresses 145 functions to
~13 high-signal candidates; this tool runs sol_intent's LLM only on those
candidates, with EACH candidate's matched TLA+ shape + corpus prior as
explicit grounding context.

Architecture:
  1. Run structural_cascade.run_cascade() on the scope
  2. For each survivor, build a structured "candidate brief" (function source
     + AST hits + matched shape + top-3 corpus priors)
  3. Pack all briefs into one prompt and call the LLM via prompts/sol_find_cascade.md
  4. Output a focused verdict list (~13 leads, much higher precision)

This is the per-prior-prompted grounding from the gap-analysis: force the
LLM to CHECK each prior, not just have it in context.

Cost model: roughly 15× cheaper than sol_intent --hybrid-rag --recall
(13 candidates × ~2K tokens vs 145 functions × ~10K tokens), and higher
precision because each LLM call has narrow context.

Usage:
  python tools/sol_intent_cascade.py <scope-dir> [--out leads.txt]

Compare to baseline:
  python sol_intent.py <scope-dir> --hybrid-rag --recall > baseline.txt
  python tools/sol_intent_cascade.py <scope-dir> > cascade.txt
  python tools/score_against_sherlock_truth.py --leads <each> --truth ...
"""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# Reuse production llm + prompt_improve
sys.path.insert(0, str(HERE))
import invariant_agent as agent
import prompt_improve as pi
from tools import structural_cascade as cascade  # type: ignore


def build_candidate_brief(rec: dict, max_text: int = 1200) -> str:
    """Render one cascade survivor as a Markdown brief for the LLM."""
    contract = rec.get("contract") or "(top-level)"
    fn = rec["function"]
    shapes = rec.get("tla_shape_matches", [])
    shape_str = ", ".join(shapes) if shapes else "(none)"
    ast_hits = ", ".join(rec.get("ast_hits", []))
    top1 = rec.get("corpus_top1", {}) or {}
    top1_cos = rec.get("corpus_top1_cos", 0.0)
    top1_str = f"[{top1.get('source','?')}/{top1.get('corpus','?')}/{top1.get('id','?')} cos={top1_cos:.3f}] {top1.get('title','')[:80]}"
    file_path = rec.get("file", "")
    text_head = rec.get("text_head") or ""
    # text_head from structural_cascade is capped at 300 chars; for cascade
    # mode we want more, so re-read the file slice if available.
    if rec.get("start_line") and rec.get("end_line") and file_path:
        full_path = HERE / file_path if not Path(file_path).is_absolute() else Path(file_path)
        if full_path.exists():
            try:
                lines = full_path.read_text(errors="replace").splitlines()
                s, e = rec["start_line"] - 1, min(rec["end_line"], len(lines))
                snippet = "\n".join(lines[s:e])[:max_text]
                text_head = snippet
            except Exception:
                pass
    return (
        f"### CAND {contract}.{fn}  (file: {file_path}:{rec.get('start_line','?')}-{rec.get('end_line','?')})\n"
        f"ast_hits: {ast_hits}\n"
        f"matched_shape: {shape_str}\n"
        f"corpus_top1: {top1_str}\n"
        f"```solidity\n{text_head}\n```\n"
    )


def run(scope_dir: Path, max_candidates: int = 20,
        cos_threshold: float = 0.55) -> tuple[str, dict]:
    """Returns (llm_output_text, cascade_summary_dict)."""
    # 1) cascade
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        cascade_out = Path(tmp.name)
    print(f"running cascade on {scope_dir}...", file=sys.stderr)
    summary = cascade.run_cascade(scope_dir, cascade_out,
                                   cos_threshold=cos_threshold)
    recs = [json.loads(l) for l in cascade_out.read_text().splitlines() if l.strip()]
    print(f"cascade survivors: {len(recs)}", file=sys.stderr)

    if not recs:
        return "(no cascade survivors)", summary
    if len(recs) > max_candidates:
        # Take the top-N by corpus_top1_cos (the strongest signals)
        recs.sort(key=lambda r: r.get("corpus_top1_cos", 0), reverse=True)
        recs = recs[:max_candidates]
        print(f"capped to top-{max_candidates} by corpus cos", file=sys.stderr)

    # 2) build candidate briefs
    briefs = [build_candidate_brief(r) for r in recs]
    candidates_text = "\n".join(briefs)

    # 3) prompt + LLM
    tmpl_path = HERE / "prompts" / "sol_find_cascade.md"
    tmpl = tmpl_path.read_text()
    prompt = pi.render(tmpl,
                       n_total=summary.get("functions_total", "?"),
                       n_candidates=len(recs),
                       candidates=candidates_text)
    print(f"prompt size: {len(prompt)} chars; calling LLM...", file=sys.stderr)
    out = agent._ask(prompt, 6000)
    return out, {"cascade": summary, "candidate_count": len(recs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scope_dir", help="Directory containing .sol files")
    ap.add_argument("--out", help="Output file (default: stdout)")
    ap.add_argument("--max-candidates", type=int, default=20,
                    help="Cap on candidate count (top by corpus cos)")
    ap.add_argument("--cos-threshold", type=float, default=0.55,
                    help="Layer C cosine threshold for cascade")
    args = ap.parse_args()
    output, summary = run(Path(args.scope_dir).resolve(),
                          max_candidates=args.max_candidates,
                          cos_threshold=args.cos_threshold)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(output)
        print(f"wrote → {args.out}", file=sys.stderr)
    else:
        print(output)
    print(f"\nCASCADE FUNNEL: {json.dumps(summary, indent=2)}", file=sys.stderr)


if __name__ == "__main__":
    main()
