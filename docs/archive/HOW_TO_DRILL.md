# Calibration Drill — Pre-Contest Prep

The honest contest question: **does plumbline add to you, replace part of
you, or just make triage noisier?** The only way to answer is to drill on
the same corpora the model has, with the same scorer, and compare numbers.

## The drill (1 corpus, ~1–3 hours)

1. Pick a corpus you HAVEN'T memorized — e.g. `examples/boss-bridge`.
   **Do not open `examples/boss-bridge/.ANSWERS.md`.** Cold read.

2. Open the source files. Audit them like a real contest. Write findings to
   `examples/boss-bridge/MY_FINDINGS.md`. Format: one `## ` section per
   finding. Free prose. Anything that helps you remember the mechanism.
   Style hint: `## H-1 reentrancy in withdrawTo — sendValue at line 91 precedes state write at line 103`.

3. Score yourself:
   ```bash
   python tools/manual_rep.py examples/boss-bridge
   ```
   This logs a rep with `proposer.kind="manual"`, `version="human-cold-read"`,
   `author=$USER`. Same scorer the model gets.

4. Compare to the model's runs on the same corpus:
   ```bash
   python scoreboard.py --corpus boss-bridge
   ```
   You'll see your row alongside the sol_intent rows.

## Interpreting the diff

| your recall vs model's | what it tells you |
|---|---|
| higher | the model is *checking* you — use it as a redundancy layer, not a finder |
| lower | you're leaning on the model — the model is your finder; do not skip its triage |
| same | use ensemble — different runs find different things |
| both low | the corpus is hard for both — go slower, deeper read |

## Drilling the four Cyfrin corpora

The full pre-contest calibration (~6–10 hours total):

```bash
# 1. Cold audit, write findings, score yourself
for corpus in puppy-raffle t-swap thunder-loan boss-bridge sequence; do
  # write examples/$corpus/MY_FINDINGS.md from a cold read of the source
  python tools/manual_rep.py examples/$corpus
done

# 2. See where you stand vs the model
python scoreboard.py
```

After this you'll have your own recall/precision baseline on 5 corpora,
and you can plan contest-day workflow accordingly:
- If your numbers beat the model: do your own audit, use model output to catch your blind spots
- If model beats you: use model output as the primary triage list, deep-dive its leads

Honest scope note: the model has *probably* seen the four Cyfrin corpora
in training. Sequence (post-2025-10) is the only one that's genuinely novel
to it. So the most informative drill is **sequence** — it's the closest
proxy for contest-day.

## What this scaffold gives you for contest day

When the contest scope drops:
```bash
# 1. Copy scope into plumbline
cp -r path/to/contest-source examples/contest-2026/
gh api repos/<contest-org>/<repo>/contents/audit-data/findings.md > examples/contest-2026/.ANSWERS.md  # if a partial answer key is available
# (if no answer key yet, you can still run sol_intent and triage — score later)

# 2. Push (this triggers the cloud loop)
git add examples/contest-2026 && git commit -m "drill: contest 2026 scope" && git push

# 3. Watch the cloud workflow finish (~6 min)
gh run watch

# 4. Pull and triage
git pull
python scoreboard.py --corpus contest-2026

# 5. Do your own deep dive on the leads the model surfaced
```

The cloud loop runs in ~6 minutes, costs ~$1 in LLM calls. Triage is
ready by the time you've finished your coffee.
