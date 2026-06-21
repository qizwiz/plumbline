"""
prompt_improve — the improve decorator for pact-style self-improving prompts.

pact's rule (intent.py, find.py): a prompt is never an inline string — it's a FILE
(prompts/<name>.md) with {{placeholders}}, and after each run it SELF-IMPROVES: the run
is scored, and if the prompt underperformed, an LLM rewrites the file. Over use, prompts
converge toward optimal.

This module is that decorator, with one upgrade over pact's default: the score is
GROUNDED, not LLM-self-assessed. The caller scores a prompt on what its output did
against the SOUND oracle — invariants that survived the skeptic, tests that built, Halmos
verdicts — so the prompt converges toward outputs the execution/proof layer accepts, not
toward what an LLM thinks looks good.

Hardening (2026-06-20):
    The legacy acceptance gate (non-empty + len>80 + presence of `{{`) admitted
    catastrophic shrinkage: a 2367-byte 8-lens prompt could collapse to 81 chars with
    one placeholder and still be accepted. The gate now enforces:
        - every {{placeholder}} from the original survives,
        - rewrite length >= 0.5 * original length (proportional floor),
        - numbered-heading count >= 0.7 * original count,
    and the original is snapshotted under prompts/.archive/ before first rewrite, and
    every rewrite is unified-diffed into /tmp/prompt_improve_<name>.log for inspection.

Usage:
    tmpl = load_prompt("sol_invariant_propose")
    out  = ask(render(tmpl, src=contract))            # run the file-backed prompt
    ...                                                # compute a grounded score in [0,1]
    improve_if_weak("sol_invariant_propose", score, transcript, ask)  # rewrite if weak
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_DIR = os.path.join(HERE, "prompts")
ARCHIVE_DIR = os.path.join(PROMPT_DIR, ".archive")
THRESHOLD = 0.7  # below this grounded score, the prompt is rewritten

# Acceptance-gate tunables (proportional floors, not absolute).
MIN_LENGTH_RATIO = 0.5     # rewrite must be at least 50% of original length
MIN_HEADING_RATIO = 0.7    # rewrite must retain at least 70% of numbered headings
HEADING_RE = re.compile(r"^(?:###\s*)?\d+\.", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, f"{name}.md"), encoding="utf-8") as f:
        return f.read()


def save_prompt(name: str, text: str) -> None:
    """Write text to prompts/<name>.md, snapshotting the *current* file under
    prompts/.archive/<name>_<sha256[:8]>.md first (idempotent — skipped if the
    archive for that exact content already exists)."""
    path = os.path.join(PROMPT_DIR, f"{name}.md")
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                current_bytes = f.read()
            digest = hashlib.sha256(current_bytes).hexdigest()[:8]
            os.makedirs(ARCHIVE_DIR, exist_ok=True)
            archive_path = os.path.join(ARCHIVE_DIR, f"{name}_{digest}.md")
            if not os.path.exists(archive_path):
                with open(archive_path, "wb") as f:
                    f.write(current_bytes)
        except Exception as exc:  # noqa: BLE001 — archival is best-effort
            print(f"  [improve] archive skipped for {name} ({type(exc).__name__}: {str(exc)[:60]})")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def render(template: str, **vars) -> str:
    for k, v in vars.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def _placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(text))


def _heading_count(text: str) -> int:
    return len(HEADING_RE.findall(text))


def _log_diff(name: str, original: str, rewrite: str, accepted: bool, reason: str) -> None:
    """Append a unified diff between original and rewrite to
    /tmp/prompt_improve_<name>.log so drift across multiple cycles is inspectable."""
    try:
        log_path = f"/tmp/prompt_improve_{name}.log"
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            rewrite.splitlines(keepends=True),
            fromfile=f"{name}.md (before)",
            tofile=f"{name}.md (proposed rewrite)",
            n=3,
        )
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"\n===== {datetime.utcnow().isoformat()}Z  accepted={accepted}  reason={reason} =====\n"
            )
            f.writelines(diff)
            f.write("\n")
    except Exception as exc:  # noqa: BLE001 — logging is best-effort
        print(f"  [improve] diff log skipped for {name} ({type(exc).__name__}: {str(exc)[:60]})")


def _gate_rewrite(name: str, original: str, rewrite: str) -> tuple[bool, str]:
    """Apply structural acceptance gates. Returns (accepted, reason).

    Gates (each failure rejects with a clear reason):
      G1  rewrite is non-empty
      G2  rewrite length >= max(80, MIN_LENGTH_RATIO * len(original))
      G3  every {{placeholder}} present in the original survives in the rewrite
      G4  numbered-heading count >= MIN_HEADING_RATIO * original heading count
          (only applied if the original has any numbered headings)
    """
    if not rewrite:
        return False, "empty rewrite"

    orig_len = len(original)
    min_len = max(80, int(MIN_LENGTH_RATIO * orig_len))
    if len(rewrite) < min_len:
        return False, (
            f"length floor: {len(rewrite)} < {min_len} "
            f"({MIN_LENGTH_RATIO:.0%} of original {orig_len})"
        )

    orig_ph = _placeholders(original)
    new_ph = _placeholders(rewrite)
    missing = orig_ph - new_ph
    if missing:
        return False, f"dropped placeholders: {sorted(missing)}"

    orig_headings = _heading_count(original)
    if orig_headings > 0:
        new_headings = _heading_count(rewrite)
        min_headings = max(1, int(MIN_HEADING_RATIO * orig_headings))
        if new_headings < min_headings:
            return False, (
                f"heading floor: {new_headings} numbered headings < {min_headings} "
                f"({MIN_HEADING_RATIO:.0%} of original {orig_headings})"
            )

    return True, "ok"


def improve_if_weak(name: str, score: float, transcript: str, ask) -> bool:
    """If the GROUNDED score is below threshold, ask an LLM to rewrite the prompt file
    given a transcript of what went wrong against the oracle. Returns True if rewritten.

    Hardened acceptance gates (see ``_gate_rewrite``) protect against multi-cycle drift —
    a rewrite that drops {{placeholders}}, shrinks below half the original length, or
    flattens the numbered-heading structure is REJECTED and the file is left untouched.
    Every proposal (accepted or not) is unified-diffed to /tmp/prompt_improve_<name>.log.
    Degrades gracefully (e.g. no API credits) — never raises."""
    if score >= THRESHOLD:
        return False
    try:
        current = load_prompt(name)
        meta = (
            f"This prompt UNDERPERFORMED against a sound oracle (grounded score {score:.2f} "
            f"< {THRESHOLD}). Rewrite it to fix the demonstrated weakness. Keep its required "
            "output format and {{placeholders}} EXACTLY. Return ONLY the improved prompt text.\n\n"
            f"=== WHAT WENT WRONG (oracle transcript) ===\n{transcript}\n\n"
            f"=== CURRENT PROMPT ({name}.md) ===\n{current}"
        )
        improved = ask(meta).strip()
        accepted, reason = _gate_rewrite(name, current, improved)
        _log_diff(name, current, improved, accepted, reason)
        if not accepted:
            print(f"  [improve] REJECTED rewrite of {name}.md — {reason}")
            return False
        save_prompt(name, improved)
        print(f"  [improve] rewrote {name}.md (grounded score {score:.2f}; gate ok)")
        return True
    except Exception as exc:  # noqa: BLE001 — improvement is best-effort
        print(f"  [improve] skipped {name} ({type(exc).__name__}: {str(exc)[:60]})")
    return False
