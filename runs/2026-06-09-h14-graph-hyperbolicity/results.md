# H14 smoke test — Gromov δ-hyperbolicity of plumbline call graphs

Generated 2026-06-09 by tools/measure_graph_hyperbolicity.py.

Compares Gromov δ-hyperbolicity (4-point condition) of each corpus's function call graph against Erdős-Rényi random graphs with same |V| and |E| (5 trials each).

**Interpretation:** δ=0 means tree-like (maximally hyperbolic). Higher δ means less hyperbolic. ratio < 1 means the real graph is MORE hyperbolic than random.

| Corpus | |V| | |E| | δ_real | δ_random (mean) | ratio | note |
|---|---|---|---|---|---|---|
| puppy-raffle | 9 | 1 | — | — | — | no connected 4-tuples |
| t-swap | 21 | 12 | 0.0 | — | — | OK |
| thunder-loan | 42 | 30 | 1.0 | 0.6 | 1.667 | OK |
| boss-bridge | 9 | 1 | — | — | — | no connected 4-tuples |
| sequence | 148 | 194 | 2.0 | 2.9 | 0.69 | OK |
| dreUSDs | 403 | 241 | 2.0 | 3.1 | 0.645 | OK |

## Honest interpretation

Mean ratio across corpora with measurable δ: **1.000**.

**Inconclusive.** Call graphs and random graphs have similar δ. Either premise is wrong or this measure is the wrong test.

## Caveats (in print before any claim)

- N=5 corpora is small; would need 30+ for statistical claim
- Call graph is one of many possible representations; data-flow / control-flow / inheritance / library-dependency graphs could give different curvature
- Tree-sitter-based call extraction is heuristic; misses dynamic dispatch, library functions, modifiers
- 4-point δ is one curvature measure; others (graph thickness, spectral gap, persistent homology) might disagree
- Even if call graphs are hyperbolic, this doesn't prove bugs cluster at predictable positions (H14's second premise)
- Erdős-Rényi is the most generous baseline; tree baseline would be harder to beat
