import { useState, useRef, useEffect } from "react";
import { researchChat, reviewStream } from "../api.js";
import GlassBox from "./GlassBox.jsx";

const SUGGESTIONS = [
  "What patterns does this repo follow?",
  "Where are we missing tests?",
  "Suggest 3 architectural improvements",
  "How can we improve error handling?",
];

// Parse inline markdown: **bold** and `code`
function parseInline(text) {
  // Split on **bold** and `code` markers
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <strong key={i}>{p.slice(2, -2)}</strong>;
    }
    if (p.startsWith("`") && p.endsWith("`")) {
      return (
        <code key={i} style={{
          background: "rgba(255,255,255,0.1)",
          borderRadius: 3,
          padding: "1px 5px",
          fontFamily: "monospace",
          fontSize: "0.88em",
        }}>
          {p.slice(1, -1)}
        </code>
      );
    }
    return p;
  });
}

function MarkdownBody({ text }) {
  if (!text) return null;
  const lines = text.split("\n");
  const out = [];
  let bullets = [];
  let ordered = [];

  const flushBullets = () => {
    if (!bullets.length) return;
    out.push(
      <ul key={`ul-${out.length}`} style={{ margin: "4px 0 8px", paddingLeft: 20 }}>
        {bullets.map((b, i) => <li key={i} style={{ marginBottom: 4 }}>{parseInline(b)}</li>)}
      </ul>
    );
    bullets = [];
  };

  const flushOrdered = () => {
    if (!ordered.length) return;
    out.push(
      <ol key={`ol-${out.length}`} style={{ margin: "4px 0 8px", paddingLeft: 22 }}>
        {ordered.map((o, i) => <li key={i} style={{ marginBottom: 4 }}>{parseInline(o)}</li>)}
      </ol>
    );
    ordered = [];
  };

  lines.forEach((raw, i) => {
    const line = raw.trim();

    if (!line) {
      flushBullets();
      flushOrdered();
      return;
    }

    // Numbered list: "1. " or "1) "
    const numMatch = line.match(/^\d+[.)]\s+(.+)/);
    if (numMatch) {
      flushBullets();
      ordered.push(numMatch[1]);
      return;
    }

    // Bullet: "- " or "• "
    if (line.startsWith("- ") || line.startsWith("• ")) {
      flushOrdered();
      bullets.push(line.replace(/^[-•]\s+/, ""));
      return;
    }

    flushBullets();
    flushOrdered();

    // ### or ## heading
    const h3 = line.match(/^###\s+(.+)/);
    const h2 = line.match(/^##\s+(.+)/);
    if (h3 || h2) {
      out.push(
        <p key={i} style={{ fontWeight: 700, marginTop: 14, marginBottom: 3, fontSize: "0.95em", opacity: 0.95 }}>
          {parseInline((h3 || h2)[1])}
        </p>
      );
      return;
    }

    // KB / citation line: starts with KB: or emoji citation markers
    const citeMatch = line.match(/^(KB:|📚|🧠|🟢)\s*(.*)/);
    if (citeMatch) {
      out.push(
        <div key={i} style={{
          marginTop: 10,
          padding: "5px 10px",
          borderLeft: "2px solid #4ade80",
          color: "#4ade80",
          fontSize: "0.82em",
          fontFamily: "monospace",
          opacity: 0.85,
        }}>
          🧠 {citeMatch[1] === "KB:" ? "KB: " : ""}{citeMatch[2]}
        </div>
      );
      return;
    }

    // Standalone **Heading**: line
    const headingMatch = line.match(/^\*\*(.+?)\*\*[:\s]*$/);
    if (headingMatch) {
      out.push(
        <p key={i} style={{ fontWeight: 700, marginTop: 12, marginBottom: 2, fontSize: "0.93em" }}>
          {headingMatch[1]}
        </p>
      );
      return;
    }

    // Regular paragraph
    out.push(<p key={i} style={{ margin: "4px 0", lineHeight: 1.6 }}>{parseInline(line)}</p>);
  });

  flushBullets();
  flushOrdered();
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
      // Always render bot answers as markdown — the LLM returns formatted text
      const botMsg = { role: "bot", content: data.answer, markdown: true };
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

    const userMsg     = { role: "user", content: "🔬 Research entire codebase" };
    const pipelineMsg = { role: "bot", type: "pipeline", trace: [], running: true };

    setMessages(prev => [...prev, userMsg, pipelineMsg]);

    let pipelineIdx = -1;

    try {
      const final = await reviewStream(
        codebase.source,
        codebase.inputType || "repo",
        (update) => {
          setMessages(prev => {
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
