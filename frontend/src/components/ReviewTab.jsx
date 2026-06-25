import { useState } from "react";
import { reviewStream } from "../api.js";
import GlassBox from "./GlassBox.jsx";
import Report from "./Report.jsx";

const INPUTS = [
  { id: "repo",    label: "Repo folder",  hint: "Path to a local folder to review" },
  { id: "github",  label: "GitHub URL",   hint: "Public repo URL — we clone + review it" },
  { id: "pr_url",  label: "GitHub PR",    hint: "Paste a GitHub PR URL — we fetch + review the diff" },
  { id: "pr_diff", label: "PR diff",      hint: "Paste a unified diff to review changed lines" },
];

export default function ReviewTab({ codebase, onUpdate }) {
  const [inputType, setInputType] = useState(codebase.inputType || "repo");
  const [source, setSource]       = useState(codebase.source || "");
  const [running, setRunning]     = useState(false);
  const [trace, setTrace]         = useState([]);
  const [report, setReport]       = useState(codebase.lastReport || null);
  const [error, setError]         = useState(null);

  async function onRun(e) {
    e.preventDefault();
    if (!source.trim() || running) return;
    setRunning(true);
    setError(null);
    setReport(null);
    setTrace([]);
    try {
      const final = await reviewStream(source, inputType, (u) =>
        setTrace((t) => [...t, u])
      );
      setReport(final);
      if (final) {
        onUpdate({
          source,
          inputType,
          name: source.split(/[\\/]/).pop() || source,
          score: final.score,
          verdict: final.verdict,
          language: final.stats?.language || "",
          findingsCount: final.recommendations?.length || 0,
          lastReport: final,
        });
      }
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setRunning(false);
    }
  }

  const hint = INPUTS.find((i) => i.id === inputType)?.hint || "";

  return (
    <>
      <form className="panel" onSubmit={onRun}>
        <div className="modes">
          {INPUTS.map((m) => (
            <span
              key={m.id}
              className={`mode ${inputType === m.id ? "active" : ""}`}
              onClick={() => setInputType(m.id)}
              title={m.hint}
            >
              {m.label}
            </span>
          ))}
        </div>
        <div className="input-row">
          <input
            className="mono"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder={hint}
          />
          <button className="btn primary" type="submit" disabled={running || !source.trim()}>
            {running ? "Reviewing…" : "Run review →"}
          </button>
        </div>
      </form>

      {error && <div className="error">⚠️ {error}</div>}
      {(running || trace.length > 0) && <GlassBox trace={trace} running={running} />}
      {report && <Report report={report} />}
    </>
  );
}
