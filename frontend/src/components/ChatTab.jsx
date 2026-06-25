import { useState, useRef, useEffect } from "react";
import { researchChat, reviewStream } from "../api.js";
import GlassBox from "./GlassBox.jsx";

const SUGGESTIONS = [
  "What patterns does this repo follow?",
  "Where are we missing tests?",
  "Suggest 3 architectural improvements",
  "How can we improve error handling?",
];

function parseInline(text) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((p, i) => (i % 2 === 1 ? <strong key={i}>{p}</strong> : p));
}

function MarkdownBody({ text }) {
  if (!text) return null;
  const lines = text.split("\n");
  const out = [];
  let bullets = [];

  const flushBullets = () => {
    if (!bullets.length) return;
    out.push(
      <ul key={`ul-${out.length}`} style={{ margin: "4px 0 8px", paddingLeft: 20 }}>
        {bullets.map((b, i) => (
          <li key={i} style={{ marginBottom: 3 }}>{parseInline(b)}</li>
        ))}
      </ul>
    );
    bullets = [];
  };

  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (!line) { flushBullets(); return; }

    if (line.startsWith("- ")) {
      bullets.push(line.slice(2));
      return;
    }
    flushBullets();

    // ### or ## heading
    const h3 = line.match(/^###\s+(.+)/);
    const h2 = line.match(/^##\s+(.+)/);
    if (h3 || h2) {
      out.push(
        <p key={i} style={{ fontWeight: 700, marginTop: 12, marginBottom: 2, fontSize: "0.93em", opacity: 0.9 }}>
          {parseInline((h3 || h2)[1])}
        </p>
      );
      return;
    }

    // Standalone **heading** line
    const headingMatch = line.match(/^\*\*(.+)\*\*[:\s]*$/);
    if (headingMatch) {
      out.push(
        <p key={i} style={{ fontWeight: 700, marginTop: 12, marginBottom: 2, fontSize: "0.93em" }}>
          {headingMatch[1]}
        </p>
      );
    } else {
      out.push(<p key={i} style={{ margin: "3px 0" }}>{parseInline(line)}</p>);
    }
  });
  flushBullets();
  return <>{out}</>;
}

function formatReport(report) {
  if (!report) return "";
  const lines = [];
  const stats = report.stats || {};

  lines.push("**Overview**");
  const ov = [];
  if (stats.language) ov.push(`Language: ${stats.language}`);
  if (typeof stats.reviewed === "number") ov.push(`Files reviewed: ${stats.reviewed}`);
  if (report.score != null) ov.push(`Score: ${Number(report.score).toFixed(1)}/10`);
  if (report.verdict) ov.push(`Verdict: ${report.verdict.replace("_", " ")}`);
  lines.push(ov.join(" · "));
  lines.push("");

  if (report.summary) {
    lines.push("**Summary**");
    lines.push(report.summary);
    lines.push("");
  }

  const recs = report.recommendations || [];
  const bySev = { critical: [], high: [], medium: [], low: [] };
  recs.forEach(r => { (bySev[r.severity] || bySev.low).push(r); });

  const section = (label, items, max = 99) => {
    if (!items.length) return;
    lines.push(`**${label}**`);
    items.slice(0, max).forEach(r => {
      const loc = r.file ? ` \`${r.file.split(/[\\/]/).pop()}${r.line ? ":" + r.line : ""}\`` : "";
      lines.push(`- ${loc} ${r.issue || ""}`.trim());
      if (r.suggestion) lines.push(`  → ${r.suggestion}`);
    });
    if (items.length > max) lines.push(`- …and ${items.length - max} more`);
    lines.push("");
  };

  section("Critical Issues", bySev.critical);
  section("High Priority", bySev.high);
  section("Medium Priority", bySev.medium, 5);
  section("Low / Style", bySev.low, 3);

  if (stats.verified != null) {
    lines.push("**Critic Pass**");
    lines.push(`- Verified: ${stats.verified}  ·  Dropped: ${stats.dropped}  ·  Re-check loops: ${stats.iterations}`);
    lines.push("");
  }

  return lines.join("\n");
}

