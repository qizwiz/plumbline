Harden contest_day pipeline based on 2026-06-08 DRE App contest results.

EVIDENCE: We ran plumbline against DRE App / dreUSD (Sherlock contest 1259).
The cascade produced 12 verdicts with 2 CONFIRMs. Both CONFIRMs FAILED
adversarial review:
- dreShareOFT.initialize "front-run" — defeated by ERC1967Proxy atomic init
  (LLM didn't check the deployment script)
- batch DoS in fillWithdrawal — defeated by Sherlock's admin-trust-scope rule
  (LLM didn't apply the trust-framework filter)

The baseline produced 180 leads, NONE survived skeptical review.

Real findings produced by plumbline pipeline on this contest: 0
Real findings produced by manual human reading: 1 (Low/Info)

The gap is mechanical, not creative. Add the verification layers
plumbline is missing.

---

DONE WHEN ALL EIGHT HOLD:

1. tools/contest_day.py runs slither by DEFAULT after cascade + baseline,
   parsing the JSON output and including findings in the union with
   appropriate confidence tags. Slither High → confidence=HIGH-static,
   Medium → MEDIUM-static, Low → LOW-static.

2. tools/admin_trust_filter.py exists and post-processes union leads.
   For each lead, checks if the function/path is gated by:
   - onlyRole(X) / onlyOwner / onlyAdmin pattern
   - immutable address set in constructor
   - admin-set address that controls the attack vector
   If admin-trust-gated, downgrades the finding to "REVIEW: admin-trust"
   with a one-line reason. Sherlock's admin-trust rule auto-applied.

3. tools/adversarial_verify.py exists and post-processes "CONFIRM" verdicts
   from cascade output. For each CONFIRM, runs three mechanical checks:
   - "Is the entry point gated by access control?" (parse for onlyRole/onlyOwner)
   - "Is the called external contract admin-set?" (track address sources)
   - "Is the deployment script atomic for any 'initializer' concern?"
     (grep deployment scripts for pattern; if ERC1967Proxy w/ initData → atomic)
   If ANY check is YES → downgrade verdict to REVIEW with reason.

4. contest_day.py outputs a separate report section: "REJECTED — admin-trust
   scope" listing leads filtered by the trust filter, so JH can manually
   verify the filter isn't being too aggressive.

5. Smoke test on examples/sequence shows the new pipeline produces fewer
   noisy verdicts than the old pipeline (precision lift measured).

6. New cost projection in CONTEST_RUNBOOK.md: cascade+baseline+slither+
   adversarial verify ≈ same total cost (slither is free deterministic).

7. autonomous_spend.json updated, all changes committed and pushed.

8. The new pipeline tested on the DRE App scope produces ≤30 candidates
   total (was 182 today) and surfaces the manual-finding (batch DoS) as
   a survivor (not filtered out).

CONSTRAINTS:

- Slither must be in PATH or pipeline auto-detects via 
  /Users/jonathanhill/Library/Python/3.14/bin/slither (today's path)
- Admin-trust filter is MECHANICAL pattern matching, not LLM-as-judge
- Adversarial verify is MECHANICAL too (grep + AST checks)
- All filtering decisions logged with reasons so JH can audit
- Failsafe: --no-filter flag to bypass the verifiers if JH wants raw output

OUT OF SCOPE:

- LLM-driven adversarial verification (separate goal, this one is mechanical)
- Halmos/mythril integration (next goal after this one)
- Custom shape templates for protocol-specific bugs

WHY THIS GOAL EXISTS:

Today's calibration on a well-audited contest (DRE App, 3 prior audits)
showed plumbline's pipeline produces 200+ leads, 0 of which survive
adversarial verification. Manual reading produced the single finding.

The gap is verification, not generation. Plumbline already finds plausible
patterns; it doesn't reject them mechanically. This goal closes the gap
between "candidate produced" and "candidate worth a human's attention."

If this lands, the next DRE-style contest pipeline produces ~10-30 leads
instead of 200+, with much higher signal/noise, freeing JH to do skeptical
manual reading on the highest-leverage targets instead of triaging noise.
