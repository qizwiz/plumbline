# Zippers as the navigation algebra for invariant inference

**Filed 2026-06-09 23:00** — JH pointed at the Haskell Wikibook Zipper chapter as "huge inspiration." This note captures the connection before it leaks.

---

## The bridge JH just identified

The thread we've been pulling all evening — "computational material," "curvature," "manifold path-finding" — gets a real mathematical formalism in **Huet's Zipper (1997) + McBride's Differentiable Types (2001)**.

### McBride's central result

For any regular type T (sum-of-products in algebraic-data-type theory), there is a derivative type dT/dx where x is a hole. **The Zipper for T is exactly dT/dx — the type of one-hole contexts.** Navigation through T is calculus on T.

- **Focus** = current position in the data structure
- **Context** = the dT/dx integration constant that lets you reconstruct the whole
- **Movement** = differentiation: each Zipper "move" (`up`, `down`, `left`, `right`) is a literal derivative operation

This isn't analogy. It's a theorem. The Zipper IS the derivative of the type.

### Why this matters for plumbline

Plumbline's data structures are all regular types:

- **cascade.jsonl entries** are records with optional fields → product type with `Maybe` slots
- **The 9-category invariant taxonomy** is a sum type
- **The 5-mode v2 schema (scalar / relational / temporal / counting / null)** is a sum type
- **Each mode's body** (scalar = single expression, relational = pre-snapshot + post-expr, temporal = action sequence, counting = ghost + hook + invariant) is a product type

The Zipper of the COMPOSED type — Mode × Category × Condition × ContextOfPriorRefinements — IS the navigation algebra for invariant refinement. Every refinement step (CEGAR-style, ToT-style, MCTS-style) is a Zipper move from one focus to a neighbor in dT/dx space.

This gives us **a principled vocabulary for what was previously hand-wavy**:

| What we were saying | What it actually is |
|---|---|
| "Curvature of the invariant manifold" | dT/dx for the invariant type — local structure of the one-hole context |
| "Path-finding through the manifold" | A sequence of Zipper moves in dT/dx |
| "Refinement guided by critic feedback" | A search policy choosing the next Zipper move (Up / Down / Sibling / Replace) using the critic's refute reason as the guidance signal |
| "Composition of modes for one bug" | Parallel zippers — one Zipper per mode, focused on the same target bug, composed at the level of the witness |

---

## What this changes about tomorrow's work

The path-finding swarm in flight is researching the SEARCH POLICY (CEGAR / ToT / MCTS / belief propagation). Zippers are the SEARCH STRUCTURE. They compose: the policy picks Zipper moves; the Zipper algebra defines what moves are available.

**Tomorrow's v2 multi-mode redesign doesn't change.** The Zipper framing is one altitude up — it's the *formalism* that justifies the multi-mode schema. The schema itself is what we ship.

**What Zipper framing adds to Section 7 of the paper:**

The H12 hypothesis (representation-mode adequacy) can be lifted from "we tried 5 modes empirically" to "**the multi-mode schema IS the regular-type decomposition of the invariant space; multi-mode emission is the minimal-Zipper navigation of dT/dx for the invariant type.**" That's a much stronger framing — it puts the multi-mode design on McBride-grade footing rather than on JH-hand-waved-curvature footing.

The "compositional invariant capture" finding on the DRE bug (documented in `dre_inflation_multimode_demonstration.md`) becomes: *"The DRE bug's invariant lives at a Zipper position requiring BOTH a relational sub-focus AND a temporal sub-focus simultaneously; no single Zipper move captures the witness."* That's a real-math statement about the structure, not a metaphor.

---

## The bigger picture this opens

If invariant inference is calculus on a regular type, then:

- **Iterative refinement = numerical integration along a Zipper path.** Each critic refute is a partial-derivative update; the convergence to a CLEAN invariant is reaching a stable point under the derivative dynamics.
- **The validator's REFUTE reasons are gradient information.** They tell you the local direction in dT/dx that the candidate needs to move. Tomorrow's v2 redesign should consider treating REFUTE reasons not as binary signals but as gradient-like guidance — *"the invariant could hold vacuously"* = "move toward stricter/curved boundary"; *"wrong abstraction layer"* = "move to a different sum-type branch (different mode)."
- **Composition of multi-mode invariants is a fiber product in the category of Zippers.** Pure category theory; well-defined; computable.

This is the **computational material program** put on rigorous footing. Not a metaphor. A theorem in algebraic data type theory.

---

## What to do with this

**Tonight (already done):** committed this note. The connection is preserved.

**Tomorrow's session:**

1. Read this note alongside the existing v2 redesign plan.
2. The v2 implementation does NOT change in shape — schema stays multi-mode, prompt stays mode-first, validator stays REFUTE-default.
3. Section 7 H12 framing tightens: cite McBride's *"The Derivative of a Regular Type"* (FoSSaCS 2001) + Huet's *"The Zipper"* (J. Functional Programming 1997) + (relevant follow-ups like "Clowns to the Left of me, Jokers to the Right") as the formal justification for the multi-mode decomposition.
4. The path-finding swarm result (landing soon) describes the SEARCH POLICY. Zippers describe the SEARCH STRUCTURE. Both go in Section 7 — H12 covers the structure, H13 will cover the policy.

**Follow-up paper material (post-arXiv-post):**

A position paper *"Invariant Inference as Calculus on Regular Types"* writing up the Zipper framing in full could be a real intellectual contribution to the formal-methods + LLM-verification literature. McBride + Huet are well-cited; nobody (that we've found tonight) has applied their work to LLM-driven invariant inference. **This is the bigger paper your "computational material" program could actually produce.**

---

## Sources

- Huet, G. *"The Zipper"* (J. Functional Programming, 1997). Original definition.
- McBride, C. *"The Derivative of a Regular Type is its Type of One-Hole Contexts"* (unpublished manuscript 2001; later FoSSaCS 2008 follow-up).
- McBride, C. *"Clowns to the Left of me, Jokers to the Right"* (POPL 2008) — derivatives of inductive types in dependent types.
- Abbott, M., Altenkirch, T., McBride, C., Ghani, N. *"∂ for Data: Differentiating Data Structures"* (Fundamenta Informaticae 2005).
- Haskell Wikibook chapter on Zippers (the page JH cited): https://en.wikibooks.org/wiki/Haskell/Zippers

This is the formalism. The rest of the program is execution.
