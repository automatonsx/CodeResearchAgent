# Sentinel — Research-Aware Code Review Assistant
### 1.5-Day Hackathon Build Spec (Team Handoff)

> **Workshop Project 8 (multi-agent) + Project 6 (review) blend** · LangGraph
> Build target: ~1.5 days · *(Rename "Sentinel" to your team's product name + theme.)*
>
> This is the **scoped MVP** of the full vision in `plan.md`. The big-picture plan
> (12 agents, an academic research corpus, GitHub Action) is the 2-week roadmap.
> This file is what we actually build in the hackathon.

---

## 1. What it is (one line)
A team of AI agents that review a **pull request or a small repo**, ground every
finding in **real tool output + a curated best-practices corpus**, self-check via a
**Critic loop**, and produce a **prioritized, cited report** — not a linter wrapper.

**The hook:** *"Your code has issue X — here's the principle/source behind it, the fix,
and the effort it takes."* Every finding is verified before it's shown.

---

## 2. Scope — what's IN and what's OUT

### ✅ IN (1.5 days)
- **One input:** a PR diff **or** a small repo folder (Python + JS only)
- **3 review agents:** Code-Quality · Security · (+ Critic + Report)
- **Tool-grounded findings:** `ruff`/`eslint`, `semgrep`, Python `ast`
- **Critic loop:** rejects unsupported/low-confidence findings → re-check
- **Curated mini-corpus:** ~10–15 best-practice snippets in ChromaDB for citations
- **Report:** prioritized, scored, cited (Markdown + JSON)
- **React UI** + **FastAPI** backend
- **1 custom Skill** (`review-repo`), demoed live

### ❌ OUT (this is the 2-week roadmap, not now)
- The 5 domain agents (distributed systems, ML, DB, API, scalability)
- Scraping arxiv / IEEE / ACM (use the curated mini-corpus instead)
- GitHub Action / inline PR comments
- "Learns team preferences", PDF export, multi-language, auto-fix/merge

> **Golden rule:** get **one input + 2 agents + Critic + report** working end-to-end
> on Day 1. Everything else is additive.

---

## 3. Architecture

```
Input (PR diff  OR  small repo)
        ↓
  Context Extractor          → detect stack (Python/JS), entry points
        ↓
  Orchestrator (LangGraph)
        ↓
  ┌─────────────┬──────────────┐
  ↓             ↓              ↓
 Code-Quality  Security    Grounding
 Agent         Agent       (cite curated corpus)
 (ruff/ast)    (semgrep)
        ↓
     Critic  ──"unsupported / low-confidence findings"──┐
        ↑                                               │
        └──────────────── re-check (max 2) ─────────────┘
        ↓ "validated"
  Report Generator  → prioritize · score · cite
        ↓
  Output (Markdown + JSON; UI render)
```

The **Critic loop** is the agentic twist 🟡 — it makes this more than a fan-out pipeline.

---

## 4. Agents

| Agent | Job | Grounded by |
|-------|-----|-------------|
| **Context Extractor** | Detect language/stack, find files to review | file walk |
| **Code-Quality Agent** | Smells, complexity, dead code, missing tests | `ruff`/`eslint`, `ast` |
| **Security Agent** | Secrets, injection, unsafe calls | `semgrep` |
| **Grounding step** | Attach a best-practice citation to each finding | ChromaDB corpus |
| **Critic** | Verify each finding is real + sourced; drop false positives → loop | re-reads `file:line` |
| **Report Generator** | Prioritize, score, format the final report | — |

> Keep it to these. Resist adding more agents — depth beats breadth here.

---

## 5. Validation (how we trust the output — the key design story)

The LLM **proposes**; tools and the Critic **verify**:
1. **No finding without a `file:line`** the Critic can re-open and confirm.
2. **Tool facts vs. LLM opinion** — `semgrep`/`ruff`/`ast` results are ground truth;
   only "weak error handling"-type findings are LLM judgment, and must quote the code.
3. **Critic loop** drops unsupported or duplicate findings and re-checks low-confidence ones.
4. **Eval set (stretch):** plant known issues in a test repo → measure precision/recall.

This is the answer to the grading question *"how did you reduce hallucination?"*

---

## 6. State

```python
from typing import TypedDict

class ReviewState(TypedDict):
    input_type: str            # "pr_diff" | "repo"
    source: str                # diff text or repo path
    context: dict              # {language, files, entry_points}
    tool_findings: list        # raw output from ruff/eslint/semgrep/ast
    findings: list             # LLM-structured findings (see schema §7)
    citations: list            # corpus matches per finding
    critique: dict             # {dropped: [], low_confidence: [], needs_recheck: bool}
    iterations: int            # loop guard (max 2)
    final_report: dict         # {summary, recommendations, verdict, score}
```

---

## 7. Finding / Report schema

```python
output_schema = {
    "recommendations": [
        {
            "type": "code | security | style | test",
            "severity": "critical | major | minor | suggestion",
            "file": "path/to/file.py",
            "line": 42,
            "issue": "what is wrong",
            "suggestion": "what to do instead",
            "example": "corrected snippet",
            "research_basis": ["best-practice citation"],   # from corpus
            "tool_evidence": "semgrep rule id / ruff code", # ground truth
            "effort": "low | medium | high",
            "confidence": 0.0
        }
    ],
    "verdict": "approve | request_changes | discuss",
    "score": 7.5,
    "summary": "..."
}
```

---

## 8. Tech stack (locked)

| Layer | Choice |
|-------|--------|
| Frontend | **React** (Vite) |
| Backend | **FastAPI** |
| Orchestration | **LangGraph** (+ **LangChain** glue) |
| LLM | **Azure OpenAI** (`gpt-4o`) — verified, see `.env.example` |
| Code parsing | Python `ast`, **tree-sitter** (optional) |
| Static analysis | **ruff**/**eslint**, **semgrep** |
| Git (PR mode) | **GitPython** |
| Corpus / RAG | **ChromaDB** + Azure embeddings |
| Deployment | **Docker** (local) |

**Flow:** React → FastAPI → LangGraph (agents via LangChain) → Azure gpt-4o / semgrep / ChromaDB.

---

## 9. Repo structure

```
sentinel/
  README.md  DESIGN.md  AI_USAGE.md  REFERENCES.md  DEMO_SCRIPT.md  LIMITATIONS.md
  .claude/skills/review-repo/SKILL.md     # custom Skill (graded)
  backend/                                 # FastAPI
    main.py                                # POST /review (diff or repo), stream progress
    graph.py                               # LangGraph wiring + state
    llm.py                                 # Azure OpenAI client (LangChain)
    agents/                                # context, code_quality, security, critic, report
    tools/                                 # ruff_runner.py, semgrep_runner.py, ast_utils.py
    corpus/                                # curated best-practices + build_index.py
  frontend/                                # React (Vite) — input + report view
  evals/                                   # planted-issue test repo (stretch)
  deployment/                              # Dockerfile
  data/                                    # sample PR diff + sample repo to demo on
```

---

## 10. Custom Claude Code Skill (graded — 10 marks)
- **`review-repo`** — run the full review graph on a target repo/diff and save the report.
- Stretch 2nd Skill: **`build-corpus`** — (re)build the best-practices ChromaDB index.

`SKILL.md` = frontmatter (`name`, `description`) + instructions. **Demo it live.**

---

## 11. Phased plan (1.5 days)

| Phase | Deliverable |
|-------|-------------|
| **Day 1 AM** | DESIGN.md · skeleton · LangGraph happy path: Context → Code-Quality → Report on a sample repo |
| **Day 1 PM** | `semgrep`/`ruff` wired as ground truth · structured findings (schema §7) · React report view · first end-to-end demo |
| **Day 2 AM** | **Critic loop** · Security agent · curated corpus + citations · `review-repo` Skill |
| **Day 2 PM** | Scoring/prioritization · branding · Docker · docs · rehearse 7-min demo |

> **50–80% is fine.** A tight diff-review demo with the Critic loop beats a half-built 12-agent system.

---

## 12. Team roles (3 people)

| Role | Owns |
|------|------|
| **Backend / Graph** | FastAPI, LangGraph wiring, agents, Critic loop, state |
| **Tools / RAG** | ruff/eslint/semgrep/ast runners, ChromaDB corpus, citations, evals |
| **Frontend / Docs** | React UI, report view, Skill, AI_USAGE.md, DESIGN.md, demo script |

Keep **AI_USAGE.md live** from hour one.

---

## 13. Demo plan (7 minutes)
1. **(1m)** Problem + user (engineers reviewing PRs).
2. **(2m)** Architecture + the Critic loop.
3. **(2m)** Live: run on a sample repo → watch agents → **Critic drops a false positive** → trigger `review-repo` Skill.
4. **(1m)** Final report: prioritized findings with `file:line`, tool evidence + citation.
5. **(1m)** AI usage (AI-generated vs. human-designed) + limitations.

---

## 14. Limitations (state these — it scores)
- Python + JS only; small/medium repos (large repos need chunking — roadmap).
- Best-practice corpus is curated (~10–15 entries), not full academic literature.
- Proposes fixes; does **not** auto-merge.
- Logic-bug detection is best-effort; strongest on security, style, missing tests.

---

## 15. Getting started
```bash
cp .env.example .env            # Azure key prefilled; add embeddings if needed

# Backend
cd backend
pip install fastapi uvicorn langgraph langchain langchain-openai chromadb \
            semgrep ruff gitpython
uvicorn main:app --reload

# Frontend
cd ../frontend
npm create vite@latest . -- --template react
npm install && npm run dev

# Build order:
# 1) graph.py state (§6) + happy path: Context → Code-Quality → Report
# 2) wire ruff/semgrep as ground truth → structured findings (§7)
# 3) add the Critic loop, then Security agent, then corpus citations
```

---

## 16. Deliverables checklist
- [ ] `DESIGN.md` (10 questions: problem, user, flow, why this architecture, what's agentic,
      what's RAG, what can go wrong, hallucination reduction, what we didn't build, 2-week plan)
- [ ] `AI_USAGE.md` (live) · `REFERENCES.md` · `DEMO_SCRIPT.md` · `LIMITATIONS.md`
- [ ] ≥1 custom Skill, demoed live
- [ ] Branding / theme · Docker deployment · readable git history
