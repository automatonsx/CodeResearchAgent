"""Web research tool — fetch recent papers, articles and codebases for architectural review.

Sources (all best-effort; failures are silently skipped):
  1. Tavily Search  — requires TAVILY_API_KEY env var; best quality (web + research)
  2. Semantic Scholar — free, no key; academic CS papers
  3. ArXiv           — free, no key; CS preprints

Set WEB_RESEARCH_ENABLED=false to disable all searches.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_TIMEOUT = 6  # seconds per outbound request
_NS_ATOM = {"atom": "http://www.w3.org/2005/Atom"}

_HEADERS = {
    "User-Agent": (
        "ScoutArchReviewer/1.0 (research-aware code-review tool; "
        "contact: scout-bot@example.com)"
    )
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, *, extra_headers: dict | None = None) -> bytes:
    headers = {**_HEADERS, **(extra_headers or {})}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read()


def _http_post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    headers = {**_HEADERS, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Source-specific search implementations
# ---------------------------------------------------------------------------

def _search_tavily(query: str, n: int) -> list[dict]:
    """Tavily comprehensive web + research search (requires TAVILY_API_KEY)."""
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        data = _http_post_json("https://api.tavily.com/search", {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": n,
            "include_answer": False,
        })
        results = []
        for item in (data.get("results") or [])[:n]:
            url = item.get("url", "")
            title = item.get("title", "")
            snippet = (item.get("content") or "")[:350]
            if url and title:
                results.append({"title": title, "url": url, "snippet": snippet, "source_type": "web"})
        return results
    except Exception:
        return []


def _search_semantic_scholar(query: str, n: int) -> list[dict]:
    """Semantic Scholar academic paper search (free, no key required)."""
    try:
        q = urllib.parse.quote(query)
        url = (
            f"https://api.semanticscholar.org/graph/v1/paper/search"
            f"?query={q}&fields=title,abstract,year,externalIds,url&limit={n}"
        )
        data = json.loads(_http_get(url))
        results = []
        for p in (data.get("data") or [])[:n]:
            title = p.get("title", "")
            if not title:
                continue
            paper_url = p.get("url") or ""
            doi = (p.get("externalIds") or {}).get("DOI")
            if doi:
                paper_url = f"https://doi.org/{doi}"
            elif not paper_url:
                pid = p.get("paperId", "")
                paper_url = f"https://www.semanticscholar.org/paper/{pid}" if pid else ""
            year = p.get("year")
            abstract = (p.get("abstract") or "")[:350]
            snippet = f"({year}) {abstract}" if year else abstract
            results.append({"title": title, "url": paper_url, "snippet": snippet, "source_type": "paper"})
        return results
    except Exception:
        return []


def _search_arxiv(query: str, n: int) -> list[dict]:
    """ArXiv preprint search limited to CS categories (free, no key required)."""
    try:
        q = urllib.parse.quote(f"cat:cs.* AND all:{query}")
        url = (
            f"https://export.arxiv.org/api/query"
            f"?search_query={q}&start=0&max_results={n}"
            f"&sortBy=relevance&sortOrder=descending"
        )
        root = ET.fromstring(_http_get(url))
        results = []
        for entry in root.findall("atom:entry", _NS_ATOM)[:n]:
            title = (entry.findtext("atom:title", namespaces=_NS_ATOM) or "").strip()
            if not title:
                continue
            summary = (entry.findtext("atom:summary", namespaces=_NS_ATOM) or "").strip()[:350]
            link = ""
            for lnk in entry.findall("atom:link", _NS_ATOM):
                if lnk.get("type") == "text/html":
                    link = lnk.get("href", "")
                    break
            if not link:
                raw_id = entry.findtext("atom:id", namespaces=_NS_ATOM) or ""
                link = raw_id.replace("http://arxiv.org/abs/", "https://arxiv.org/abs/")
            results.append({"title": title, "url": link, "snippet": summary, "source_type": "preprint"})
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def research_for_architecture(queries: list[str], max_per_query: int = 3) -> list[dict]:
    """Run web research for a list of architectural queries.

    Returns a deduplicated list of result dicts:
      {title, url, snippet, source_type, query}

    source_type values: "web" (Tavily), "paper" (Semantic Scholar), "preprint" (ArXiv).
    Results are returned as soon as each query finishes (parallel execution).
    """
    if os.environ.get("WEB_RESEARCH_ENABLED", "true").lower() in ("false", "0", "no"):
        return []

    queries = [q for q in queries if q and q.strip()][:5]  # cap at 5 queries
    if not queries:
        return []

    def _search_one(query: str) -> list[dict]:
        # Tavily is preferred when available — it covers both web and academic
        hits = _search_tavily(query, max_per_query)
        if not hits:
            # Fall back to the two free academic sources in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                f_ss = pool.submit(_search_semantic_scholar, query, 2)
                f_ax = pool.submit(_search_arxiv, query, 2)
                hits = (f_ss.result() or []) + (f_ax.result() or [])
        return [{**h, "query": query} for h in hits]

    seen_urls: set[str] = set()
    all_results: list[dict] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(queries)) as executor:
        futures = {executor.submit(_search_one, q): q for q in queries}
        for future in concurrent.futures.as_completed(futures):
            try:
                for hit in (future.result() or []):
                    url = hit.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(hit)
            except Exception:
                pass

    return all_results


# ---------------------------------------------------------------------------
# Query generation helpers
# ---------------------------------------------------------------------------

# Signals in source code that indicate a particular framework
_FRAMEWORK_SIGNALS: dict[str, list[str]] = {
    "FastAPI": ["from fastapi", "FastAPI()", "APIRouter", "@app.get", "@app.post"],
    "Flask": ["from flask", "Flask(__name__", "@app.route"],
    "Django": ["from django", "django.db.models", "INSTALLED_APPS"],
    "SQLAlchemy": ["from sqlalchemy", "declarative_base", "sessionmaker"],
    "LangChain / LangGraph": ["from langchain", "from langgraph", "StateGraph", "LLMChain"],
    "React": ["import React", "from 'react'", "useState(", "useEffect("],
    "Next.js": ["from 'next/", "getServerSideProps", "getStaticProps"],
    "Express": ["require('express')", "from 'express'", "app.listen("],
    "Spring Boot": ["@SpringBootApplication", "@RestController", "SpringApplication"],
    "Celery": ["from celery", "Celery(", "@celery.task"],
    "Kafka": ["KafkaConsumer", "KafkaProducer", "confluent_kafka"],
}


def research_for_security(language: str, frameworks: list[str], issue_types: list[str]) -> list[dict]:
    """Search for security guidance relevant to the detected stack and issues."""
    queries: list[str] = []
    fw = frameworks[0] if frameworks else ""
    if fw:
        queries.append(f"{fw} security vulnerabilities OWASP CVE best practices 2024 2025")
    if language:
        queries.append(f"{language} secure coding practices OWASP injection vulnerabilities")
    if issue_types:
        types_str = " ".join(issue_types[:3])
        queries.append(f"prevent {types_str} security code review best practices")
    return research_for_architecture(queries[:3])


def research_for_tests(language: str, frameworks: list[str]) -> list[dict]:
    """Search for testing best practices for the detected language and framework stack."""
    queries: list[str] = []
    fw = frameworks[0] if frameworks else ""
    if fw:
        queries.append(f"{fw} unit testing best practices test patterns pytest 2024")
        queries.append(f"{fw} integration testing test coverage strategy guide")
    if language:
        queries.append(f"{language} TDD test driven development unit testing design patterns research")
    if not queries:
        queries.append("software unit testing best practices test coverage strategies 2024")
    return research_for_architecture(queries[:3])


def detect_frameworks(file_contents: list[dict]) -> list[str]:
    """Detect frameworks from a list of {file, content} dicts."""
    combined = "\n".join(fc.get("content", "") for fc in file_contents[:8])
    return [fw for fw, sigs in _FRAMEWORK_SIGNALS.items() if any(s in combined for s in sigs)]


def build_architecture_queries(context: dict, file_contents: list[dict]) -> list[str]:
    """Generate targeted web-research queries from review context and file content.

    Args:
        context: ReviewState context dict (language, entry_points, etc.)
        file_contents: List of {file, content} dicts from the reviewed files.

    Returns:
        Up to 3 search query strings.
    """
    language = (context.get("language") or "").strip()

    # Detect frameworks from source
    detected: list[str] = []
    combined_src = "\n".join(fc.get("content", "") for fc in file_contents[:8])
    for fw, signals in _FRAMEWORK_SIGNALS.items():
        if any(sig in combined_src for sig in signals):
            detected.append(fw)

    queries: list[str] = []

    if detected:
        primary_fw = detected[0]
        queries.append(
            f"{primary_fw} architecture best practices design patterns 2024"
        )
        if len(detected) > 1:
            queries.append(
                f"{' '.join(detected[:2])} software design scalability maintainability"
            )
        elif language:
            queries.append(
                f"{language} {primary_fw} clean architecture patterns research paper"
            )
    elif language:
        queries.append(f"{language} software architecture design patterns best practices 2024")
        queries.append(f"{language} clean architecture maintainability research")

    queries.append("software architecture anti-patterns code review design improvements")

    return queries[:3]
