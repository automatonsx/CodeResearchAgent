// Talks to the FastAPI backend (proxied at /api -> http://localhost:8000).

const BASE = "/api";

// Non-streaming: run the review and get the final report.
export async function review(source, inputType) {
  const res = await fetch(`${BASE}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, input_type: inputType }),
  });
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  const data = await res.json();
  return data.report;
}

// Streaming: yields each per-node state update for the glass-box view.
// onUpdate({node, state}) is called per step; resolves with the final report.
export async function reviewStream(source, inputType, onUpdate) {
  const res = await fetch(`${BASE}/review/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, input_type: inputType }),
  });
  if (!res.ok || !res.body) throw new Error(`Backend error ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalReport = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() || "";
    for (const evt of events) {
      const line = evt.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") continue;
      try {
        const update = JSON.parse(payload);
        const node = Object.keys(update)[0];
        const state = update[node];
        if (node === "report" && state?.final_report) finalReport = state.final_report;
        onUpdate({ node, state });
      } catch {
        /* ignore malformed chunk */
      }
    }
  }
  return finalReport;
}

// Research chat: ask a question about a codebase, answered by LLM + KB.
export async function researchChat(question, source = "") {
  const res = await fetch(`${BASE}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, source }),
  });
  if (!res.ok) throw new Error(`Backend error ${res.status}`);
  return await res.json();
}
