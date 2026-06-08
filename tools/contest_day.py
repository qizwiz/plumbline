"""
contest_day — one-command orchestrator for Sherlock/C4 contest scope.

Runs cascade-grounded sol_intent (high precision, 12 verdicts) and
baseline sol_intent (broad recall, ~200 leads) in PARALLEL, unions
outputs with confidence tags, renders the Sherlock/C4 template.

Per the 2026-06-08 measurement:
  - cascade-grounded: 50%+ precision, low recall on diverse contests
  - baseline: 13.7% precision, 75.6% recall
  - UNION: confidence-tagged for fast triage

This is the contest-day-tomorrow operational pipeline.

Usage:
  python tools/contest_day.py <scope-dir> \\
      --slug 2026-06-08-sponsor --sponsor "Sponsor" \\
      --target sherlock \\
      --out-dir reports/

Outputs:
  reports/<slug>-cascade-verdicts.txt    (cascade-grounded, ~12 verdicts)
  reports/<slug>-baseline-leads.txt      (raw sol_intent, ~200 leads)
  reports/<slug>-union-leads.json        (combined, confidence-tagged)
  reports/<slug>-report.md               (rendered Sherlock/C4 markdown)

If --target sherlock, also prints pandoc invocation for PDF.
"""
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

# Known fallback path for slither when not on PATH (e.g. user's local Python install)
_SLITHER_FALLBACK = "/Users/jonathanhill/Library/Python/3.14/bin/slither"


def _find_slither() -> str | None:
    """Return slither binary path: PATH first, then known fallback."""
    s = shutil.which("slither")
    if s:
        return s
    if Path(_SLITHER_FALLBACK).exists():
        return _SLITHER_FALLBACK
    return None


def run_slither(scope_dir: Path, out: Path) -> tuple[int, int]:
    """
    Run slither --json on scope_dir. Returns (elapsed_s, n_findings).
    Writes JSON to `out`. Writes empty dict if slither unavailable or fails.
    """
    slither_bin = _find_slither()
    if slither_bin is None:
        print("[slither] not found in PATH or fallback — SKIPPED", file=sys.stderr)
        out.write_text("{}")
        return 0, 0

    t0 = time.time()
    print(f"[slither] starting on {scope_dir}", file=sys.stderr)
    p = subprocess.run(
        [slither_bin, str(scope_dir), "--json", str(out),
         "--exclude-informational", "--exclude-optimization"],
        env=env_with_key(), cwd=str(HERE),
        capture_output=True, text=True, timeout=300,
    )
    elapsed = int(time.time() - t0)
    # Slither exits 1 even on success when detectors fire; only >1 is a hard fail
    if p.returncode > 1:
        print(f"[slither] FAILED rc={p.returncode}\n{p.stderr[:600]}", file=sys.stderr)
        out.write_text("{}")
        return elapsed, 0

    n = 0
    if out.exists():
        try:
            data = json.loads(out.read_text())
            n = len(data.get("results", {}).get("detectors", []))
        except (json.JSONDecodeError, KeyError):
            pass
    print(f"[slither] done in {elapsed}s → {n} detectors fired → {out}",
          file=sys.stderr)
    return elapsed, n


def parse_slither_output(json_path: Path) -> list[dict]:
    """Parse slither --json output into lead dicts with confidence tags."""
    if not json_path.exists():
        return []
    try:
        data = json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    detectors = data.get("results", {}).get("detectors", [])
    leads: list[dict] = []
    for det in detectors:
        impact = det.get("impact", "").strip()
        if impact == "High":
            conf_tag = "HIGH-static"
        elif impact == "Medium":
            conf_tag = "MEDIUM-static"
        else:
            conf_tag = "LOW-static"

        # Best location: first function element → "Contract.fn", else filename stem
        location = "?"
        for el in (det.get("elements") or []):
            el_type = el.get("type", "")
            name = el.get("name", "")
            src = el.get("source_mapping", {})
            filename = src.get("filename_relative", "")
            parent = (el.get("type_specific_fields") or {}).get("parent", {})
            contract_name = parent.get("name", "") or Path(filename).stem
            if name and contract_name:
                sep = "." if el_type == "function" else "/"
                location = f"{contract_name}{sep}{name}"
                break
            elif filename:
                location = Path(filename).stem
                break

        leads.append({
            "confidence": conf_tag,
            "source": "slither",
            "location": location,
            "claim": det.get("description", "")[:200].replace("\n", " ").strip(),
            "shape": det.get("check", ""),
            "why": f"slither/{det.get('check', '')} impact={impact} "
                   f"confidence={det.get('confidence', '?')}",
        })
    return leads


