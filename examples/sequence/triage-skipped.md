# Triage skipped — examples/sequence/ (DRY-RUN)

Per §5 of the goal contract. Every dropped candidate, 1-line reason.

## Skipped

- **LEAD-11 (L-05)** — low-prob: gas-optimization informational; not a contest-worthy finding for dry-run substrate validation.
- **LEAD-12 (L-06)** — low-prob: code-quality informational (duplicated delegatecall validation); not security-critical.

## Notes

For real-contest mode, L-* informationals would still be submitted (separate severity tier, low payout but worth listing). Dry-run focuses substrate validation on H/M tier where the mechanical-citation pipeline matters most.
