"""
sol_intent — the auditor's brain. Recover what the builders INTENDED (from README, ADRs, NatSpec, and
git history) and find where the Solidity code BETRAYS its own stated intent. The bug is the gap between
what they meant and what they made.

This is the eyes; plumbline (the verifier) is the organ. Run intent first to get the promised invariants
+ a struggle-prioritized list of where code contradicts them; verify the survivors with plumbline.

  python sol_intent.py <repo-or-dir>
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import invariant_agent as agent
import prompt_improve as pi

_SKIP = {"lib", "node_modules", "out", "cache", ".git", "test", "tests", "script", "scripts"}
_FIX = re.compile(r"\b(fix|bug|revert|reverts|again|broke|broken|wrong|incorrect|patch|hotfix|oops)\b", re.I)


def _read_first(root, names):
    for n in names:
        p = os.path.join(root, n)
        if os.path.isfile(p):
            return open(p, encoding="utf-8", errors="replace").read()
    return ""


def collect(root):
    """README + ADRs (highest-confidence intent) + the Solidity sources (excluding tests/libs)."""
    readme = _read_first(root, ["README.md", "README.rst", "README.txt", "README"])[:8000]
    adrs, sols = [], []
    for dp, dns, fs in os.walk(root):
        parts = set(dp.split(os.sep))
        dns[:] = [d for d in dns if d not in _SKIP and not d.endswith(".egg-info")]
        if parts & _SKIP:
            continue
        low = dp.lower()
        for f in sorted(fs):
            fl = f.lower()
            full = os.path.join(dp, f)
            if fl.endswith((".md", ".txt")) and ("adr" in low or "decision" in low or "adr" in fl or fl.startswith("adr")):
                adrs.append(open(full, encoding="utf-8", errors="replace").read())
            elif f.endswith(".sol") and not f.endswith(".t.sol"):
                rel = os.path.relpath(full, root)
                sols.append((rel, open(full, encoding="utf-8", errors="replace").read()))
    return readme, "\n\n---\n\n".join(adrs[:10])[:8000], sols


def git_struggle(root, sols):
    """Per-file struggle score from git history: more fixes/reverts = where they fought bugs = look
    here hardest. Language-agnostic (the distinctive pact-intent signal)."""
    rows = []
    for rel, _ in sols:
        try:
            log = subprocess.run(["git", "-C", root, "log", "--oneline", "--", rel],
                                 capture_output=True, text=True, timeout=20).stdout
        except Exception:
            log = ""
        lines = [l for l in log.splitlines() if l.strip()]
        churn = len(lines)
        struggle = sum(1 for l in lines if _FIX.search(l))
        if churn:
            rows.append((struggle * 3 + churn, churn, struggle, rel))
    rows.sort(reverse=True)
    if not rows:
        return "(no git history — prioritize by code complexity instead)"
    return "\n".join(f"  {rel}: {churn} commits, {struggle} fix/revert" for _, churn, struggle, rel in rows)


def _chunks(sols, budget):
    """Pack source files into chunks under `budget` chars so the finder SEES every file (a finder that
    truncates cannot audit a real codebase — real repos exceed any context window). Keeps files in their
    walk order so same-directory contracts tend to land together."""
    out, cur, sz = [], [], 0
    for rel, src in sols:
        piece = f"// ===== {rel} =====\n{src}"
        if cur and sz + len(piece) > budget:
            out.append(cur); cur, sz = [], 0
        cur.append(piece); sz += len(piece)
    if cur:
        out.append(cur)
    return out


def analyze(root, model=None, budget=120000, prompt="prompts/sol_intent.md",
            rag_exclude_corpus=None, hybrid_rag=False, oracle_loop=False,
            tlc_oracle=False):
    readme, adrs, sols = collect(root)
    if not sols:
        return "(no Solidity sources found under " + root + ")"
    struggle = git_struggle(root, sols)
    tmpl = open(os.path.join(HERE, prompt)).read()
    chunks = _chunks(sols, budget)
    # The prompt is file-backed and SELF-IMPROVING: sol_flywheel scores this output on grounded
    # recall/precision and calls prompt_improve.improve_if_weak, which rewrites sol_intent.md when weak.
    outs = []
    for i, ch in enumerate(chunks):
        sources_text = "\n\n".join(ch)
        retrieved_findings = ""
        retrieved_evidence = ""
        if rag_exclude_corpus is not None:
            sys.path.insert(0, os.path.join(HERE, "tools"))
            if hybrid_rag:
                import hybrid_rag_query
                retrieved_evidence = hybrid_rag_query.retrieve_block(
                    sources_text, rag_exclude_corpus, k=3)
            else:
                import rag_query
                retrieved_findings = rag_query.retrieve_block(
                    sources_text, rag_exclude_corpus, k=3)
        prompt = pi.render(tmpl, struggle=struggle, readme=readme or "(no README)",
                           adrs=adrs or "(no ADRs found)",
                           sources=sources_text,
                           retrieved_findings=retrieved_findings,
                           retrieved_evidence=retrieved_evidence)
        tag = f"\n===== CHUNK {i + 1}/{len(chunks)} =====\n" if len(chunks) > 1 else ""
        chunk_out = agent._ask(prompt, 8000)
        if tlc_oracle and rag_exclude_corpus is not None:
            sys.path.insert(0, os.path.join(HERE, "tools"))
            import tlc_oracle_loop as tol
            items = tol._split_leads(chunk_out)
            stats = {"confirmed": 0, "revised": 0, "needs-larger-bound": 0,
                     "not-a-bug": 0, "no-match": 0, "error": 0}
            new_lines = []
            for kind, ln in items:
                if kind != "LEAD":
                    new_lines.append(ln); continue
                new_ln, status, _ = tol.process_lead(ln, rag_exclude_corpus)
                stats[status] = stats.get(status, 0) + 1
                new_lines.append(new_ln)
            chunk_out = "\n".join(new_lines)
            sys.stderr.write(f"\ntlc_oracle_loop chunk stats: {stats}\n")
        elif oracle_loop and rag_exclude_corpus is not None:
            sys.path.insert(0, os.path.join(HERE, "tools"))
            import oracle_loop as ol
            ol_tmpl = open(os.path.join(HERE, "prompts", "oracle_loop.md")).read()
            items = ol._split_leads(chunk_out)
            revised_lines = []
            for kind, ln in items:
                if kind != "LEAD":
                    revised_lines.append(ln); continue
                revised, _ = ol._revise_lead(ln, rag_exclude_corpus, 0.55, ol_tmpl)
                revised_lines.append("- [REVISED] " + revised.strip()
                                     if revised != ln else ln)
            chunk_out = "\n".join(revised_lines)
        outs.append(tag + chunk_out)
    return "\n".join(outs)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    use_hybrid = "--hybrid-rag" in sys.argv
    use_rag = "--rag" in sys.argv
    use_oracle = "--oracle-loop" in sys.argv
    use_tlc_oracle = "--tlc-oracle" in sys.argv
    use_mechanism = "--mechanism" in sys.argv
    if use_hybrid:
        prompt = ("prompts/sol_find_mechanism.md" if use_mechanism
                  else "prompts/sol_find_hybrid_rag.md")
        corpus = os.path.basename(root.rstrip("/"))
        rag_exclude = corpus
        mode = "RECALL+HYBRID-RAG" + ("+MECHANISM" if use_mechanism else "")
    elif use_rag:
        prompt = "prompts/sol_find_rag.md"
        corpus = os.path.basename(root.rstrip("/"))
        rag_exclude = corpus
        mode = "RECALL+RAG"
    else:
        prompt = "prompts/sol_find.md" if "--recall" in sys.argv else "prompts/sol_intent.md"
        rag_exclude = None
        mode = "RECALL-first" if "--recall" in sys.argv else "intent"
    print(f"sol_intent: {mode} pass for {root}")
    if use_rag or use_hybrid:
        print(f"  (rag index excludes corpus: {rag_exclude})")
    print()
    print(analyze(root, prompt=prompt, rag_exclude_corpus=rag_exclude,
                  hybrid_rag=use_hybrid, oracle_loop=use_oracle,
                  tlc_oracle=use_tlc_oracle))
