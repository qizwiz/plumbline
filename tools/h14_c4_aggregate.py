"""
h14_c4_aggregate — aggregator for the overnight c4 scale-up.

Runs h14_bug_geometry's measure_corpus against each cloned contest in
/tmp/c4_repos, paired with the .ANSWERS.md in corpus/c4/<contest>/,
then POOLS the per-function bug/clean labels across all contests for
a single big Mann-Whitney U test PER FEATURE with Bonferroni
multiple-testing correction.

Pooled N (across hundreds of functions, hundreds of bugs) is the
statistical-power bump that tonight's N=6-corpora smoke test lacked.

Output: runs/2026-06-10-h14-c4-pooled/results.md + features.json.
"""
from __future__ import annotations
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))
from h14_bug_geometry import (
    extract_bug_implicated_functions, compute_features, mann_whitney_u
)
from measure_graph_hyperbolicity import extract_call_graph

CACHE = Path("/tmp/c4_repos")
OUT = HERE / "runs" / "2026-06-10-h14-c4-pooled"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    contests = sorted(p.name for p in (HERE / "corpus" / "c4").iterdir()
                      if p.is_dir() and (p / ".ANSWERS.md").exists())
    print(f"aggregating across {len(contests)} contests with answer keys")

    all_features = []
    per_contest = []
    for name in contests:
        sol_dir = CACHE / name
        ans = HERE / "corpus" / "c4" / name / ".ANSWERS.md"
        if not sol_dir.exists():
            print(f"  skip {name}: not cloned")
            continue
        if not ans.exists():
            print(f"  skip {name}: no .ANSWERS.md")
            continue
        try:
            nodes_set, edges_dir = extract_call_graph(sol_dir)
        except Exception as e:
            print(f"  skip {name}: parse error {e}")
            continue
        nodes = sorted(nodes_set)
        edges = {(min(u, v), max(u, v)) for u, v in edges_dir if u != v}
        if len(nodes) < 3:
            continue
        bug_names = extract_bug_implicated_functions(ans)
        features = compute_features(nodes, edges, bug_names)
        if not features:
            continue
        n_bug = sum(1 for f in features if f["is_bug"])
        n_clean = len(features) - n_bug
        per_contest.append({"contest": name, "n_v": len(features),
                            "n_bugs": n_bug, "n_clean": n_clean})
        for f in features:
            f["contest"] = name
            all_features.append(f)
        print(f"  {name}: |V|={len(features)} bugs={n_bug} clean={n_clean}")

    print(f"\nPOOLED: total functions={len(all_features)}, "
          f"contests={len(per_contest)}")
    n_bugs = sum(1 for f in all_features if f["is_bug"])
    n_clean = len(all_features) - n_bugs
    print(f"  bug rows: {n_bugs}, clean rows: {n_clean}")

    # Pooled Mann-Whitney per feature
    feature_names = ("degree", "betweenness", "clustering", "is_cut_vertex")
    pooled = {}
    for feat in feature_names:
        a = [int(f[feat]) if isinstance(f[feat], bool) else f[feat]
             for f in all_features if f["is_bug"]]
        b = [int(f[feat]) if isinstance(f[feat], bool) else f[feat]
             for f in all_features if not f["is_bug"]]
        U, p = mann_whitney_u(a, b)
        pooled[feat] = {
            "n_bug": len(a), "n_clean": len(b),
            "bug_mean": statistics.mean(a) if a else None,
            "clean_mean": statistics.mean(b) if b else None,
            "U": U, "p": p,
        }
        sig_bonf = " ★★" if (p is not None and p < 0.05 / 4) else (
            " ★" if (p is not None and p < 0.05) else "")
        print(f"  pooled {feat:<14} n_bug={len(a)} n_clean={len(b)} "
              f"bug={pooled[feat]['bug_mean']} clean={pooled[feat]['clean_mean']} "
              f"p={p}{sig_bonf}")

    (OUT / "features.json").write_text(
        json.dumps([{"contest": f["contest"], "node": f["node"],
                     "is_bug": f["is_bug"], "degree": f["degree"],
                     "betweenness": f["betweenness"], "clustering": f["clustering"],
                     "is_cut_vertex": f["is_cut_vertex"]}
                    for f in all_features], indent=2, default=str))

    md = OUT / "results.md"
    with md.open("w") as f:
        f.write("# H14 second-premise — c4 scale-up (pooled)\n\n")
        f.write(f"Generated {len(per_contest)} contests, {len(all_features)} functions, "
                f"{n_bugs} bug-implicated, {n_clean} clean.\n\n")
        f.write("## Pooled Mann-Whitney U per feature (★ = p<0.05, ★★ = Bonferroni-corrected p<0.0125)\n\n")
        f.write("| Feature | n_bug | n_clean | bug mean | clean mean | p |\n")
        f.write("|---|---|---|---|---|---|\n")
        for feat in feature_names:
            r = pooled[feat]
            sig = " ★★" if (r["p"] is not None and r["p"] < 0.05 / 4) else (
                " ★" if (r["p"] is not None and r["p"] < 0.05) else "")
            f.write(f"| {feat} | {r['n_bug']} | {r['n_clean']} | "
                    f"{r['bug_mean']} | {r['clean_mean']} | "
                    f"{r['p']}{sig} |\n")
        f.write("\n## Per-contest summary\n\n")
        f.write("| Contest | |V| | bugs | clean |\n")
        f.write("|---|---|---|---|\n")
        for c in per_contest:
            f.write(f"| {c['contest']} | {c['n_v']} | {c['n_bugs']} | {c['n_clean']} |\n")
        f.write("\n## Honest interpretation\n\n")
        sig_count = sum(1 for feat in feature_names
                        if pooled[feat]["p"] is not None and pooled[feat]["p"] < 0.05 / 4)
        f.write(f"With pooled N={len(all_features)} functions, "
                f"{sig_count}/4 features survived Bonferroni correction at "
                f"α=0.05/4=0.0125.\n\n")
        if sig_count >= 2:
            f.write("**H14 second premise is SUPPORTED by this data.** Bug-implicated functions "
                    "occupy systematically different positions on the corresponding graph features. "
                    "Geometric priors are informative about bug location.\n")
        elif sig_count == 1:
            f.write("**Weak support for H14.** One feature distinguishes bug from clean at Bonferroni "
                    "correction; the others don't.\n")
        else:
            f.write("**No support for H14 in this data.** No feature distinguishes bug from clean "
                    "at Bonferroni correction. Either the premise is wrong on this corpus, the call "
                    "graph isn't the right representation, or .ANSWERS.md function-name matching is "
                    "missing real bug locations.\n")
    print(f"\nwrote {md}")


if __name__ == "__main__":
    main()
