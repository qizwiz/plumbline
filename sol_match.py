"""
sol_match — the DETERMINISTIC matcher. The LLM judge (sol_score) was provably broken: it scored a SUPERSET
of leads LOWER recall than its subset — impossible for a sound matcher, so it wobbles ±1-2 every run and
makes every recall number untrustworthy. This replaces it: embed leads + ground-truth findings once, match
each finding to its best lead by cosine similarity with a FIXED threshold. Same inputs → same numbers,
forever. No LLM, no network at match time, no truncation.

  recall    = findings with a lead above threshold / total findings   (did we catch the bug?)
  precision = leads matching some finding / total leads               (signal vs noise)

  python sol_match.py <leads.txt> <findings.txt> [threshold]
"""
from __future__ import annotations

import sys

import numpy as np
from fastembed import TextEmbedding

_MODEL = None


def _embed(texts):
    global _MODEL
    if _MODEL is None:
        _MODEL = TextEmbedding("BAAI/bge-small-en-v1.5")
    v = np.array(list(_MODEL.embed(list(texts))), dtype=np.float64)
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)


def _lines(path):
    out = []
    for ln in open(path, encoding="utf-8", errors="replace"):
        s = ln.strip().lstrip("-*# ").strip()
        if len(s) > 8:
            out.append(s)
    return out


import re

# common Solidity/finding vocabulary that would cause spurious identifier overlap — not a specific anchor
_STOP = {"function", "address", "amount", "balance", "transfer", "approve", "require", "owner", "tokens",
         "token", "uint256", "contract", "contracts", "across", "value", "values", "public", "external",
         "initialize", "rewards", "staking", "incentives", "withdraw", "deposit", "tokenomics", "treasury",
         "msgsender", "totalsupply", "allowance", "validation", "missing", "unchecked", "reentrancy"}


def _idents(text):
    """Specific FUNCTION identifiers = the anchor that says two descriptions point at the SAME function.
    Solidity convention: functions are camelCase (lowercase-first), contracts are PascalCase — so requiring
    a lowercase-first (or _lowercase) name with an internal capital excludes contract names (too coarse:
    same contract != same bug) and keeps function names like initializeTokenomics, getV3Pool."""
    out = set()
    for w in re.findall(r"_?[a-z][A-Za-z0-9_]{6,}", text):     # lowercase-first or _lowercase, len>=7
        low = w.lower().strip("_")
        if low in _STOP or not re.search(r"[a-z][A-Z]", w):    # must have an internal capital (camelCase)
            continue
        out.add(low)
    return out


def match(leads, findings, threshold=0.80):
    if not leads or not findings:
        return {"recall": 0.0, "precision": 0.0, "matched": [], "missed": findings, "pairs": []}
    lead_ids = [_idents(x) for x in leads]
    find_ids = [_idents(x) for x in findings]
    L, F = _embed(leads), _embed(findings)
    sim = F @ L.T  # [findings x leads]
    pairs, matched_f, lead_hit = [], [], [False] * len(leads)
    for i in range(len(findings)):
        # 1) deterministic identifier overlap (hard, precise)
        best_j, reason, score = None, None, 0.0
        for j in range(len(leads)):
            if find_ids[i] & lead_ids[j]:
                best_j, reason, score = j, "id:" + ",".join(sorted(find_ids[i] & lead_ids[j]))[:30], 1.0
                break
        # 2) embedding fallback (high threshold, paraphrase only)
        if best_j is None:
            j = int(sim[i].argmax())
            if sim[i][j] >= threshold:
                best_j, reason, score = j, f"emb:{sim[i][j]:.2f}", float(sim[i][j])
        ok = best_j is not None
        matched_f.append(ok)
        if ok:
            lead_hit[best_j] = True
        pairs.append((findings[i], leads[best_j] if ok else "—", score, ok, reason or "—"))
    n = len(findings)
    return {
        "recall": sum(matched_f) / n,
        "precision": sum(lead_hit) / len(leads),
        "matched": [findings[i] for i in range(n) if matched_f[i]],
        "missed": [findings[i] for i in range(n) if not matched_f[i]],
        "pairs": pairs,
    }


if __name__ == "__main__":
    leads = _lines(sys.argv[1])
    findings = _lines(sys.argv[2])
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.80
    r = match(leads, findings, thr)
    print(f"RECALL    {r['recall']:.3f}   ({len(r['matched'])}/{len(findings)} findings matched, thr={thr})")
    print(f"PRECISION {r['precision']:.3f}   ({len(leads)} leads)")
    print("\n=== per-finding match (✓ = matched; reason shows id-overlap or embed score) ===")
    for f, l, s, ok, why in sorted(r["pairs"], key=lambda x: -x[2]):
        print(f"  {'✓' if ok else '✗'} [{why[:22]:22s}] {f[:60]:60s} <- {l[:38]}")
