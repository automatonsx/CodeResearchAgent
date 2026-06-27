"""Azure OpenAI client (via LangChain) + helpers.

Centralizes LLM construction so every agent shares one configured client.
Reads credentials from environment / .env (see ``.env.example``).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import time
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

# Load credentials: local .env first, then ~/.scout/.env as the global fallback.
# ~/.scout/.env is written by `scout setup` and is shared across all repos.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
if not os.environ.get("AZURE_OPENAI_API_KEY"):
    _scout_env = os.environ.get("SCOUT_ENV") or str(pathlib.Path.home() / ".scout" / ".env")
    load_dotenv(_scout_env)


@lru_cache(maxsize=4)
def get_llm(temperature: float = 0.2) -> AzureChatOpenAI:
    """Return a cached Azure OpenAI chat client.

    Required env vars:
      AZURE_OPENAI_API_KEY
      AZURE_OPENAI_ENDPOINT
      AZURE_OPENAI_DEPLOYMENT  (deployment name; falls back to AZURE_OPENAI_MODEL or "gpt-4o")
      AZURE_OPENAI_API_VERSION
    """
    deployment = (
        os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        or os.environ.get("AZURE_OPENAI_MODEL")
        or "gpt-4o"
    )
    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_deployment=deployment,
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        temperature=temperature,
    )


def load_prompt(name: str) -> str:
    """Load a prompt template.

    Checks backend/prompts/ first (correct path when pip-installed), then falls
    back to the root prompts/ directory (correct path when running from source).
    """
    _pkg_prompts = pathlib.Path(__file__).resolve().parent / "prompts"
    _root_prompts = _ROOT / "prompts"
    for directory in (_pkg_prompts, _root_prompts):
        candidate = directory / f"{name}.md"
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"Prompt '{name}.md' not found in {_pkg_prompts} or {_root_prompts}"
    )


def _extract_json(text: str):
    """Best-effort JSON extraction from an LLM reply (handles ```json fences)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fall back to the first {...} or [...] block.
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate_limit" in msg or "too_many_requests" in msg


def _invoke_with_retry(messages, temperature: float, max_retries: int = 4):
    """Invoke the LLM with exponential back-off on 429 rate-limit errors.

    Waits 15 s → 30 s → 60 s → 120 s before each retry, then re-raises.
    """
    llm = get_llm(temperature)
    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            if _is_rate_limit(exc) and attempt < max_retries - 1:
                wait = 15 * (2 ** attempt)   # 15, 30, 60, 120 seconds
                print(
                    f"  [Scout] Rate limit hit — waiting {wait}s before retry "
                    f"({attempt + 1}/{max_retries - 1}) …",
                    flush=True,
                )
                time.sleep(wait)
            else:
                raise


def chat_json(system: str, user: str, temperature: float = 0.2):
    """Call the LLM and parse its reply as JSON. Retries on 429 rate-limit errors."""
    resp = _invoke_with_retry(
        [SystemMessage(content=system), HumanMessage(content=user)],
        temperature,
    )
    return _extract_json(resp.content)


def chat_text(system: str, user: str, temperature: float = 0.3) -> str:
    """Call the LLM and return the raw text reply. Retries on 429 rate-limit errors."""
    resp = _invoke_with_retry(
        [SystemMessage(content=system), HumanMessage(content=user)],
        temperature,
    )
    return resp.content.strip()
