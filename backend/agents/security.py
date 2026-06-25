"""Security Agent — secrets, injection, unsafe calls + web-research citations.

Ground truth: ruff's bandit (S) rules + semgrep when available. The LLM structures
these into scored security findings. Web research enriches each finding's research_basis
with current OWASP guidance and security advisories for the detected stack.
"""

from __future__ import annotations

from ..state import ReviewState
from ..tools import run_ruff, run_semgrep, generic_scan
from ..tools.web_research import research_for_security, detect_frameworks
from ._structure import structure_findings

# Map raw issue codes / keywords to OWASP-style issue type labels for query building
_ISSUE_KEYWORDS = {
    "S608": "SQL injection", "S602": "command injection", "S307": "code injection eval",
    "S101": "assert misuse", "S105": "hardcoded password", "S106": "hardcoded password",
    "S324": "weak hash md5 sha1", "S501": "TLS verification disabled",
    "SCAN-SECRET": "hardcoded secret credential", "SCAN-EVAL": "eval exec injection",
    "SCAN-INNERHTML": "XSS innerHTML", "SCAN-HASH": "weak cryptographic hash",
}


def _issue_types_from_raw(raw: list[dict]) -> list[str]:
    seen: list[str] = []
    for r in raw:
        code = r.get("code", "")
        label = _ISSUE_KEYWORDS.get(code)
        if not label:
            # Partial match on prefix
            for k, v in _ISSUE_KEYWORDS.items():
                if code.startswith(k[:4]):
                    label = v
                    break
        if label and label not in seen:
            seen.append(label)
    return seen[:4]


def security_node(state: ReviewState) -> ReviewState:
    """Security review: ruff S (Python) + semgrep + language-agnostic secret/pattern scan,
    enriched with current web research on the detected stack's known vulnerabilities."""
    ctx = state.get("context", {})
    py_files = ctx.get("py_files", [])
    all_files = ctx.get("files", [])
    if not all_files and not py_files:
        return {}

    raw = run_ruff(py_files, select="S") if py_files else []
    raw += run_semgrep(ctx.get("review_path") or "")
    raw += generic_scan(all_files)
    for r in raw:
        r["type"] = "security"
        r["category"] = "security"

    findings = structure_findings("security", "security", raw, state.get("critique"))

    # ------------------------------------------------------------------ #
    # Web research: fetch security guidance for this stack + issue types  #
    # ------------------------------------------------------------------ #
    language = ctx.get("language", "")
    # Reuse file content already loaded by architecture agent if available,
    # else infer frameworks from raw tool codes
    all_contents = state.get("context", {}).get("_file_contents", [])
    frameworks = detect_frameworks(all_contents) if all_contents else []
    issue_types = _issue_types_from_raw(raw)

    web_results = research_for_security(language, frameworks, issue_types)

    # Attach web citations to findings that don't already have a research_basis
    if web_results:
        for f in findings:
            if f.get("research_basis"):
                continue
            # Match by issue type keyword
            fissue = (f.get("issue") or "").lower() + " " + (f.get("tool_evidence") or "").lower()
            for wr in web_results[:3]:
                snippet = (wr.get("snippet") or "").lower() + wr.get("title", "").lower()
                if any(kw in snippet or kw in fissue for kw in ("injection", "secret", "owasp", "security", "hash", "eval")):
                    f.setdefault("research_basis", [])
                    citation = f"{wr['title']} — {wr['url']}"
                    if citation not in f["research_basis"]:
                        f["research_basis"].append(citation)
                    break

    # Merge web_research into state (architecture node may have added some already)
    seen_urls = {r["url"] for r in state.get("web_research", []) if r.get("url")}
    merged_web = list(state.get("web_research", [])) + [
        r for r in web_results if r.get("url") and r["url"] not in seen_urls
    ]

    other_tools = [t for t in state.get("tool_findings", []) if t.get("category") != "security"]
    other_finds = [f for f in state.get("findings", []) if f.get("category") != "security"]
    return {
        "tool_findings": other_tools + raw,
        "findings": other_finds + findings,
        "web_research": merged_web,
    }
