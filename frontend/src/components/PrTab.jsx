import { useState } from "react";
import { reviewStream } from "../api.js";
import GlassBox from "./GlassBox.jsx";
import Report from "./Report.jsx";

function verdictClass(v) {
  return { approve: "v-approve", discuss: "v-discuss", request_changes: "v-changes" }[v] || "";
}

export default function PrTab({ codebase, onUpdate }) {
  const [prs, setPrs]         = useState(codebase.prs || []);
  const [prUrl, setPrUrl]     = useState("");
  const [running, setRunning] = useState(false);
  const [trace, setTrace]     = useState([]);
  const [error, setError]     = useState(null);
  const [selected, setSelected] = useState(null);

  async function reviewPr(e) {
    e.preventDefault();
    if (!prUrl.trim() || running) return;
    setRunning(true);
    setError(null);
    setTrace([]);
    try {
      const final = await reviewStream(prUrl, "pr_url", (u) =>
        setTrace((t) => [...t, u])
      );
      if (final) {
        const titleParts = prUrl.split("/");
        const prNum = titleParts[titleParts.length - 1];
        const repo  = titleParts.slice(-4, -2).join("/");
        const pr = {
          id: Date.now().toString(),
          url: prUrl,
          title: `PR #${prNum} — ${repo}`,
          meta: prUrl,
          verdict: final.verdict,
          score: final.score,
          findingsCount: final.recommendations?.length || 0,
          report: final,
          reviewedAt: new Date().toISOString(),
        };
        const next = [pr, ...prs];
        setPrs(next);
        onUpdate({ prs: next });
        setSelected(pr.id);
        setPrUrl("");
      }
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <form className="pr-add-form" onSubmit={reviewPr}>
        <input
          className="mono"
          value={prUrl}
          onChange={(e) => setPrUrl(e.target.value)}
          placeholder="https://github.com/owner/repo/pull/123"
        />
        <button className="btn primary" type="submit" disabled={running || !prUrl.trim()}>
          {running ? "Reviewing…" : "Review PR →"}
        </button>
      </form>

      {error && <div className="error">⚠️ {error}</div>}
      {(running || trace.length > 0) && <GlassBox trace={trace} running={running} />}

      {prs.length === 0 && !running && (
        <p style={{ color: "var(--muted)" }}>
          No PR reviews yet. Paste a GitHub PR URL above to run the first one.
        </p>
      )}

      {prs.map((pr) => (
        <div
          key={pr.id}
          className={`prcard ${selected === pr.id ? "selected" : ""}`}
          onClick={() => setSelected(selected === pr.id ? null : pr.id)}
        >
          <div className="prstate open">🔀</div>
          <div>
            <div className="prtitle">{pr.title}</div>
            <div className="prmeta mono">{pr.meta}</div>
          </div>
          <div className="prnums">
            {pr.verdict && (
              <span className={`verdict ${verdictClass(pr.verdict)}`}>
                {pr.verdict.replace("_", " ")}
              </span>
            )}
            {pr.score != null && <span>{Number(pr.score).toFixed(1)}/10</span>}
            <span>{pr.findingsCount} findings</span>
          </div>
        </div>
      ))}

      {selected && (() => {
        const pr = prs.find((p) => p.id === selected);
        return pr?.report ? (
          <div style={{ marginTop: 22 }}>
            <Report report={pr.report} />
          </div>
        ) : null;
      })()}
    </>
  );
}
