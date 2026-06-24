# data/ — sample inputs

- **`sample_repo/`** — a tiny Python repo with planted issues (hardcoded secret, SQL
  injection, `shell=True`, `eval`, bare except, mutable default, dead code). Review it
  in **repo** mode.
- **`sample.diff`** — a unified diff with planted issues. Review it in **pr_diff** mode.
- **`chroma/`** (gitignored) — the persisted ChromaDB best-practices index.

Try them:
```bash
python -m backend.graph "data/sample_repo" repo
python -m backend.graph "$(cat data/sample.diff)" pr_diff
```
