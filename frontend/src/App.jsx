import { useState } from "react";
import TopBar from "./components/TopBar.jsx";
import Dashboard from "./components/Dashboard.jsx";
import Workspace from "./components/Workspace.jsx";
import "./styles.css";

const SAMPLE = [
  {
    id: "scout-demo",
    name: "Scout",
    source: "data/sample_repo",
    inputType: "repo",
    score: null,
    verdict: null,
    language: "python",
    findingsCount: 0,
    lastReport: null,
    chatHistory: [],
    prs: [],
    updatedAt: new Date().toISOString(),
  },
];

function loadCodebases() {
  try {
    const saved = JSON.parse(localStorage.getItem("scout_codebases") || "null");
    return Array.isArray(saved) && saved.length ? saved : SAMPLE;
  } catch {
    return SAMPLE;
  }
}

function persist(cbs) {
  localStorage.setItem("scout_codebases", JSON.stringify(cbs));
}

export default function App() {
  const [screen, setScreen] = useState("dash");
  const [codebases, setCodebases] = useState(loadCodebases);
  const [activeIdx, setActiveIdx] = useState(null);

  function openCodebase(idx) {
    setActiveIdx(idx);
    setScreen("ws");
  }

  function newCodebase() {
    const cb = {
      id: Date.now().toString(),
      name: "New codebase",
      source: "",
      inputType: "repo",
      score: null,
      verdict: null,
      language: "",
      findingsCount: 0,
      lastReport: null,
      chatHistory: [],
      prs: [],
      updatedAt: new Date().toISOString(),
    };
    setCodebases((prev) => {
      const next = [...prev, cb];
      persist(next);
      return next;
    });
    setActiveIdx(codebases.length);
    setScreen("ws");
  }

  function updateCodebase(idx, patch) {
    setCodebases((prev) => {
      const next = prev.map((cb, i) =>
        i === idx ? { ...cb, ...patch, updatedAt: new Date().toISOString() } : cb
      );
      persist(next);
      return next;
    });
  }

  function navTo(s) {
    setScreen(s);
    if (s === "ws" && activeIdx === null && codebases.length > 0) {
      setActiveIdx(0);
    }
  }

  return (
    <>
      <TopBar screen={screen} onNav={navTo} />
      {screen === "dash" && (
        <Dashboard codebases={codebases} onOpen={openCodebase} onNew={newCodebase} />
      )}
      {screen === "ws" && activeIdx !== null && (
        <Workspace
          key={activeIdx}
          codebase={codebases[activeIdx]}
          onBack={() => setScreen("dash")}
          onUpdate={(patch) => updateCodebase(activeIdx, patch)}
        />
      )}
    </>
  );
}
