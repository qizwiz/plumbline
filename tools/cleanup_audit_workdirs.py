"""
tools/cleanup_audit_workdirs.py — reclaim disk by removing audit source-tree
working dirs whose JSON output is already safely saved.

Pattern that emerged 2026-06-21 across 3 disk-pressure events: proposer-bet-style
workflows download ~24 Solidity codebases to /private/tmp/plumbline-proposer-bet/
(~400-1000 MB total), run Sonnet/GPT audits, save findings to
runs/proposer-bet/sonnet_<pid>.json. Once the JSON is saved, the source tree is
dead weight and should be removed — but nothing did this automatically until now.

Safe by construction:
- Only deletes a source dir if its corresponding output JSON exists AND is
  non-empty AND parses as JSON with a "findings" list.
- Never touches the output JSONs themselves.
- Never touches dirs that don't have a saved JSON yet (in-flight audits).
- Idempotent — running it twice does nothing the second time.

Usage:
    python tools/cleanup_audit_workdirs.py                 # default paths
    python tools/cleanup_audit_workdirs.py --dry-run       # show what would be deleted
    python tools/cleanup_audit_workdirs.py --workdir-root /tmp/other-bet-dir \
                                            --output-dir runs/other-bet \
                                            --output-prefix gpt5_

Call this from inside workflow Compose/Score phases too — clean up after each
agent so the next one has room.
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def cleanup(
    workdir_root: Path,
    output_dir: Path,
    output_prefix: str = "sonnet_",
    dry_run: bool = False,
) -> tuple[int, int]:
    """Return (n_cleaned, bytes_reclaimed).

    For each subdir of workdir_root, check whether output_dir/<output_prefix><dirname>.json
    exists and is a valid findings file. If yes, remove the source dir.
    """
    if not workdir_root.is_dir():
        return 0, 0
    if not output_dir.is_dir():
        return 0, 0

    n_cleaned = 0
    bytes_reclaimed = 0
    for source_dir in sorted(workdir_root.iterdir()):
        if not source_dir.is_dir():
            continue
        json_path = output_dir / f"{output_prefix}{source_dir.name}.json"
        if not json_path.is_file() or json_path.stat().st_size < 50:
            continue
        try:
            content = json.loads(json_path.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(content.get("findings"), list):
            continue
        # Size before delete (du -sk reports the actual on-disk usage)
        try:
            kb = int(subprocess.check_output(
                ["du", "-sk", str(source_dir)], text=True
            ).split()[0])
        except (subprocess.SubprocessError, ValueError):
            kb = 0
        bytes_reclaimed += kb * 1024
        if dry_run:
            print(f"WOULD DELETE: {source_dir} ({kb / 1024:.1f} MB) — output at {json_path}")
        else:
            shutil.rmtree(source_dir, ignore_errors=True)
            print(f"DELETED: {source_dir} ({kb / 1024:.1f} MB)")
        n_cleaned += 1
    return n_cleaned, bytes_reclaimed


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workdir-root", default="/private/tmp/plumbline-proposer-bet",
                   help="Root of audit working dirs (default: /private/tmp/plumbline-proposer-bet)")
    p.add_argument("--output-dir",
                   default="/Users/jonathanhill/src/plumbline/runs/proposer-bet",
                   help="Where saved audit JSONs live (default: runs/proposer-bet)")
    p.add_argument("--output-prefix", default="sonnet_",
                   help="Filename prefix on saved JSONs (default: sonnet_)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be deleted, don't actually delete")
    args = p.parse_args()

    n, reclaimed = cleanup(
        Path(args.workdir_root),
        Path(args.output_dir),
        output_prefix=args.output_prefix,
        dry_run=args.dry_run,
    )
    mb = reclaimed / (1024 * 1024)
    verb = "would reclaim" if args.dry_run else "reclaimed"
    print(f"\n{n} source dirs cleaned, {verb} {mb:.1f} MB")


if __name__ == "__main__":
    main()
