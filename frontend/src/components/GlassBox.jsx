// Glass-box view — show the live agent graph + state as it runs.

const STEPS = [
  { node: "context", label: "Context Extractor", desc: "Detect stack + files" },
  { node: "code_quality", label: "Code-Quality Agent", desc: "ruff + AST findings" },
  { node: "security", label: "Security Agent", desc: "bandit (S) rules / semgrep" },
  { node: "grounding", label: "Grounding", desc: "Attach corpus citations" },
  { node: "critic", label: "Critic", desc: "Verify file:line, drop false positives" },
  { node: "recheck", label: "↻ Re-check", desc: "Critic loop fired" },
  { node: "report", label: "Report Generator", desc: "Prioritize · score · verdict" },
];

export default function GlassBox({ trace, running }) {
  const seen = trace.map((t) => t.node);
  const current = seen[seen.length - 1];
  const loops = seen.filter((n) => n === "recheck").length;

  // Pull a few live stats out of the latest states.
  const lastCritic = [...trace].reverse().find((t) => t.node === "critic")?.state?.critique;

  return (
    <section className="glassbox">
      <div className="glass-head">
        <h2>🪟 Glass-box — agents at work</h2>
        {loops > 0 && <span className="loop-badge">Critic loop ×{loops}</span>}
      </div>
      <ol className="pipeline">
        {STEPS.map((s) => {
          const done = seen.includes(s.node);
          const active = running && current === s.node;
          if (s.node === "recheck" && loops === 0) return null;
          return (
            <li key={s.node} className={`step ${done ? "done" : ""} ${active ? "active" : ""}`}>
              <span className="dot" />
              <div>
                <div className="step-label">{s.label}</div>
                <div className="step-desc">{s.desc}</div>
              </div>
            </li>
          );
        })}
      </ol>

      {lastCritic && (lastCritic.dropped?.length || lastCritic.low_confidence?.length) ? (
        <div className="critic-note">
          Critic: dropped {lastCritic.dropped?.length || 0} unverifiable/duplicate ·{" "}
          {lastCritic.low_confidence?.length || 0} low-confidence flagged
        </div>
      ) : null}

      <details className="raw">
        <summary>Raw state updates ({trace.length})</summary>
        <pre>{JSON.stringify(trace, null, 2)}</pre>
      </details>
    </section>
  );
}
