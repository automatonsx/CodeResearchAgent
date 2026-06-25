import { useState } from "react";
import ReviewTab from "./ReviewTab.jsx";
import ChatTab from "./ChatTab.jsx";
import PrTab from "./PrTab.jsx";

const TABS = [
  { id: "review",   label: "🔍 Review codebase" },
  { id: "research", label: "🧠 Research & improvements" },
  { id: "pr",       label: "🔀 PR reviews" },
];

function verdictClass(v) {
  return { approve: "v-approve", discuss: "v-discuss", request_changes: "v-changes" }[v] || "";
}

export default function Workspace({ codebase, onBack, onUpdate }) {
  const [activeTab, setActiveTab] = useState("review");

  return (
    <div className="wrap">
      <div className="crumb" onClick={onBack}>← Codebases</div>

      <div className="ws-head">
        <h1 style={{ margin: 0 }}>🛡️ {codebase.name}</h1>
        {codebase.source && <span className="chip mono">{codebase.source}</span>}
        <div className="spacer" />
        {codebase.score != null && (
          <>
            <span className="score">{Number(codebase.score).toFixed(1)}/10</span>
            <span className={`verdict ${verdictClass(codebase.verdict)}`}>
              {codebase.verdict?.replace("_", " ")}
            </span>
          </>
        )}
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <div
            key={t.id}
            className={`tab ${activeTab === t.id ? "active" : ""}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </div>
        ))}
      </div>

      {activeTab === "review"   && <ReviewTab codebase={codebase} onUpdate={onUpdate} />}
      {activeTab === "research" && <ChatTab   codebase={codebase} onUpdate={onUpdate} />}
      {activeTab === "pr"       && <PrTab     codebase={codebase} onUpdate={onUpdate} />}
    </div>
  );
}
