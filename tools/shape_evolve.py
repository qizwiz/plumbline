"""
shape_evolve — score TLA+ mutations against held-out Sherlock findings.

Wraps tools/spec_mutator.py (which generates + TLC-verifies novel
mutations) with the missing piece: coverage fitness on the 146
Sherlock-graded findings that have NO existing-shape RAG prior at cos>0.7.

This is the grounded-self-improvement loop for the shape library:
  1. spec_mutator.py generates novel mutations (already shipped)
  2. shape_evolve.py embeds each mutation's invariant + parent shape
     description and scores coverage on the 146 unmatched findings
  3. Top-ranked mutation = candidate to bank as next shape

The fitness signal is SOUND (no LLM-as-judge):
  - TLC discharge yes/no (deterministic, by spec_mutator)
  - Cosine ≥ 0.7 to unmatched finding (deterministic, by embedding)
  - Anti-similarity: penalize variants whose centroid is within
    cos > 0.85 of any existing shape (otherwise they just rediscover
    the original)

Usage:
  python tools/shape_evolve.py [--score-only]     # score existing mutations
  python tools/shape_evolve.py --runs 20          # generate + score new ones
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TLA_DIR = HERE / "docs" / "tla"
MUT_DIR = TLA_DIR / "mutations"
SHERLOCK_COVERAGE = HERE / "corpus" / "calibration" / "sherlock_coverage.jsonl"
COS_COVER = 0.7      # threshold: shape covers a finding
COS_ANTI = 0.85      # threshold: too-close-to-existing → penalty


def load_unmatched_findings() -> list[dict]:
    """Findings from sherlock_coverage.jsonl with no existing shape at cos>0.7."""
    if not SHERLOCK_COVERAGE.exists():
        sys.exit(f"missing: {SHERLOCK_COVERAGE}. Run "
                 "tools/calibrate_against_sherlock.py first.")
    out = []
    for line in SHERLOCK_COVERAGE.read_text().splitlines():
        if not line.strip(): continue
        rec = json.loads(line)
        for f in rec.get("findings", []):
            if f.get("top1_cos", 0) <= COS_COVER:
                out.append({"id": f["id"], "severity": f["severity"],
                            "title": f["title"], "contest": rec["slug"]})
    return out


def extract_signature(tla_path: Path) -> str:
    """Build a shape signature from a .tla module: doc header + invariant +
    state vars + action names. This is what we embed."""
    text = tla_path.read_text(errors="replace")
    # Header comment block (between ( * and * ))
    m = re.search(r"\(\*(.*?)\*\)", text, re.S)
    header = m.group(1) if m else ""
    # All invariant declarations of the form `Name == ...` whose LHS doesn't
    # start with internal keywords
    invs = []
    for m in re.finditer(r"^([A-Z]\w+)\s*==\s*(.+?)(?=\n[A-Z][\w]*\s*==|\n=====|\Z)",
                         text, re.M | re.S):
        name = m.group(1)
        if name in ("Init", "Next", "Spec", "TypeInvariant", "Fairness"):
            continue
        invs.append(f"{name}: {m.group(2).strip()[:200]}")
    # VARIABLES list
    vm = re.search(r"VARIABLES\s*\n((?:\s+\w+,?\s*\n)+)", text)
    varlist = ""
    if vm:
        varlist = " ".join(x.strip().rstrip(",") for x in vm.group(1).split("\n")
                           if x.strip())
    # Mutation kind if present
    mut = ""
    mm = re.search(r"\\\* MUTATION:\s*(.+)", text)
    if mm:
        mut = f"mutation: {mm.group(1).strip()}"
    sig = f"{mut}\nvars: {varlist}\nheader: {header[:1500]}\ninvariants: {' | '.join(invs[:5])[:1500]}"
    return sig


def load_existing_shape_signatures() -> dict[str, str]:
    """For anti-similarity penalty: signatures of the 9 originals."""
    out = {}
    for tla in sorted(TLA_DIR.glob("*.tla")):
        if tla.name.startswith("imported_"): continue
        out[tla.stem] = extract_signature(tla)
    return out


def score_mutations(mutations: dict[str, str],
                    unmatched: list[dict],
                    existing_sigs: dict[str, str]) -> list[dict]:
    """Embed each mutation signature + each unmatched finding title,
    measure how many unmatched findings come within cos>0.7. Apply
    anti-similarity penalty."""
    sys.path.insert(0, str(HERE / "tools"))
    import spec_retrieval as sr
    from fastembed import TextEmbedding
    import numpy as np

    embedder = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    # Embed unmatched findings
    finding_texts = [sr._lift_idents(f["title"]) for f in unmatched]
    finding_embs = np.array(list(embedder.embed(finding_texts)))
    finding_norms = np.linalg.norm(finding_embs, axis=1)

    # Embed existing shape signatures (for anti-similarity)
    existing_sig_texts = [sr._lift_idents(s) for s in existing_sigs.values()]
    existing_embs = np.array(list(embedder.embed(existing_sig_texts)))
    existing_norms = np.linalg.norm(existing_embs, axis=1)
    existing_names = list(existing_sigs.keys())

    # Embed mutation signatures
    mut_names = list(mutations.keys())
    mut_texts = [sr._lift_idents(s) for s in mutations.values()]
    mut_embs = np.array(list(embedder.embed(mut_texts)))
    mut_norms = np.linalg.norm(mut_embs, axis=1)

    results = []
    for i, name in enumerate(mut_names):
        sims_findings = finding_embs @ mut_embs[i] / (finding_norms * mut_norms[i])
        covered = sum(1 for s in sims_findings if s > COS_COVER)
        covered_findings = [unmatched[j]["title"][:50]
                            for j in range(len(unmatched))
                            if sims_findings[j] > COS_COVER]
        # Anti-similarity: closest existing shape
        sims_existing = existing_embs @ mut_embs[i] / (existing_norms * mut_norms[i])
        closest_idx = int(sims_existing.argmax())
        closest_cos = float(sims_existing[closest_idx])
        penalty = closest_cos > COS_ANTI
        fitness = 0 if penalty else covered
        results.append({
            "mutation": name,
            "covered_count": covered,
            "fitness_score": fitness,
            "closest_existing": existing_names[closest_idx],
            "closest_existing_cos": closest_cos,
            "anti_sim_penalty": penalty,
            "covered_findings_sample": covered_findings[:5],
        })
    results.sort(key=lambda r: (-r["fitness_score"], -r["covered_count"]))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score-only", action="store_true",
                    help="Score existing docs/tla/mutations/ without "
                         "regenerating.")
    ap.add_argument("--runs", type=int, default=0,
                    help="If >0, run spec_mutator with this many runs first.")
    args = ap.parse_args()

    if args.runs > 0:
        print(f"running spec_mutator --runs {args.runs}...", file=sys.stderr)
        subprocess.run([sys.executable, str(HERE / "tools" / "spec_mutator.py"),
                        "--runs", str(args.runs)], check=True)

    print("loading unmatched Sherlock findings...", file=sys.stderr)
    unmatched = load_unmatched_findings()
    print(f"  {len(unmatched)} findings with no existing-shape RAG prior cos>{COS_COVER}",
          file=sys.stderr)

    print("loading mutations...", file=sys.stderr)
    mut_files = sorted(MUT_DIR.glob("*.tla"))
    mutations = {p.stem: extract_signature(p) for p in mut_files}
    print(f"  {len(mutations)} mutations: {sorted(mutations.keys())}",
          file=sys.stderr)

    if not mutations:
        sys.exit("no mutations to score. Run with --runs N to generate.")

    print("loading existing shape signatures...", file=sys.stderr)
    existing = load_existing_shape_signatures()
    print(f"  {len(existing)} existing shapes: {sorted(existing.keys())}",
          file=sys.stderr)

    print("\nscoring mutations vs unmatched findings...", file=sys.stderr)
    results = score_mutations(mutations, unmatched, existing)

    print("\n" + "=" * 70)
    print("SHAPE EVOLVE RANKING")
    print("=" * 70)
    print(f"{'mutation':<40} {'cov':>4} {'fit':>4} {'closest':<25} {'cos':>5}")
    print("-" * 80)
    for r in results:
        print(f"{r['mutation']:<40} {r['covered_count']:>4} "
              f"{r['fitness_score']:>4} {r['closest_existing']:<25} "
              f"{r['closest_existing_cos']:>5.2f}"
              + ("  ←ANTI" if r['anti_sim_penalty'] else ""))

    top = results[0] if results else None
    if top and top["fitness_score"] > 0:
        print(f"\nTOP: {top['mutation']}  fitness={top['fitness_score']}")
        print(f"  covered findings (sample):")
        for f in top["covered_findings_sample"]:
            print(f"    - {f}")
        out = HERE / "corpus" / "calibration" / "shape_evolve_ranking.json"
        out.write_text(json.dumps(results, indent=2))
        print(f"\nfull ranking → {out}")
    else:
        print("\nNo mutation passed anti-similarity penalty AND covered >0 findings.")
        print("Try: --runs 20 to generate more mutations.")


if __name__ == "__main__":
    main()
