import { useState } from "react";
import { reviewStream } from "./api.js";
import GlassBox from "./components/GlassBox.jsx";
import Report from "./components/Report.jsx";

const INPUTS = [
  { id: "repo", label: "Repo folder", hint: "Path to a local folder to review" },
  { id: "github", label: "GitHub URL", hint: "Public repo URL — we clone + review it" },
  { id: "pr_url", label: "GitHub PR", hint: "Paste a GitHub PR URL — we fetch + review the diff" },
  { id: "pr_diff", label: "PR diff", hint: "Paste a unified diff to review changed lines" },
];

const PLACEHOLDER = {
  repo: "e.g. data/sample_repo",
  github: "https://github.com/PyCQA/bandit/tree/main/examples",
  pr_url: "https://github.com/owner/repo/pull/123",
  pr_diff: "Paste a unified diff (diff --git a/... b/...) here",
};

const DEFAULT_SOURCE = {
  repo: "data/sample_repo",
  github: "https://github.com/PyCQA/bandit/tree/main/examples",
  pr_url: "",
  pr_diff: "",
};

export default function App() {
  const [inputType, setInputType] = useState("repo");
  const [source, setSource] = useState("data/sample_repo");
  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState([]);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  async function onRun(e) {
    e.preventDefault();
    if (!source.trim() || running) return;
    setRunning(true);
    setError(null);
    setReport(null);
    setTrace([]);
    try {
      const final = await reviewStream(source, inputType, (u) => setTrace((t) => [...t, u]));
      setReport(final);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app">
      <header className="hero">
        <div className="brandbar">
          <img src="/echo-logo-dark.png" alt="echo by AX" className="brand-logo" />
          <span className="brand-div" />
          <span className="product">Scout</span>
        </div>
        <h1>Research-Aware <span className="grad">Code Review</span></h1>
        <p className="tagline">
          Agents review a repo or PR, ground every finding in <strong>real tool output
          + a best-practices corpus</strong>, self-check via a <strong>Critic loop</strong>,
          and produce a prioritized, cited report — not a linter wrapper.
        </p>
        <div className="pills">
          <span className="pill">⚙️ LangGraph</span>
          <span className="pill">🔧 Tool-grounded</span>
          <span className="pill">🛡️ Critic-verified</span>
          <span className="pill">📚 Cited</span>
        </div>
      </header>

      <form className="query-card" onSubmit={onRun}>
        <div className="modes">
          {INPUTS.map((m) => (
            <button
              type="button"
              key={m.id}
              className={`mode ${inputType === m.id ? "active" : ""}`}
              onClick={() => {
                setInputType(m.id);
                setSource(DEFAULT_SOURCE[m.id]);
              }}
              title={m.hint}
            >
              {m.label}
            </button>
          ))}
        </div>
        <textarea
          rows={inputType === "pr_diff" ? 8 : 1}
          placeholder={PLACEHOLDER[inputType]}
          value={source}
          onChange={(e) => setSource(e.target.value)}
          spellCheck={false}
        />
        <button className="run" type="submit" disabled={running || !source.trim()}>
          {running ? "Reviewing…" : "Run review →"}
        </button>
      </form>

      {error && <div className="error">⚠️ {error}</div>}

      {(running || trace.length > 0) && <GlassBox trace={trace} running={running} />}

      {report && <Report report={report} />}

      <footer className="foot">
        <img src="/echo-logo-dark.png" alt="echo by AX" className="foot-logo" />
        <span>Scout · LangGraph · Azure OpenAI gpt-4o · ruff/ast · ChromaDB · Workshop Project 8</span>
      </footer>
    </div>
  );
}
