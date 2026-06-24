# frontend/ — Scout (React + Vite)

The app is already scaffolded. Just install and run:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The dev server **proxies `/api` → `http://localhost:8000`** (FastAPI), so start the
backend too (from the repo root):

```bash
uvicorn backend.main:app --reload
```

## Structure
- `src/App.jsx` — input (repo folder path OR PR diff) + run orchestration.
- `src/api.js` — calls `/review` and streams `/review/stream` (glass-box updates).
- `src/components/GlassBox.jsx` — live agent pipeline + Critic-loop / drop stats.
- `src/components/Report.jsx` — verdict + score, then findings: severity, `file:line`,
  fix, 🔧 tool evidence, 📚 best-practice citation.
- `src/styles.css` — branded dark theme.

## Inputs
- **Repo folder** — a local path (try `data/sample_repo`).
- **GitHub URL** — a public repo; the backend clones it. A `…/tree/<branch>/<subdir>`
  link reviews just that subfolder (try `https://github.com/PyCQA/bandit/tree/main/examples`).
- **PR diff** — paste a unified diff (try `data/sample.diff`).
