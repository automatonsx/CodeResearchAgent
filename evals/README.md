# evals/ — planted-issue evaluation

Measure review quality on a repo whose issues we already know.

## Run
```bash
# from the repo root (backend venv active)
python -m evals.score
```

## What it reports
- **Recall** — how many of the planted issues in `expected.json` we caught.
- **Critic ablation** — findings **before vs. after** the Critic, i.e. how many false /
  duplicate / hallucinated findings it dropped. This is the measured anti-hallucination
  effect.
- **Tool-grounded ratio** — fraction of kept findings backed by a tool rule (high precision).

## Files
- `expected.json` — the answer key: `{file, line, type, what}` per planted issue.
  A finding matches a label by **file basename + line (±2)**.
- `score.py` — runs the pipeline once (no loop) so it can compare pre- vs post-Critic.

## Why precision is reported this way
The label set targets the **planted critical issues**, not every lint nit, so a raw
precision number against it would unfairly count legitimate extra findings as "wrong."
Instead we report the **tool-grounded ratio** + **Critic drop count** as the precision
evidence. To get a classic precision number, expand `expected.json` to label *every*
expected finding in the target.