# Lazy import so the filter is optional and doesn't break if called
# with --no-filter or from old scripts that don't pass scope_dir.
def _admin_filter(leads, scope_dir, no_filter=False):
    try:
        from admin_trust_filter import filter_leads
        return filter_leads(leads, scope_dir, no_filter=no_filter)
    except ImportError:
        return leads, []


def _adversarial_verify(leads, scope_dir, scripts_dir=None, no_filter=False):
    try:
        from adversarial_verify import verify_leads
        return verify_leads(leads, scope_dir, scripts_dir=scripts_dir, no_filter=no_filter)
    except ImportError:
        return leads, []


def env_with_key() -> dict:
    """Source .env into a copy of os.environ."""
    env = os.environ.copy()
    env_path = HERE / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def run_cascade(scope_dir: Path, out: Path) -> int:
    """Run sol_intent_cascade.py. Returns elapsed seconds."""
    t0 = time.time()
    print(f"[cascade-grounded] starting on {scope_dir}", file=sys.stderr)
    p = subprocess.run(
        [sys.executable, str(HERE / "tools" / "sol_intent_cascade.py"),
         str(scope_dir), "--out", str(out)],
        env=env_with_key(), cwd=str(HERE),
        capture_output=True, text=True, timeout=600)
    elapsed = int(time.time() - t0)
    if p.returncode != 0:
        print(f"[cascade-grounded] FAILED rc={p.returncode}\n{p.stderr[:600]}",
              file=sys.stderr)
    else:
        print(f"[cascade-grounded] done in {elapsed}s → {out}", file=sys.stderr)
    return elapsed


def run_baseline(scope_dir: Path, out: Path) -> int:
    """Run sol_intent.py --hybrid-rag --recall. Returns elapsed seconds."""
    t0 = time.time()
    print(f"[baseline] starting on {scope_dir}", file=sys.stderr)
    with open(out, "w") as f:
        p = subprocess.run(
            [sys.executable, str(HERE / "sol_intent.py"),
             str(scope_dir), "--hybrid-rag", "--recall"],
            env=env_with_key(), cwd=str(HERE),
            stdout=f, stderr=subprocess.PIPE, text=True, timeout=900)
    elapsed = int(time.time() - t0)
    if p.returncode != 0:
        print(f"[baseline] FAILED rc={p.returncode}\n{p.stderr[:600]}",
              file=sys.stderr)
    else:
        print(f"[baseline] done in {elapsed}s → {out}", file=sys.stderr)
    return elapsed


def parse_cascade_verdicts(text: str) -> list[dict]:
    """Pull CONFIRM lines from cascade output as high-confidence leads."""
    out = []
    # Match "- [CONFIRM] Contract.fn -- bug claim" with "shape:" + "why:" lines
    pat = re.compile(
        r"\[CONFIRM\]\s+([\w.]+)\s*--\s*(.+?)$\s*shape:\s*(.+?)$\s*why:\s*(.+?)$",
        re.M | re.S)
    for m in pat.finditer(text):
        out.append({
            "confidence": "HIGH",
            "source": "cascade-grounded",
            "location": m.group(1).strip(),
            "claim": m.group(2).strip()[:200],
            "shape": m.group(3).strip()[:60],
            "why": m.group(4).strip()[:300],
        })
    return out


