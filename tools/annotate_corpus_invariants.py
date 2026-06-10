"""
annotate_corpus_invariants — Pass A of the structural_proposer build.

For each of the 1,240 findings in tools/findings_index.pkl, use the LLM
to (a) extract a structural invariant from the finding's title + body,
then (b) adversarially validate the extraction with a second LLM call
that tries to REFUTE it. Both results are stored as
`structural_invariant` (with `validation` sub-field) on each finding.
The annotated index then feeds Pass B (tools/structural_proposer.py,
not yet built).

Per docs/design/structural_proposer.md + agentic-orchestration notes
adopted 2026-06-09:
  - One-time pre-pass, estimated cost $10-15 OpenRouter (Sonnet 4.5)
    — doubled from initial $5-8 estimate by adding the adversarial
    re-extraction validator
  - Output: re-pickled findings_index.pkl with the new field
  - Validation: dump 50 sampled annotations to a markdown file for JH
    review, with a summary of how many the adversarial critic refuted

The extraction + validation prompt design adopts patterns from Claude
Code's deep-research Workflow harness — specifically the "spawn N
independent skeptics per finding, each prompted to REFUTE, default to
refuted=true if uncertain" pattern. This is the cheapest insurance
against poisoning Pass B with bad annotations.

The extraction prompt + few-shot examples + invariant schema are
FILLED IN FROM the pass-a-research-swarm Workflow output (in-progress
at time of skeleton write). Sections marked PLACEHOLDER_FROM_SWARM are
stubs to replace once research lands.

Usage:
  # Smoke test on 10 findings (no write):
  python3 tools/annotate_corpus_invariants.py --limit 10 --dry-run

  # Sample 50 + dump validation markdown:
  python3 tools/annotate_corpus_invariants.py --sample 50 --validation-out \\
    runs/2026-06-09-pass-a/validation.md

  # Full annotation run (writes findings_index.pkl in place; original
  # backed up to findings_index.pkl.bak):
  python3 tools/annotate_corpus_invariants.py --full

Resumability:
  The script writes partial results to runs/<date>-pass-a/partial.jsonl
  every 50 findings. If interrupted, re-running with --full picks up
  where it left off.
"""
from __future__ import annotations
import argparse
import json
import os
import pickle
import random
import shutil
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
INDEX_PATH = HERE / "tools" / "findings_index.pkl"
SPEC_PATH = HERE / "docs" / "design" / "pass_a_spec.json"
RUNS_DIR = HERE / "runs" / f"{date.today().isoformat()}-pass-a"

# ============================================================
# Spec loaded from docs/design/pass_a_spec.json
# (produced by the pass-a-research-swarm Workflow on 2026-06-09)
# ============================================================
#
# To iterate on the prompt or schema, edit pass_a_spec.json — the script
# picks up changes on next run. The spec separation lets us version the
# research-derived design independently of this driver code.

with SPEC_PATH.open() as _f:
    _SPEC = json.load(_f)

INVARIANT_CATEGORIES: list[str] = _SPEC["category_list"]
FEW_SHOT_EXAMPLES: list[dict] = _SPEC["few_shot_examples"]
INVARIANT_SCHEMA: str = _SPEC["invariant_field_schema"]
EXTRACTION_PROMPT_TEMPLATE: str = _SPEC["llm_prompt_full_text"]
NOISY_TITLE_PROTOCOL: str = _SPEC["noisy_title_protocol"]
HALMOS_TEMPLATE: str = _SPEC["halmos_template"]
OPEN_QUESTIONS: list[str] = _SPEC["open_questions"]

# ============================================================
# LLM wiring (uses plumbline's existing llm.py / PACT_LLM_* env)
# ============================================================

sys.path.insert(0, str(HERE))


def _get_client():
    from llm import make_client, resolve_model
    from dotenv import load_dotenv
    load_dotenv(HERE / ".env")
    return make_client(), resolve_model()


