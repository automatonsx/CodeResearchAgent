# evals/ — planted-issue evaluation (stretch)

Measure review quality with a repo whose issues we already know.

## Idea
1. A test repo (e.g. `data/sample_repo`) with **planted, labelled issues**
   (`expected.json`: file, line, type).
2. Run the review graph over it.
3. Compare verified findings to the labels → **precision / recall**:
   - precision = real findings / all reported findings (false-positive rate)
   - recall = planted issues found / all planted issues
4. Track scores across changes; fail CI if precision/recall drop below a threshold.

## Files (to add)
- `expected.json` — ground-truth labels for the planted issues.
- `score.py` — runs the graph, matches findings to labels, prints precision/recall.

This is the quantitative answer to *"how do you know the Critic reduces hallucination?"*