def parse_baseline_leads(text: str) -> list[dict]:
    """Pull bulleted leads from baseline sol_intent output."""
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("- "): continue
        if len(line) < 20: continue
        # Try to extract Location :: claim pattern
        body = line[2:].strip()
        # The standard sol_intent format: `[LENS] Contract::function -- issue -- why`
        m = re.match(r"\[(\w+(?:\s*/\s*\w+)*)\]\s*(.+?)\s*--\s*(.+?)\s*--\s*(.+)$", body)
        if m:
            out.append({
                "confidence": "NORMAL",
                "source": "baseline",
                "lens": m.group(1).strip(),
                "location": m.group(2).strip()[:80],
                "claim": m.group(3).strip()[:200],
                "why": m.group(4).strip()[:300],
            })
        else:
            out.append({
                "confidence": "NORMAL",
                "source": "baseline",
                "raw": body[:400],
            })
    return out


def union_dedupe(cascade_verdicts: list[dict],
                 baseline_leads: list[dict],
                 slither_leads: list[dict] | None = None) -> list[dict]:
    """
    Cascade HIGH verdicts ranked first, then slither HIGH-static/MEDIUM-static,
    then baseline NORMAL leads (deduped against cascade locs), then slither
    LOW-static last.  Slither findings keyed by (location, shape) to avoid
    duplicates from re-runs.
    """
    out = list(cascade_verdicts)
    cascade_locs = {v["location"].lower() for v in cascade_verdicts}

    seen_slither: set[tuple[str, str]] = set()

    # Slither HIGH-static + MEDIUM-static go before baseline
    for lead in (slither_leads or []):
        if lead.get("confidence") in ("HIGH-static", "MEDIUM-static"):
            key = (lead.get("location", "").lower(), lead.get("shape", "").lower())
            if key not in seen_slither:
                seen_slither.add(key)
                out.append(lead)

    # Baseline leads, deduped against cascade locs
    for lead in baseline_leads:
        loc = lead.get("location", "").lower()
        if loc and any(c in loc or loc in c for c in cascade_locs):
            continue
        out.append(lead)

    # Slither LOW-static appended last
    for lead in (slither_leads or []):
        if lead.get("confidence") == "LOW-static":
            key = (lead.get("location", "").lower(), lead.get("shape", "").lower())
            if key not in seen_slither:
                seen_slither.add(key)
                out.append(lead)

    return out