def _parse_json_response(txt: str) -> dict | None:
    """Strip ```json fences if present and parse. Returns None on failure."""
    txt = txt.strip()
    if txt.startswith("```"):
        txt = txt.split("```", 2)[1]
        if txt.startswith("json"):
            txt = txt[4:]
        txt = txt.strip()
        if txt.endswith("```"):
            txt = txt[:-3].strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def extract_invariant(finding: dict, client, model: str,
                      max_tokens: int = 800) -> dict:
    """Extract a structural_invariant from one finding via LLM.

    Returns a dict matching INVARIANT_SCHEMA (or {"category": "none",
    "reason": ...} if the bug class doesn't extract cleanly).
    """
    # Append per-finding context to the spec's standing prompt. The synthesis
    # spec contains the taxonomy + protocol + few-shots inline; we just hand
    # it the specific finding.
    prompt = EXTRACTION_PROMPT_TEMPLATE + (
        f"\n\n# Finding to annotate\n\n"
        f"- Title: {finding['title']}\n"
        f"- Severity: {finding['severity']}\n"
        f"- Source: {finding.get('source','?')}\n"
        f"- Corpus: {finding.get('corpus','?')}\n"
        f"- Body:\n{finding.get('body','')[:3000]}\n\n"
        f"Return ONLY the JSON object — no prose, no fences."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    txt = resp.content[0].text if resp.content else ""
    parsed = _parse_json_response(txt)
    if parsed is None:
        return {"category": "none",
                "reason": "LLM output not valid JSON",
                "raw_output": txt[:500]}
    return parsed


# ============================================================
# Adversarial re-extraction validator
# ============================================================
#
# Per the agentic-orchestration patterns adopted 2026-06-09: every
# extraction is checked by a SECOND LLM call with a distinct ADVERSARIAL
# prompt that tries to REFUTE the extraction. Default to refuted=true if
# uncertain. Extractions flagged refuted=true are kept in the corpus
# annotation but marked so Pass B can either skip them or weight them
# down. Doubles Pass A LLM cost (~$5 → ~$10) but is cheap insurance
# against poisoning Pass B with bad invariants.
#
# Pattern source: Claude Code's deep-research Workflow harness, which
# documents "spawn N independent skeptics per finding, each prompted to
# REFUTE. Default to refuted=true if uncertain. Prevents plausible-but-
# wrong findings from surviving."

VALIDATOR_PROMPT_TEMPLATE = """You are an adversarial reviewer auditing an automated extraction.

A previous LLM read a smart-contract bug finding and extracted a structural invariant from it. Your job is to REFUTE the extraction — find any reason to doubt that the extracted invariant faithfully captures what the bug actually violates. Default to refuted=true if you have ANY doubt.

BUG FINDING:
- Title: {title}
- Severity: {severity}
- Body: {body}

EXTRACTED INVARIANT (the thing you are refuting):
```json
{invariant}
```

QUESTIONS TO ASK:
1. Does the invariant describe a property the bug actually violates?
2. Is the invariant's category correct?
3. Is the invariant precise enough that a sound verifier could check it?
4. Could this invariant HOLD even when the bug fires? (If yes, the extraction is wrong — refute.)
5. Is the invariant about the WRONG quantity / state variable / contract?
6. Does the invariant generalize the bug too narrowly or too broadly?

Return JSON ONLY (no prose, no fences):
{{"refuted": <bool>, "reason": "<one sentence explaining why or why not>"}}"""


def validate_extraction(finding: dict, inv: dict, client, model: str,
                        max_tokens: int = 300) -> dict:
    """Adversarial critic. Returns {refuted: bool, reason: str}.

    Skipped (returns {refuted: false, reason: "skipped"}) for extractions
    that already self-reported category=none — no point validating a null.
    """
    if inv.get("category") == "none":
        return {"refuted": False, "reason": "skipped — extraction self-reported null"}
    prompt = VALIDATOR_PROMPT_TEMPLATE.format(
        title=finding["title"],
        severity=finding["severity"],
        body=finding.get("body", "")[:2000],
        invariant=json.dumps(inv, indent=2),
    )
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    txt = resp.content[0].text if resp.content else ""
    parsed = _parse_json_response(txt)
    if parsed is None:
        return {"refuted": True,
                "reason": "validator output not parseable JSON — defaulting to refuted"}
    # be defensive about types
    refuted = bool(parsed.get("refuted", True))
    reason = str(parsed.get("reason", ""))[:300]
    return {"refuted": refuted, "reason": reason}


def extract_and_validate(finding: dict, client, model: str) -> dict:
    """Full Pass A step for one finding: extract + adversarially validate.

    Returns the invariant dict with an additional `validation` field:
      {... extracted fields ..., "validation": {"refuted": bool, "reason": str}}
    """
    inv = extract_invariant(finding, client, model)
    verdict = validate_extraction(finding, inv, client, model)
    inv["validation"] = verdict
    return inv


# ============================================================
# Resumability + checkpointing
# ============================================================

def partial_path(run_dir: Path) -> Path:
    return run_dir / "partial.jsonl"


def load_completed_ids(run_dir: Path) -> set[str]:
    """Resume-from: read any partial.jsonl entries already on disk."""
    p = partial_path(run_dir)
    if not p.exists():
        return set()
    ids = set()
    with p.open() as f:
        for ln in f:
            try:
                r = json.loads(ln)
                if "finding_id" in r:
                    ids.add(r["finding_id"])
            except json.JSONDecodeError:
                pass
    return ids


def append_partial(run_dir: Path, finding_id: str, inv: dict):
    """Append one annotation to the partial log. Atomic per-line."""
    run_dir.mkdir(parents=True, exist_ok=True)
    with partial_path(run_dir).open("a") as f:
        f.write(json.dumps({"finding_id": finding_id, "structural_invariant": inv}) + "\n")
        f.flush()


# ============================================================
# Main flows
# ============================================================

def run_dry(idx: dict, limit: int) -> None:
    """Smoke test: extract from N findings, print result, no write."""
    client, model = _get_client()
    print(f"DRY RUN: extracting from {limit} findings using {model}\n")
    for i, finding in enumerate(idx["findings"][:limit]):
        print(f"[{i+1}/{limit}] {finding['severity']}: {finding['title'][:80]}")
        inv = extract_and_validate(finding, client, model)
        print(f"  → {json.dumps(inv, indent=2)[:400]}")
        print()


def run_sample(idx: dict, sample_n: int, validation_out: Path) -> None:
    """Annotate N random findings + dump a markdown file for human review.
    Does NOT modify the corpus pickle."""
    client, model = _get_client()
    random.seed(42)  # deterministic sampling
    sampled = random.sample(idx["findings"], sample_n)
    validation_out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, finding in enumerate(sampled):
        print(f"[{i+1}/{sample_n}] {finding['title'][:60]}")
        inv = extract_and_validate(finding, client, model)
        rows.append({"finding": finding, "invariant": inv})

    # Summary statistics across the sample.
    n_refuted = sum(1 for r in rows
                    if r["invariant"].get("validation", {}).get("refuted") is True)
    n_null = sum(1 for r in rows if r["invariant"].get("category") == "none")
    n_clean = sample_n - n_refuted - n_null

    with validation_out.open("w") as f:
        f.write(f"# Pass A annotation sample (N={sample_n}, seed=42)\n\n")
        f.write(f"Generated {date.today().isoformat()} by tools/annotate_corpus_invariants.py.\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- **Clean** (extracted + adversarial critic accepted): {n_clean} / {sample_n}\n")
        f.write(f"- **Refuted** by adversarial critic: {n_refuted} / {sample_n}\n")
        f.write(f"- **Null** (extraction self-reported `category: none`): {n_null} / {sample_n}\n\n")
        f.write(f"If refuted ratio > 30%: the extraction prompt needs work before running --full.\n\n")
        f.write("Review each row: does the extracted structural_invariant faithfully capture the bug? Does the critic's REFUTE decision look right?\n\n")
        f.write("---\n\n")
        for i, r in enumerate(rows):
            fnd = r["finding"]
            inv = r["invariant"]
            val = inv.get("validation", {})
            badge = "🔴 REFUTED" if val.get("refuted") else (
                "⚪ NULL" if inv.get("category") == "none" else "✅ CLEAN"
            )
            f.write(f"## {i+1}. {badge} — [{fnd['severity']}] {fnd['title']}\n\n")
            f.write(f"- Corpus: `{fnd.get('corpus','?')}` (source: {fnd.get('source','?')})\n")
            f.write(f"- Body: {fnd.get('body','')[:400]}{'...' if len(fnd.get('body',''))>400 else ''}\n\n")
            f.write(f"**Extracted invariant:**\n\n```json\n{json.dumps(inv, indent=2)}\n```\n\n")
            if val:
                f.write(f"**Adversarial critic verdict:** "
                        f"`refuted={val.get('refuted')}` — *{val.get('reason','')}*\n\n")
            f.write("**JH manual verdict:** ☐ faithful  ☐ partial  ☐ wrong  ☐ critic-was-right  ☐ critic-was-wrong\n\n")
            f.write("---\n\n")
    print(f"\nValidation markdown written to {validation_out}")
    print(f"  Clean:   {n_clean}/{sample_n}")
    print(f"  Refuted: {n_refuted}/{sample_n}")
    print(f"  Null:    {n_null}/{sample_n}")
    if n_refuted / max(sample_n, 1) > 0.30:
        print(f"  ⚠️  >30% refuted — extraction prompt may need iteration before --full")


def run_full(idx: dict) -> None:
    """Annotate all 1,240 findings. Resumable. Writes findings_index.pkl in place."""
    client, model = _get_client()
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    # back up the original BEFORE first write
    backup = INDEX_PATH.with_suffix(".pkl.bak")
    if not backup.exists():
        shutil.copy(INDEX_PATH, backup)
        print(f"backed up corpus to {backup}")

    completed = load_completed_ids(RUNS_DIR)
    todo = [f for f in idx["findings"] if f["finding_id"] not in completed]
    print(f"Resuming: {len(completed)} done, {len(todo)} to go (of {len(idx['findings'])} total)")

    t0 = time.time()
    for i, finding in enumerate(todo):
        try:
            inv = extract_and_validate(finding, client, model)
        except Exception as e:
            print(f"  [{i+1}/{len(todo)}] ERROR on {finding['finding_id']}: {e}")
            inv = {"category": "none", "reason": f"extraction error: {e}"}
        append_partial(RUNS_DIR, finding["finding_id"], inv)
        if (i + 1) % 25 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(todo) - i - 1) / rate
            print(f"  [{i+1}/{len(todo)}] {rate:.2f}/s, ETA {eta:.0f}s ({eta/60:.1f}m)")

    # merge partial.jsonl back into the pickle
    print("\nMerging annotations into findings_index.pkl...")
    inv_by_id = {}
    with partial_path(RUNS_DIR).open() as f:
        for ln in f:
            r = json.loads(ln)
            inv_by_id[r["finding_id"]] = r["structural_invariant"]
    for finding in idx["findings"]:
        if finding["finding_id"] in inv_by_id:
            finding["structural_invariant"] = inv_by_id[finding["finding_id"]]

    with INDEX_PATH.open("wb") as f:
        pickle.dump(idx, f)
    print(f"wrote {INDEX_PATH} ({len(inv_by_id)} annotations merged)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print, do not write")
    ap.add_argument("--limit", type=int, default=10, help="Findings to process in dry-run")
    ap.add_argument("--sample", type=int, help="Sample N + dump validation markdown")
    ap.add_argument("--validation-out", type=Path,
                    default=RUNS_DIR / "validation.md",
                    help="Where to write validation markdown")
    ap.add_argument("--full", action="store_true",
                    help="Annotate all 1,240 findings (resumable, writes corpus in place)")
    args = ap.parse_args()

    # Pre-flight: confirm the spec loaded successfully + has expected shape.
    if not EXTRACTION_PROMPT_TEMPLATE or len(EXTRACTION_PROMPT_TEMPLATE) < 1000:
        print("ERROR: EXTRACTION_PROMPT_TEMPLATE looks empty/short.")
        print(f"       Check {SPEC_PATH} — expected ~10k-char prompt text.")
        sys.exit(2)
    if len(INVARIANT_CATEGORIES) < 5:
        print(f"ERROR: only {len(INVARIANT_CATEGORIES)} categories loaded. Spec corrupt?")
        sys.exit(2)
    if len(FEW_SHOT_EXAMPLES) < 5:
        print(f"WARNING: only {len(FEW_SHOT_EXAMPLES)} few-shot examples loaded.")
    print(f"spec OK: {len(INVARIANT_CATEGORIES)} categories, "
          f"{len(FEW_SHOT_EXAMPLES)} few-shots, "
          f"{len(OPEN_QUESTIONS)} known caveats")

    with INDEX_PATH.open("rb") as f:
        idx = pickle.load(f)
    print(f"loaded {len(idx['findings'])} findings\n")

    if args.dry_run:
        run_dry(idx, args.limit)
    elif args.sample:
        run_sample(idx, args.sample, args.validation_out)
    elif args.full:
        run_full(idx)
    else:
        print("Choose one: --dry-run, --sample N, or --full")
        sys.exit(2)


if __name__ == "__main__":
    main()
