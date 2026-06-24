# Scout — Multi-Agent Research Assistant
### End-to-End Build Spec (Team Handoff)

> **Workshop Project 8** · LangGraph multi-agent system · Build target: ~1.5 days
> *(Rename "Scout" to your team's product name + theme.)*

---

## 1. One-line vision
A team of AI agents that **research a question, fact-check themselves, and deliver a
sourced brief that ends in a usable action** — across three sources: the web, your own
documents, and a codebase.

We are NOT building "another chatbot." The difference is: **multiple specialized agents,
a self-correcting critic loop, citations on every claim, and an action artifact at the end.**

---

## 2. The problem & who it's for

A single LLM answer is shallow, unsourced, and you can't trust it. Scout fixes this with
specialized agents that divide the work and check each other.

| Mode | User | What they get |
|------|------|---------------|
| **Web research** | Sales team | A company/prospect brief with citations + talking points → drafts an **outreach email** |
| **Document research** | Product / PM | Research over our own docs + web → drafts a **PRD / spec** |
| **Codebase audit** | Engineers | Scan a repo → "what's missing" report → proposes **fixes / a PR** |

---

## 3. Core architecture — the multi-agent graph

Five agents, wired in **LangGraph**. The same engine runs all three modes; only the
**Researcher's source adapter** changes.

| Agent | Responsibility | Output |
|-------|----------------|--------|
| **Planner** | Break the question into 3–4 sub-questions | `sub_questions[]` |
| **Researcher** | Pull sources from the active mode (web / docs / code) | `sources[]` |
| **Summarizer** | Distill sources into evidence snippets *with citations* | `evidence[]` |
| **Critic** | Find gaps, contradictions, weak/unsourced claims → loop back or approve | `critique{}` |
| **Final Report** | Synthesize the brief + the action artifact | `final_brief{}` |

### Orchestration graph (the custom twist 🟡)
```
START
  │
  ▼
Planner ─► Researcher ─► Summarizer ─► Critic
                ▲                         │
                │   "gaps / weak sources" │
                └─────────── re-research ─┤   (max 2 loops)
                                          │
                              "good enough" │
                                          ▼
                                   Final Report ─► END
```
The **Critic → Researcher loop** is what makes this *agentic*, not a linear pipeline.
Cap it at 2 iterations so it always terminates.

### Shared state object
```python
from typing import TypedDict

class ResearchState(TypedDict):
    mode: str                # "web" | "docs" | "code"
    question: str
    sub_questions: list[str]
    sources: list[dict]      # {title, url_or_path, snippet}
    evidence: list[dict]     # {claim, source_ref, confidence}
    critique: dict           # {gaps: [], conflicts: [], needs_more: bool}
    iterations: int          # loop guard (max 2)
    final_brief: dict        # {summary, findings, sources, risks, action}
```

---

## 4. The three modes (one engine, swappable source)

| | **Web** | **Document** | **Codebase audit** |
|--|---------|--------------|--------------------|
| **Source adapter** | Tavily web search | ChromaDB over uploaded files + web | Repo file walk + parse |
| **Researcher pulls** | Web pages | Doc chunks (+ web) | Files, tests, configs |
| **Critic checks** | Source quality, recency | Coverage of the ask | Missing tests, error handling, security, docs |
| **Action output** | Outreach email draft | PRD / spec draft | Fix list + proposed PR/patch |
| **Build priority** | ✅ Day 1 (safest) | Should-have | Should-have (most unique) |

> **Scope rule:** get **ONE mode fully working end-to-end first** (recommend Web).
> Add a second mode only once the first is solid.

---

## 5. Features we will implement

### Must-have (core demo)
- [ ] LangGraph graph: Planner → Researcher → Summarizer → Final Report
- [ ] Web mode with real search (Tavily)
- [ ] Structured brief: **Summary · Findings · Sources · Risks**
- [ ] **Claim-level citations** — every finding links to a source
- [ ] `run-brief` custom Skill
- [ ] Branded UI (landing + result page)

### Should-have (the differentiators)
- [ ] **Critic → Researcher loop** (self-correction)
- [ ] **Action output** per mode (email / PRD / fix-proposal)
- [ ] **Second mode** (docs or code)
- [ ] **Glass-box view** — show the live agent graph + state as it runs
- [ ] **Source-conflict detection** — surface contradictions instead of hiding them

### Stretch (bonus points)
- [ ] **LLM-judge eval** — auto-score each brief's quality (`evals/`)
- [ ] **Human-in-the-loop** — approve/edit sub-questions before research
- [ ] **Confidence scoring** per finding
- [ ] **Cross-brief memory** — reuse prior evidence
- [ ] Export to PDF / Markdown
- [ ] Docker deployment

---

## 6. What makes it unique (vs. a traditional research bot)
1. **Self-correcting Critic loop** — rejects weak findings and re-researches.
2. **Action-ending modes** — outputs an artifact (email/PRD/fix), not just text.
3. **One engine, three source adapters** — architecture, not a single-purpose script.
4. **Claim-level grounding** — every sentence is traceable; unsourced claims are killed.
5. **Source-conflict detection** — shows disagreement instead of averaging it away.
6. **Glass-box orchestration** — users watch the agents work and see *why*.
7. **Self-eval + risk section** — states its own confidence instead of over-claiming.

---

## 7. Anti-hallucination strategy (grading requirement)
- Every claim in the brief **must** carry a source reference.
- The **Critic** rejects any claim without a supporting source and forces re-research.
- The brief always includes a **Risks / Unknowns** section — what it could *not* confirm.
- Source-conflict detection prevents confident-but-wrong synthesis.

---

## 8. Tech stack
| Layer | Choice | Notes |
|-------|--------|-------|
| Frontend | **React** | Branded UI, glass-box view, result/action pages |
| Backend | **FastAPI** | REST + streaming endpoints; runs the graph |
| Orchestration | **LangGraph** | State graph + conditional Critic loop |
| LLM glue | **LangChain** | Used where needed (LLM calls, tool wiring) |
| LLM | **Azure OpenAI** (`gpt-4o`) | Verified working — see `.env.example` |
| Web search | **Tavily API** | Built for LLM research |
| Doc retrieval | **ChromaDB** | For document mode |
| Deployment | **Docker** (local) or Azure | Bonus points |

**Flow:** React → FastAPI → LangGraph (agents via LangChain) → Azure OpenAI / Tavily / ChromaDB.

---

## 9. Repo structure (matches workshop requirements)
```
scout/
  README.md  DESIGN.md  AI_USAGE.md  REFERENCES.md  DEMO_SCRIPT.md  LIMITATIONS.md
  .claude/
    skills/run-brief/SKILL.md      # custom Skill #1 (graded)
    skills/audit-repo/SKILL.md     # custom Skill #2 (bonus, code mode)
  backend/                         # FastAPI app
    main.py                        # API routes (POST /research, stream progress)
    graph.py                       # LangGraph wiring + state
    llm.py                         # Azure OpenAI client (LangChain)
    agents/                        # planner, researcher, summarizer, critic, report
    adapters/                      # web.py (Tavily), docs.py (ChromaDB), code.py
    actions/                       # email.py, prd.py, fix.py
  frontend/                        # React app (Vite)
  prompts/                         # one prompt file per agent
  evals/                           # LLM-judge test set
  deployment/                      # Dockerfile + steps
  data/                            # sample inputs (docs, a test repo)
  ai/knowledge/  ai/memory/
```

---

## 10. Custom Claude Code Skills (graded — 10 marks)
- **`run-brief`** — run the full graph for a topic/mode and save the brief to `/briefs`.
- **`audit-repo`** (bonus 2nd Skill) — run the codebase-audit mode on a target repo.

Each is a `SKILL.md` with frontmatter (`name`, `description`) + instructions, committed
and **demoed live** (required for full marks).

---

## 11. Scope by phase

| Phase | Goal |
|-------|------|
| **Day 1 AM** | DESIGN.md · repo skeleton · LangGraph happy path (Planner→Researcher→Report), web mode |
| **Day 1 PM** | Citations · branded UI · `run-brief` Skill · first end-to-end demo |
| **Day 2 AM** | Critic loop · action output · second mode |
| **Day 2 PM** | Glass-box view · conflict detection · eval · polish · docs · rehearse demo |

> **Even 50–80% is fine.** A tight, working single-mode demo beats three half-built modes.

---

## 12. Team roles (3 people)
| Role | Owns |
|------|------|
| **Backend / Graph** | FastAPI app, LangGraph wiring, agents, state, Critic loop, adapters |
| **Frontend / UX** | React app, branded UI, glass-box view, result/action pages |
| **Integrations / Docs** | Tavily + ChromaDB hookup, Skills, evals, AI_USAGE.md, DESIGN.md, demo script |

Keep **AI_USAGE.md live** from hour one (tools used, Skills fired, AI vs human %).

---

## 13. Demo plan (7 minutes)
1. **(1m)** Problem + user (sales/PM/eng).
2. **(2m)** Architecture + the orchestration graph.
3. **(2m)** Live run — show the Critic loop firing + trigger the `run-brief` Skill.
4. **(1m)** Show the final brief with clickable sources + the action artifact.
5. **(1m)** AI usage (what AI generated vs. what we designed) + limitations.

---

## 14. Out of scope / limitations
- No auth, multi-user, or persistent production DB.
- No fine-tuning — prompting + orchestration only.
- Text sources only (no audio/video/images).
- Codebase mode reads/analyzes; it proposes patches but doesn't auto-merge.

---

## 15. Hackathon deliverables checklist
- [ ] `DESIGN.md` — answer the 10 questions (problem, user, flow, why this architecture,
      what's agentic, what's RAG, what can go wrong, hallucination reduction, what we
      didn't build, 2-week plan)
- [ ] `AI_USAGE.md` — kept live
- [ ] `REFERENCES.md` — every reused repo/template declared (+ our 3+ custom features)
- [ ] `DEMO_SCRIPT.md` + `LIMITATIONS.md`
- [ ] ≥1 custom Skill (2 for full marks), demoed live
- [ ] Company branding / theme
- [ ] Docker or Azure deployment
- [ ] Git history with readable commits (Linear/tracker = bonus)

---

## 16. Getting started
```bash
# 1. Create the repo skeleton (section 9)
cp .env.example .env            # Azure key prefilled; add TAVILY_API_KEY

# 2. Backend (FastAPI + LangGraph)
cd backend
pip install fastapi uvicorn langgraph langchain langchain-openai chromadb tavily-python
uvicorn main:app --reload       # serves the API

# 3. Frontend (React)
cd ../frontend
npm create vite@latest . -- --template react
npm install && npm run dev

# 4. Build graph.py with the state object (section 3), wire the happy path
# 5. Run the web mode end-to-end, then add the Critic loop
```
