"""
c4_ingest — batch-ingest Code4rena findings into plumbline's .ANSWERS.md format.

Architecture per docs/research/C4_INGEST_OPPORTUNITY.md (deep-research):
  - 376 *-findings repos in github.com/code-423n4 (verified 2026-06-07)
  - ~115K bug-labeled issues; ~38K unique H/M after dedup
  - report.md follows the structure documented in
    docs/research/AUDIT_REPORT_TEMPLATE_RESEARCH.md

LICENSE NOTE (verified 2026-06-07):
  All 7 sampled C4 findings repos return 404 on /license endpoint
  (no LICENSE file). Default GitHub TOS applies: anyone can view +
  fork; redistribution requires explicit permission.

  THIS TOOL IS FOR PRIVATE RAG INDEX USE ONLY. Output should not be
  published or redistributed without further legal review. Solodit
  (cyfrin.io) operates a similar aggregation publicly; their position
  on this would be a useful reference but is outside this tool's scope.

Usage:
  # List candidate contests, ranked by recency
  python tools/c4_ingest.py list --limit 30

  # Ingest top N most recent contests into corpus/c4/<slug>/.ANSWERS.md
  python tools/c4_ingest.py pull --limit 10

  # Pull one specific contest
  python tools/c4_ingest.py pull --slug 2024-04-renzo

  # Show stats
  python tools/c4_ingest.py stats
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CORPUS_ROOT = HERE / "corpus" / "c4"


# ============================================================
# GitHub API access via `gh` CLI
# ============================================================

def gh_api(path: str, paginate: bool = False) -> dict | list:
    cmd = ["gh", "api"]
    if paginate: cmd.append("--paginate")
    cmd.append(path)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(f"gh api failed: {p.stderr[:400]}")
    if paginate:
        # paginated output is concatenated JSON arrays/objects with newlines
        out = []
        for line in p.stdout.split("\n"):
            if not line.strip(): continue
            try:
                out.extend(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
    return json.loads(p.stdout)


def list_findings_repos(limit: int | None = None) -> list[dict]:
    """Return list of {name, full_name, pushed_at, has_findings_repo}.
    Searches for code-423n4/*-findings repos sorted by recency."""
    repos = []
    page = 1
    while True:
        result = gh_api(
            f"/search/repositories?q=org:code-423n4+findings+in:name"
            f"&sort=updated&order=desc&per_page=100&page={page}")
        items = result.get("items", [])
        if not items: break
        for it in items:
            name = it["name"]
            if name.endswith("-findings"):
                repos.append({
                    "name": name,
                    "slug": name[:-len("-findings")],
                    "pushed_at": it.get("pushed_at"),
                    "open_issues_count": it.get("open_issues_count", 0),
                })
        if limit and len(repos) >= limit: break
        if len(items) < 100: break
        page += 1
        if page > 5: break  # safety
    if limit: repos = repos[:limit]
    return repos


# ============================================================
# Report.md parsing
# ============================================================

# Per-finding heading: `## [[H-01] title](url)` or with brackets on severity tag only
# Two variants observed across years:
#   `## [[H-01] Title here](https://github.com/.../issues/N)`   (2024+, single link)
#   `## [[H-01 Title here](url)](url)`                           (older, double link)
FINDING_HEAD = re.compile(
    r"^##\s+\[\[([HML])-(\d+)\]?\s*(.+?)\]\((https://[^\)]+)\)(?:\]\((https://[^\)]+)\))?\s*$",
    re.M)

# Section delimiters within a finding body
SECTION_HEADS = ["Description", "Impact", "Proof of Concept", "POC",
                 "Recommended Mitigation Steps", "Recommendation",
                 "Tools Used", "Severity Rationalization", "References"]


def parse_report(text: str, slug: str) -> list[dict]:
    """Extract per-finding dicts from a Code4rena report.md."""
    findings = []
    # Find all H/M finding heading positions
    head_matches = list(FINDING_HEAD.finditer(text))
    for i, m in enumerate(head_matches):
        sev_letter = m.group(1)
        num = int(m.group(2))
        title = m.group(3).rstrip("]").strip()
        issue_url = m.group(4)
        # body extends to next finding heading OR a # / ## section
        body_start = m.end()
        body_end = (head_matches[i + 1].start()
                    if i + 1 < len(head_matches) else len(text))
        # Also stop at the next top-level header
        next_top = re.search(r"^#\s+", text[body_start:body_end], re.M)
        if next_top:
            body_end = body_start + next_top.start()
        body = text[body_start:body_end].strip()
        sections = _split_sections(body)
        sev_map = {"H": "High", "M": "Medium", "L": "Low"}
        findings.append({
            "id": f"{sev_letter}-{num:02d}",
            "severity": sev_map[sev_letter],
            "title": title,
            "source_issue_url": issue_url,
            "contest_slug": slug,
            "description": sections.get("Description", ""),
            "impact": sections.get("Impact", ""),
            "poc": (sections.get("Proof of Concept", "") or
                    sections.get("POC", "")),
            "mitigation": (sections.get("Recommended Mitigation Steps", "") or
                           sections.get("Recommendation", "")),
            "tools_used": sections.get("Tools Used", ""),
            "severity_rationale": sections.get("Severity Rationalization", ""),
            "raw_body_chars": len(body),
        })
    return findings


def _split_sections(body: str) -> dict[str, str]:
    """Split a finding body into named sections by ### headers."""
    out = {}
    pat = re.compile(r"^###\s+(.+?)\s*$", re.M)
    matches = list(pat.finditer(body))
    if not matches:
        return out
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out[name] = body[start:end].strip()
    return out


def fetch_report(slug: str) -> str | None:
    """Fetch raw report.md from github."""
    urls = [
        f"https://raw.githubusercontent.com/code-423n4/{slug}-findings/main/report.md",
        f"https://raw.githubusercontent.com/code-423n4/{slug}-findings/main/README.md",
        f"https://raw.githubusercontent.com/code-423n4/{slug}-findings/master/report.md",
    ]
    for url in urls:
        try:
            p = subprocess.run(["curl", "-fsSL", url], capture_output=True,
                               text=True, timeout=60)
            if p.returncode == 0 and p.stdout.strip():
                return p.stdout
        except subprocess.TimeoutExpired:
            continue
    return None


# ============================================================
# Output: plumbline .ANSWERS.md format
# ============================================================

def write_answers_md(slug: str, findings: list[dict]):
    out_dir = CORPUS_ROOT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ".ANSWERS.md"
    lines = [f"# {slug} — confirmed findings", "",
             f"_Auto-ingested from code-423n4/{slug}-findings by "
             "`tools/c4_ingest.py`. Per `docs/research/C4_INGEST_OPPORTUNITY.md`, "
             "this output is for PRIVATE RAG index only — original C4 repo "
             "has no LICENSE file, default 'all rights reserved' applies._", ""]
    for f in findings:
        lines.append(f"## {f['id']} {f['title']}")
        if f.get("description"):
            lines.append(f["description"])
        if f.get("impact"):
            lines.append(f"\n**Mechanism:** {f['impact']}")
        if f.get("mitigation"):
            lines.append(f"\n**Mitigation:** {f['mitigation']}")
        lines.append("")
    path.write_text("\n".join(lines))
    print(f"  → {path} ({len(findings)} findings)")


# ============================================================
# CLI subcommands
# ============================================================

def cmd_list(args):
    repos = list_findings_repos(limit=args.limit)
    print(f"# top {len(repos)} most-recent Code4rena findings repos:")
    print()
    for r in repos:
        print(f"  {r['name']:<60} pushed={r['pushed_at'][:10]}  "
              f"issues={r['open_issues_count']}")


def cmd_pull(args):
    if args.slug:
        slugs = [args.slug]
    else:
        repos = list_findings_repos(limit=args.limit)
        slugs = [r["slug"] for r in repos]
    print(f"# pulling {len(slugs)} contest(s)\n")
    totals = {"contests": 0, "findings": 0, "skipped": 0}
    for slug in slugs:
        report = fetch_report(slug)
        if not report:
            print(f"  SKIP {slug} (no report.md found)")
            totals["skipped"] += 1
            continue
        findings = parse_report(report, slug)
        if not findings:
            print(f"  SKIP {slug} (0 findings parsed)")
            totals["skipped"] += 1
            continue
        write_answers_md(slug, findings)
        totals["contests"] += 1
        totals["findings"] += len(findings)
    print(f"\n# done: {totals['contests']} contests, "
          f"{totals['findings']} findings ingested, {totals['skipped']} skipped")


def cmd_stats(args):
    if not CORPUS_ROOT.exists():
        print("(no corpus/c4 yet — run `pull` first)"); return
    contests = sorted(CORPUS_ROOT.iterdir())
    total_findings = 0
    by_severity = {"High": 0, "Medium": 0, "Low": 0}
    for c in contests:
        a = c / ".ANSWERS.md"
        if not a.exists(): continue
        n = sum(1 for ln in a.read_text().split("\n")
                if ln.startswith("## H-") or ln.startswith("## M-") or
                   ln.startswith("## L-"))
        total_findings += n
        for ln in a.read_text().split("\n"):
            if ln.startswith("## H-"): by_severity["High"] += 1
            elif ln.startswith("## M-"): by_severity["Medium"] += 1
            elif ln.startswith("## L-"): by_severity["Low"] += 1
    print(f"corpus/c4: {len(contests)} contests, {total_findings} findings")
    print(f"  severity: H={by_severity['High']} M={by_severity['Medium']} "
          f"L={by_severity['Low']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_list = sub.add_parser("list")
    p_list.add_argument("--limit", type=int, default=30)
    p_list.set_defaults(func=cmd_list)
    p_pull = sub.add_parser("pull")
    p_pull.add_argument("--limit", type=int, default=10)
    p_pull.add_argument("--slug", help="single contest slug e.g. 2024-04-renzo")
    p_pull.set_defaults(func=cmd_pull)
    p_stats = sub.add_parser("stats")
    p_stats.set_defaults(func=cmd_stats)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
