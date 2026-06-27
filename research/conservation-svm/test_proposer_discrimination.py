#!/usr/bin/env python3
"""
test_proposer_discrimination.py — discrimination control for conserve.py's proposer.

The conservation engine pins precision at 1.0 by SOUNDNESS, but that guarantee carries a
hidden premise: the structural proposer must only fire where conservation is the RIGHT law.
If it fired on keyword PRESENCE alone, it would emit a meaningless halmos property on a
non-conservation contract — vacuous pass (false confidence) or spurious fail (a false
positive that breaks precision 1.0).

Every existing fixture is conservation-POSITIVE (CleanVault, dreUSDfixed, MiniToken*), so the
DECLINE half of the discrimination was never regression-guarded. This test locks both halves:

  PROPOSE  on a real vault           (inverse-op pair present)             -> pair is not None
  DECLINE  on an adversarial admin   (keywords present, never paired in    -> pair is None
           contract                   a single function)

Note the test is non-vacuous BY CONSTRUCTION: a broken analyze() that always returned None
would fail the PROPOSE case, and one that always paired would fail the DECLINE case. Only a
detector that genuinely discriminates passes both.

$0: pure structural analysis. No halmos, no network, no LLM. Runs in milliseconds.

Run: python3 test_proposer_discrimination.py   (exit 0 = discrimination holds, 1 = regression)
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from conserve import analyze  # noqa: E402

# (fixture, should_propose, why)
CASES = [
    ("fixtures/CleanVault.sol", True,
     "real vault: mint(transferFrom-in + _mint) / redeem(_burn + transfer-out) -> the inverse pair"),
    ("fixtures/AdminVault.sol", False,
     "admin contract: _mint, .transfer, transferFrom all present but never paired in one function"),
    ("fixtures/AdminVaultBurn.sol", False,
     "admin contract WITH _burn: regression guard for the interface-decl parser false-positive"),
]


def main():
    failures = []
    for rel, should_propose, why in CASES:
        a = analyze((HERE / rel).read_text())
        proposed = a["pair"] is not None
        ok = (proposed == should_propose)
        verb = "PROPOSE" if proposed else "DECLINE"
        want = "PROPOSE" if should_propose else "DECLINE"
        print(f"[{'ok ' if ok else 'FAIL'}] {rel:28s} -> {verb:7s} (want {want})  | {why}")
        if not ok:
            failures.append((rel, want, verb))

    if failures:
        print(f"\n{len(failures)} discrimination failure(s):")
        for rel, want, got in failures:
            print(f"  {rel}: wanted {want}, got {got}")
        sys.exit(1)

    print("\nDISCRIMINATION HOLDS: proposer fires on the vault, declines on the admin contract.")
    print("The precision-1.0-by-soundness claim's proposer premise is now regression-guarded.")


if __name__ == "__main__":
    main()
