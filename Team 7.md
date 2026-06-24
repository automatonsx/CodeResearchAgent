# Scout — Multi-Agent Research Assistant

> Ask a question → get a sourced, critiqued research brief.
> One LangGraph multi-agent engine, three input modes. *(Workshop Project 8.)*

## What it does
Four agents work together to research a topic and produce a structured brief
with citations and risks — instead of one shallow, unsourced LLM answer.

| Agent | Job |
|-------|-----|
| **Planner** | Split the question into sub-questions |
| **Researcher** | Pull sources from the chosen mode |
| **Summarizer** | Turn sources into evidence + citations |
| **Critic** | Find gaps → loop back or approve |
| **Final Report** | Write: Summary · Findings · Sources · Risks |

## Three modes (one engine, swappable source)
- **Web** — research any topic online
- **Doc-RAG** — research over uploaded documents
- **Codebase audit** — scan a repo → what's missing (tests, error handling, docs)

