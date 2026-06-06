"""
nca_train — stub for the Neural Cellular Automaton bug-class scanner.

NOT BUILT YET. This file exists to (a) commit the architectural decision,
(b) document the API the rest of the stack will integrate against, (c)
let CI sanity-check the import path so the codespace breaks early if the
shape drifts.

ARCHITECTURE (see ARCHITECTURE.md §3):
  - Program lattice: SlithIR statements as nodes; control-flow + dataflow
    edges. Resolution TBD (statement-level vs basic-block-level).
  - Cell state: vector of (semantic_embedding, taint_class, ownership,
    cei_position, arithmetic_risk, reentrancy_class, ...). Dim ~64-128.
  - Local update rule: small neural net f(self, aggregate(neighbors)) ->
    new_self_state. Shared across all cells.
  - Iterations: T ~10-30 message-passing rounds until convergence.
  - Output: per-cell bug-class label (softmax over {clean, reentrancy,
    overflow, oracle, replay, ...}) at the final state.

TRAINING DATA:
  - tools/synth_bugs.py (also stub) emits (program, per-node-label) pairs
    by mutating clean contracts to inject known patterns from .ANSWERS.md.
  - At scale: tens of thousands of synthetic programs per bug class.
  - Loss: cross-entropy on per-cell labels at final NCA state.

REACHABLE SET (the contest-relevant measurement):
  For each bug class B:
    - Synthesize M instances containing B
    - Run NCA on each
    - Recall[B] = fraction where NCA's max-activated bug-class label per
      labeled-bug-node is B at convergence
    - Compression[B] = number of NCA iterations to convergence (CA-style
      complexity proxy; Rule-30-incompressible ↔ slow convergence ↔
      contest-relevant bug class; compressible ↔ slither-class)

The DIFFERENCE between (NCA reachable set) and (verifier-discharged
ground truth) is the bug-class boundary we're chasing.

USAGE (planned, not implemented):
    python tools/nca_train.py train --epochs 100 --hidden 64 --t-iters 20
    python tools/nca_train.py predict <contract.sol>   # per-node bug-class
    python tools/nca_train.py reachable <bug-class>    # measure recall + complexity

REALISTIC NEXT STEPS:
  1. Implement tools/synth_bugs.py FIRST — without data, NCA is theory.
  2. Build a minimal graph-attention model (PyTorch geometric) as the
     "NCA placeholder" — call it NCA architecturally, even though early
     version is a small GAT.
  3. Train on synth data from one bug class (signature replay, mirroring
     SignatureReplay.tla); measure recall on held-out synth + on
     boss-bridge real contract.
  4. Scale: add bug classes one at a time; the NCA's reachable set grows
     as the FailureMode corpus grows.
"""
from __future__ import annotations

import sys


def _stub(msg: str) -> None:
    print(f"NOT IMPLEMENTED: {msg}")
    print("See ARCHITECTURE.md §3 (NCA) for the design.")
    print("See tools/synth_bugs.py (also stub) for the data dependency.")


def train(**kwargs):
    _stub("NCA training. Need tools/synth_bugs.py first for labeled data.")


def predict(*paths):
    _stub(f"NCA prediction on {paths}. Train a model first.")


def reachable(bug_class: str):
    _stub(f"Reachable-set measurement for bug class {bug_class!r}. "
          "Needs a trained NCA + synth instances of this class.")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "train":   train()
    elif cmd == "predict": predict(*sys.argv[2:])
    elif cmd == "reachable": reachable(sys.argv[2] if len(sys.argv) > 2 else "<all>")
    else:
        print(f"unknown: {cmd}"); sys.exit(1)


if __name__ == "__main__":
    main()