export default function ChatTab({ codebase, onUpdate }) {
  const [messages, setMessages]       = useState(codebase.chatHistory || []);
  const [input, setInput]             = useState("");
  const [loading, setLoading]         = useState(false);
  const [researching, setResearching] = useState(false);
  const threadRef = useRef(null);

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);

  async function send(question) {
    const q = question.trim();
    if (!q || loading) return;
    const userMsg = { role: "user", content: q };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const data = await researchChat(q, codebase.source || "");
      const botMsg = { role: "bot", content: data.answer };
      const final = [...next, botMsg];
      setMessages(final);
      onUpdate({ chatHistory: final });
    } catch (err) {
      const errMsg = { role: "bot", content: `Error: ${err.message}` };
      setMessages([...next, errMsg]);
    } finally {
      setLoading(false);
    }
  }

  async function researchAll() {
    if (!codebase.source || researching) return;
    setResearching(true);

    // 1) Push user trigger + a live pipeline message into the thread
    const userMsg    = { role: "user", content: "🔬 Research entire codebase" };
    const pipelineMsg = { role: "bot", type: "pipeline", trace: [], running: true };

    setMessages(prev => {
      const base = [...prev, userMsg, pipelineMsg];
      return base;
    });

    // capture the index AFTER we push (prev.length + 1 = pipelineMsg index)
    let pipelineIdx = -1;

    try {
      const final = await reviewStream(
        codebase.source,
        codebase.inputType || "repo",
        (update) => {
          setMessages(prev => {
            // find pipeline message (running:true) if index not yet known
            if (pipelineIdx === -1) {
              pipelineIdx = prev.findIndex(m => m.type === "pipeline" && m.running);
            }
            if (pipelineIdx === -1) return prev;
            const next = [...prev];
            next[pipelineIdx] = {
              ...next[pipelineIdx],
              trace: [...(next[pipelineIdx].trace || []), update],
            };
            return next;
          });
        }
      );

      if (final) {
        const resultMsg = { role: "bot", content: formatReport(final), markdown: true };
        setMessages(prev => {
          const idx = pipelineIdx !== -1
            ? pipelineIdx
            : prev.findIndex(m => m.type === "pipeline");
          const next = [...prev];
          if (idx !== -1) next[idx] = resultMsg; else next.push(resultMsg);
          // persist only non-pipeline messages
          const persisted = next.filter(m => m.type !== "pipeline");
          onUpdate({
            chatHistory: persisted,
            score: final.score,
            verdict: final.verdict,
            lastReport: final,
          });
          return next;
        });
      }
    } catch (err) {
      const errMsg = { role: "bot", content: `Error: ${err.message}` };
      setMessages(prev => {
        const idx = prev.findIndex(m => m.type === "pipeline");
        const next = [...prev];
        if (idx !== -1) next[idx] = errMsg; else next.push(errMsg);
        return next;
      });
    } finally {
      setResearching(false);
    }
  }

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <p className="sub" style={{ margin: 0, flex: 1 }}>
          Ask anything about <b>this codebase's</b> architecture — answers grounded in
          the knowledge base + the actual code.
        </p>
        <button
          className="btn"
          style={{ whiteSpace: "nowrap", flexShrink: 0 }}
          onClick={researchAll}
          disabled={researching || !codebase.source}
          title={!codebase.source ? "Run a review first to set the codebase source" : "Run full pipeline research"}
        >
          {researching ? "Researching…" : "🔬 Research entire codebase"}
        </button>
      </div>

      <div className="chat">
        <div className="thread" ref={threadRef}>
          {messages.length === 0 && (
            <p style={{ color: "var(--muted)", margin: "auto", textAlign: "center" }}>
              No messages yet. Ask something below or pick a suggestion.
            </p>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="ava">{m.role === "user" ? "🧑" : "🛡️"}</div>

              {m.type === "pipeline" ? (
                // GlassBox lives INSIDE the bot bubble in the thread
                <div className="bubble" style={{ padding: 0, background: "transparent", boxShadow: "none", maxWidth: "100%" }}>
                  <GlassBox trace={m.trace} running={m.running} />
                </div>
              ) : (
                <div className="bubble">
                  {m.markdown ? <MarkdownBody text={m.content} /> : m.content}
                  {m.cite && <span className="cite">{m.cite}</span>}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="msg bot">
              <div className="ava">🛡️</div>
              <div className="bubble" style={{ color: "var(--muted)" }}>Thinking…</div>
            </div>
          )}
        </div>

        {messages.length === 0 && (
          <div className="suggap">
            {SUGGESTIONS.map((s) => (
              <span key={s} className="sugg" onClick={() => send(s)}>{s}</span>
            ))}
          </div>
        )}

        <div className="composer">
          <input
            placeholder="Ask about this codebase…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
          />
          <button
            className="btn primary"
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </div>
      </div>
    </>
  );
}