def render_report(slug: str, sponsor: str, target: str,
                  union: list[dict], out_md: Path):
    """Render the Sherlock/C4 template. For v1, we synthesize a reps.jsonl
    on the fly from union leads, then call render_report.py."""
    reps_jsonl = out_md.parent / f".{slug}-reps.jsonl"
    high_idx = m_idx = 1
    with open(reps_jsonl, "w") as f:
        for lead in union:
            severity = "High" if lead["confidence"] == "HIGH" else "Medium"
            rep = {
                "rep_id": f"contest-{slug}-{high_idx if severity=='High' else m_idx}",
                "ts_ns": int(time.time() * 1e9),
                "leads": [lead.get("claim") or lead.get("raw", "")],
                "contract": {"path": lead.get("location", "?")},
                "proposer": {"author": "plumbline"},
                "plumbline_provenance": {
                    "matched_spec": lead.get("shape", ""),
                    "weak_confirm_strength": "STRONG" if severity == "High" else "WEAK",
                    "tlc_trace_head": lead.get("why", ""),
                    "mitigation": "(see why field)",
                },
            }
            f.write(json.dumps(rep) + "\n")
            if severity == "High": high_idx += 1
            else: m_idx += 1

    cmd = [sys.executable, str(HERE / "tools" / "render_report.py"),
           "--reps", str(reps_jsonl), "--target", target,
           "--slug", slug, "--sponsor", sponsor, "--out", str(out_md)]
    p = subprocess.run(cmd, env=env_with_key(), cwd=str(HERE),
                       capture_output=True, text=True, timeout=120)
    print(p.stderr, end="", file=sys.stderr)
    if p.returncode != 0:
        print(f"[render] FAILED rc={p.returncode}", file=sys.stderr)
    return reps_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scope_dir")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--sponsor", required=True)
    ap.add_argument("--target", default="sherlock",
                    choices=["sherlock", "code4rena", "immunefi"])
    ap.add_argument("--out-dir", default="reports")
    ap.add_argument("--skip-baseline", action="store_true",
                    help="Cascade-only mode (faster, lower recall)")
    ap.add_argument("--skip-slither", action="store_true",
                    help="Skip slither static analysis step")
    ap.add_argument("--scripts-dir", default=None,
                    help="Deployment scripts directory override (default: auto-detect script/deploy/)")
    ap.add_argument("--no-filter", action="store_true",
                    help="Skip admin-trust filter and adversarial verify; output raw union")
    args = ap.parse_args()

    scope = Path(args.scope_dir).resolve()
    out_dir = (HERE / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cascade_out = out_dir / f"{args.slug}-cascade-verdicts.txt"
    baseline_out = out_dir / f"{args.slug}-baseline-leads.txt"
    slither_out = out_dir / f"{args.slug}-slither.json"
    union_out = out_dir / f"{args.slug}-union-leads.json"
    report_out = out_dir / f"{args.slug}-report.md"

    # Run both in parallel via background subprocesses
    t_start = time.time()
    print(f"\n=== plumbline contest_day pipeline ===", file=sys.stderr)
    print(f"  scope:     {scope}", file=sys.stderr)
    print(f"  slug:      {args.slug}", file=sys.stderr)
    print(f"  target:    {args.target}", file=sys.stderr)
    print(f"  out:       {out_dir}\n", file=sys.stderr)

    # cascade first (fast — single LLM call after structural filter)
    t_cascade = run_cascade(scope, cascade_out)
    if not args.skip_baseline:
        t_baseline = run_baseline(scope, baseline_out)
    else:
        t_baseline = 0
        baseline_out.write_text("(skipped)\n")

    # Slither — deterministic static analysis, free to run
    if not args.skip_slither:
        t_slither, n_slither = run_slither(scope, slither_out)
        slither_leads = parse_slither_output(slither_out)
    else:
        t_slither, n_slither = 0, 0
        slither_leads = []
        slither_out.write_text("{}")

    # Parse + union
    cascade_text = cascade_out.read_text() if cascade_out.exists() else ""
    baseline_text = baseline_out.read_text() if baseline_out.exists() else ""
    cascade_verdicts = parse_cascade_verdicts(cascade_text)
    baseline_leads = parse_baseline_leads(baseline_text)
    union = union_dedupe(cascade_verdicts, baseline_leads, slither_leads)
    union_out.write_text(json.dumps(union, indent=2))

    n_slither_high = sum(1 for l in slither_leads if l["confidence"] == "HIGH-static")
    n_slither_med = sum(1 for l in slither_leads if l["confidence"] == "MEDIUM-static")
    n_slither_low = sum(1 for l in slither_leads if l["confidence"] == "LOW-static")
    print(f"\nCASCADE: {len(cascade_verdicts)} CONFIRMs (HIGH confidence)",
          file=sys.stderr)
    print(f"SLITHER: {len(slither_leads)} findings "
          f"(H={n_slither_high} M={n_slither_med} L={n_slither_low})",
          file=sys.stderr)
    print(f"BASELINE: {len(baseline_leads)} leads (NORMAL confidence)",
          file=sys.stderr)
    print(f"UNION (dedup): {len(union)} total\n", file=sys.stderr)

    # Admin-trust filter
    filtered, rejected = _admin_filter(union, scope, no_filter=args.no_filter)
    if rejected:
        print(f"ADMIN-TRUST FILTER: {len(rejected)} leads downgraded to REVIEW "
              f"({len(filtered) - len(rejected)} survivors)\n", file=sys.stderr)
        print("=== REJECTED — admin-trust scope (verify filter isn't too aggressive) ===",
              file=sys.stderr)
        for r in rejected:
            loc = r.get("location", "?")
            reason = r.get("admin_trust_reason", "?")
            claim = (r.get("claim") or r.get("raw", "?"))[:80]
            print(f"  • {loc}: {claim}  [{reason}]", file=sys.stderr)
        print("", file=sys.stderr)
    else:
        print(f"ADMIN-TRUST FILTER: 0 leads downgraded (all {len(filtered)} survive)\n",
              file=sys.stderr)

    # Adversarial verify — post-process HIGH-confidence CONFIRMs
    # Detect script dir: explicit override → sibling of scope → None
    if args.scripts_dir:
        scripts_dir = Path(args.scripts_dir).resolve()
    else:
        scripts_dir = None
        for candidate in ("script", "deploy", "scripts", "deployment"):
            d = scope / candidate
            if d.is_dir():
                scripts_dir = d
                break
    verified, adv_rejected = _adversarial_verify(
        filtered, scope, scripts_dir=scripts_dir, no_filter=args.no_filter)
    if adv_rejected:
        print(f"ADVERSARIAL VERIFY: {len(adv_rejected)} HIGH leads downgraded to "
              f"REVIEW:adversarial\n", file=sys.stderr)
        for d in adv_rejected:
            loc = d.get("location", "?")
            reasons = d.get("adversarial_reasons", [])
            claim = (d.get("claim") or d.get("raw", "?"))[:80]
            print(f"  • {loc}: {claim}", file=sys.stderr)
            for r in reasons:
                print(f"      {r}", file=sys.stderr)
        print("", file=sys.stderr)
    else:
        n_high = sum(1 for l in filtered if l.get("confidence") in ("HIGH", "CASCADE"))
        print(f"ADVERSARIAL VERIFY: all {n_high} HIGH leads survive\n", file=sys.stderr)

    # Write filtered union (REVIEW:* leads present for audit)
    filtered_out = out_dir / f"{args.slug}-filtered-leads.json"
    filtered_out.write_text(json.dumps(verified, indent=2))

    # Render only surviving (non-REVIEW) leads in the report
    report_leads = [l for l in verified if not str(l.get("confidence","")).startswith("REVIEW")]

    # Render
    reps = render_report(args.slug, args.sponsor, args.target, report_leads, report_out)
    elapsed = int(time.time() - t_start)

    n_review = len(rejected) + len(adv_rejected)
    print(f"\n=== DONE in {elapsed}s ===", file=sys.stderr)
    print(f"  cascade-grounded:  {cascade_out.relative_to(HERE)}  ({t_cascade}s)",
          file=sys.stderr)
    print(f"  slither:           {slither_out.relative_to(HERE)}  "
          f"({t_slither}s, {n_slither} detectors)",
          file=sys.stderr)
    print(f"  baseline-leads:    {baseline_out.relative_to(HERE)}  ({t_baseline}s)",
          file=sys.stderr)
    print(f"  union-leads.json:  {union_out.relative_to(HERE)}", file=sys.stderr)
    print(f"  filtered-leads:    {filtered_out.relative_to(HERE)}  "
          f"({len(report_leads)} actionable + {n_review} REVIEW)",
          file=sys.stderr)
    print(f"  report:            {report_out.relative_to(HERE)}", file=sys.stderr)
    if args.target == "sherlock":
        pdf_name = (f"{__import__('datetime').date.today().strftime('%Y.%m.%d')}"
                    f" - Final - {args.sponsor} Audit Report.pdf")
        print(f"\nNEXT: convert to PDF:\n  pandoc {report_out.relative_to(HERE)} "
              f"--pdf-engine=xelatex -o '{pdf_name}'", file=sys.stderr)
    print(f"\nTRIAGE: start with HIGH-confidence cascade verdicts in "
          f"{union_out.relative_to(HERE)}", file=sys.stderr)


if __name__ == "__main__":
    main()
