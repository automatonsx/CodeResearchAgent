// Result page — prioritized findings with file:line, tool evidence + citation.

const VERDICT_LABEL = {
  approve: "✅ Approve",
  discuss: "💬 Discuss",
  request_changes: "🚫 Request changes",
};

function fileName(path = "") {
  return path.split(/[\\/]/).pop();
}

function Finding({ f }) {
  return (
    <li className={`finding sev-${f.severity}`}>
      <div className="finding-head">
        <span className={`badge ${f.severity}`}>{f.severity}</span>
        <span className="ftype">{f.type}</span>
        <span className="floc">{fileName(f.file)}:{f.line}</span>
        {f.tool_evidence ? (
          <span className="tool" title="Ground-truth tool rule">🔧 {f.tool_evidence}</span>
        ) : (
          <span className="tool judgment" title="LLM judgment — Critic-verified">⚖ judgment</span>
        )}
        {typeof f.confidence === "number" && (
          <span className="conf">conf {Number(f.confidence).toFixed(2)}</span>
        )}
        {f.effort && <span className="effort">effort: {f.effort}</span>}
      </div>

      <div className="issue">{f.issue}</div>
      {f.suggestion && <div className="suggest"><strong>Fix:</strong> {f.suggestion}</div>}
      {f.example && <pre className="example">{f.example}</pre>}
      {f.research_basis?.length > 0 && (
        <div className="basis">📚 {f.research_basis.join("; ")}</div>
      )}
    </li>
  );
}

export default function Report({ report }) {
  const recs = report.recommendations || [];
  const stats = report.stats || {};
  return (
    <section className="brief">
      <div className="report-head">
        <h2>🛡️ Review Report</h2>
        <div className="verdict-row">
          <span className={`verdict ${report.verdict}`}>
            {VERDICT_LABEL[report.verdict] || report.verdict}
          </span>
          <span className="score">
            {report.score == null ? "n/a" : `${report.score}/10`}
          </span>
        </div>
      </div>

      <div className="block">
        <h3>Summary</h3>
        <p>{report.summary}</p>
        <div className="statline">
          {stats.verified} verified · {stats.dropped} dropped by Critic ·{" "}
          {stats.iterations} re-check loop(s) · {stats.language}
          {typeof stats.reviewed === "number" && (
            <> · reviewed {stats.reviewed} file(s)
              {stats.skipped > 0 ? `, skipped ${stats.skipped}` : ""}</>
          )}
        </div>
      </div>

      <div className="block">
        <h3>Findings ({recs.length})</h3>
        {recs.length ? (
          <ul className="findings-list">
            {recs.map((f, i) => <Finding key={i} f={f} />)}
          </ul>
        ) : (
          <p className="muted">No issues found. 🎉</p>
        )}
      </div>
    </section>
  );
}
