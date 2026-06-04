# Plumbline

**Autonomous AI agents that do the rule-bound, evidence-heavy work — with governance that's *proven*, not promised.**

The hard part of deploying an AI *workforce* — not copilots, not RPA — isn't the model. It's
**governance**: how do you trust an agent making high-volume, rule-bound decisions when being
confidently wrong costs real money? Most "AI governance" is dashboards and review queues bolted on
after the fact. Plumbline is a working architecture where the governance is **theorem-checked**.

> **The AI proposes. A formally-verified gate disposes. The agent never grades its own homework.
> Humans govern only the edge cases the gate escalates.**

## The operating model (domain-general)

1. **Reason, don't keystroke.** An AI agent reads the artifact and hypothesizes where a rule is
   violated — the high-volume, evidence-heavy work humans were never going to do well at scale.
2. **Verify against ground truth.** Every conclusion is checked by concrete re-execution and, where
   the logic is subtle, a **Lean 4 machine-checked proof**. A finding counts *only* if it provably
   holds. Nothing confident-but-wrong survives the gate.
3. **Escalate judgment.** Anything the gate cannot soundly settle — anything needing a new assumption
   or a human call — is escalated, **never auto-accepted.**

Agents take the rule-bound load; a verified layer governs them; humans handle only what needs a
person. That is an AI-native operating model with governance baked into the architecture, not painted
on top.

## Governance as the harness, not a feature

Governance, compliance, and safety belong in the framework everything is built on — *auditable,
defensible, safe by design* — not bolted on as a later layer. Plumbline takes that literally:

- **Safe by design** = the trust kernel's soundness is a **machine-checked Lean 4 proof**, not an
  assertion. The agent cannot weaken it.
- **Auditable & defensible** = a proof is the strongest audit artifact there is. The basis for a
  finding is a derivation you can hand a regulator or an investigator — not "the model said so."

AI can write the code and propose the answers. It cannot build *this* — the verified foundation that
decides whether the whole system is worth trusting. That foundation is still human work.

## Proven on financial correctness

The working demonstration is smart-contract money-safety. Plumbline autonomously finds where value
can be improperly created or drained (e.g. ERC-4626 vault inflation / donation attacks), and **proves
each finding is real** by concrete replay — *zero false positives survive the gate*. The mathematical
core (a bounded-arithmetic abstraction) is discharged in **Lean 4 — 0 `sorry`, 0 axioms** — a
machine-checked trust kernel, not a promise. And it **self-extends**: on hitting a roadblock with no
handler, it generates a *new gated workflow* to dissolve it, escalating anything that would require an
unproven assumption.

The reasoning is exactly what evidence-heavy adjudication needs: *does this conform to the rules,
against the evidence, provably?* — at machine scale, with humans on the judgment calls.

## Why this is rare

One engineer at an intersection almost no one occupies:

- **AI-agent orchestration** — autonomous, self-improving, self-extending workflows.
- **Formal verification** — Lean 4, symbolic execution (halmos), SMT (z3): the governance layer, made
  sound.
- **Sound-systems discipline** — the insistence that the signal *governing* the agent must itself be
  verified, or the whole system confidently lies.

The model is commodity. The **verified governance layer is the moat** — and it's the hard part almost
no one builds.

## Honest status

A demonstrated capability, not a shipped product: it autonomously catches canonical real-world
correctness violations on real code, with machine-checked soundness. What's next is breadth (more
artifact shapes) and a grounded learning layer over its accumulating case library — learning from the
gate's verified verdicts, not surface similarity.

## Layout

| Path | Role |
|------|------|
| `pact_check.py` | wieldable entry point — point it at a contract, get a sound verdict |
| `roadblock_dispatch.py` | the autonomous engine: detect roadblock → gated workflow → log case |
| `adaptive_harness.py` | LLM plans the attack/invariant + the **concrete-replay validator** (the gate) |
| `summarize.py` | the soundness gate: z3 *screens*, Lean *admits* — never auto-blesses |
| `lean/SummaryObligation.lean` | the **trust kernel** — the obligation, proved (0 `sorry`, 0 axioms) |
| `prompts/` | the stochastic layer (proposes); everything it emits is gated |
| `.github/workflows/ci.yml` | Foundry + halmos run green in CI |

---

*Built by Jonathan Hill.*
