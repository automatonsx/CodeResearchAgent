function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function verdictClass(v) {
  return { approve: "v-approve", discuss: "v-discuss", request_changes: "v-changes" }[v] || "";
}

function CodebaseCard({ cb, onClick }) {
  const chips = [
    cb.language && cb.language.split(",")[0].trim(),
    cb.findingsCount ? `${cb.findingsCount} findings` : null,
    cb.updatedAt ? `updated ${timeAgo(cb.updatedAt)}` : null,
  ].filter(Boolean);

  return (
    <div className="card" onClick={onClick}>
      <div className="name">🛡️ {cb.name}</div>
      {cb.source && <div className="repo mono">{cb.source}</div>}
      {cb.score != null ? (
        <div className="row" style={{ margin: "10px 0 0" }}>
          <span className="score">{Number(cb.score).toFixed(1)}/10</span>
          {cb.verdict && (
            <span className={`verdict ${verdictClass(cb.verdict)}`}>
              {cb.verdict.replace("_", " ")}
            </span>
          )}
        </div>
      ) : (
        <p style={{ color: "var(--muted)", fontSize: 13, margin: "10px 0 0" }}>
          Not reviewed yet
        </p>
      )}
      <div className="meta">
        {chips.map((c, i) => <span key={i} className="chip">{c}</span>)}
      </div>
    </div>
  );
}

export default function Dashboard({ codebases, onOpen, onNew }) {
  return (
    <div className="wrap">
      <div className="row">
        <div>
          <h1>Your codebases</h1>
          <p className="sub">
            Each box is a codebase. Open one to review it, research improvements, or see PR reviews.
          </p>
        </div>
        <div className="spacer" />
        <button className="btn primary" onClick={onNew}>＋ New codebase</button>
      </div>

      <div className="grid">
        {codebases.map((cb, i) => (
          <CodebaseCard key={cb.id || i} cb={cb} onClick={() => onOpen(i)} />
        ))}
        <div className="card add" onClick={onNew}>
          <div>＋<br />Add a codebase</div>
        </div>
      </div>
    </div>
  );
}
