"""
hf_mirror — push reps.jsonl to a HuggingFace dataset repo so the data survives
independent of any one Codespace's storage. Safe to run on every Nth rep.

  python hf_mirror.py                          # uses HF_TOKEN env
  python hf_mirror.py --repo <user/dataset>    # override default repo

Default repo: qizwiz/plumbline-reps (private). Created if missing.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REP_LOG = os.path.join(HERE, "reps.jsonl")
DEFAULT_REPO = "qizwiz/plumbline-reps"


def main():
    repo = DEFAULT_REPO
    args = sys.argv[1:]
    if "--repo" in args:
        repo = args[args.index("--repo") + 1]

    if not os.path.isfile(REP_LOG):
        print(f"no reps to mirror at {REP_LOG}")
        return 1

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("HF_TOKEN not set — skipping mirror. "
              "Set as a Codespaces Secret in GH repo settings.")
        return 0

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("huggingface_hub not installed — run: pip install huggingface_hub")
        return 1

    api = HfApi(token=token)
    try:
        create_repo(repo, repo_type="dataset", private=True, exist_ok=True, token=token)
    except Exception as e:
        print(f"create_repo: {e}")

    api.upload_file(
        path_or_fileobj=REP_LOG,
        path_in_repo="reps.jsonl",
        repo_id=repo,
        repo_type="dataset",
    )
    n = sum(1 for _ in open(REP_LOG))
    print(f"mirrored {n} reps -> https://huggingface.co/datasets/{repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
