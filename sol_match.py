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


import re


def _lines(path):
    """Tokenize a leads-or-findings file into one entry per atomic claim.

    Two modes, auto-detected:
      (1) markdown-section mode — if the file has `## ` headings, each section
          (heading + flattened body) is ONE finding. Sections whose heading
          starts with a non-finding marker (Clean / Out / Acknowledged /
          Resolved / Fixed) are dropped. This is the right shape for answer
          keys and external contest reports.
      (2) line-by-line mode — original behaviour, used for bulleted lead lists
          (sol_intent output etc.) and any file without `## ` headings.

    Discovered by rep 1 (2026-06-05): markdown answer keys were being scored as
    20 line-findings instead of 2 section-findings → recall numbers untrustworthy.
    """
    text = open(path, encoding="utf-8", errors="replace").read()
    sections = re.findall(r"^##+ +(.+?)\n(.*?)(?=^##+ |\Z)", text, flags=re.M | re.S)
    # heading prefixes that mean "not a finding" (truth-side: Clean/Out-of-scope;
    # lead-side: Intent/Violations/Summary section dividers from sol_intent etc.)
    SKIP_PREFIX = ("clean", "out of scope", "out-of-scope", "acknowledged",
                   "resolved", "fixed", "informational only", "summary",
                   "intent", "violations", "violations —", "violation —",
                   "the promises", "the violations")
    # body markers that mean "section explicitly says no bug found here"
    NO_BUG_BODY = ("no violation", "no mechanistic violation", "no bug",
                   "no issue found", "no planted bug", "is correct",
                   "not a violation", "no concrete violation")
    if sections:
        out = []
        for heading, body in sections:
            head_lc = heading.strip().lstrip("*_ ").lower()
            body_oneline = " ".join(body.split())
            body_lc = body_oneline.lower()
            if any(head_lc.startswith(p) for p in SKIP_PREFIX):
                continue
            if any(p in body_lc for p in NO_BUG_BODY):
                continue
            # pure divider: heading but ~no body
            if len(body_oneline) < 40:
                continue
            # Bullet-list body: each bullet is a separate finding, but ONLY
            # when the heading signals a finding-list (e.g. "Spearbit findings",
            # "Quantstamp findings", "Issues", "Vulnerabilities"). Otherwise
            # bullets are supporting detail and the whole section is one entry.
            # Rep 12→13 surfaced both halves of this: needed the explode, but
            # also needed the gate to avoid blowing up Clean-section bullets.
            FINDING_LIST_WORDS = ("findings", "issues", "vulnerabilities",
                                  "bugs", "violations list", "audit notes")
            is_finding_list = any(w in head_lc for w in FINDING_LIST_WORDS)
            bullets = [ln.strip().lstrip("-*•").strip()
                       for ln in body.splitlines()
                       if ln.strip().startswith(("-", "*", "•"))]
            bullets = [b for b in bullets if len(b) > 20]
            if is_finding_list and len(bullets) >= 2:
                out.extend(bullets)
            else:
                out.append(f"{heading.strip()} — {body_oneline}")
        if out:
            return out
    out = []
    for ln in text.splitlines():
        s = ln.strip().lstrip("-*# ").strip()
        if len(s) > 8:
            out.append(s)
    return out

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
        # 1) deterministic identifier overlap (hard, precise) — pick MAXIMUM
        # overlap (rep 6 surfaced: first-hit `break` collapsed all 3 findings
        # onto the same lead when they shared a common identifier).
        best_j, reason, score = None, None, 0.0
        best_overlap = 0
        for j in range(len(leads)):
            ov = find_ids[i] & lead_ids[j]
            if len(ov) > best_overlap:
                best_overlap = len(ov)
                best_j, reason, score = j, "id:" + ",".join(sorted(ov))[:30], 1.0
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
