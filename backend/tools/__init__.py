"""Ground-truth tool runners — the LLM proposes, these verify.

ruff (quality + bandit security rules), AST checks, optional semgrep, and a
unified-diff parser for PR mode.
"""

from .ruff_runner import run_ruff
from .semgrep_runner import run_semgrep, semgrep_available
from .ast_utils import ast_findings, python_skeleton
from .code_skeleton import code_skeleton
from .dep_audit import run_dependency_audit, run_pip_audit, run_npm_audit
from .diff_utils import parse_diff, fetch_pr_diff
from .git_utils import clone_repo, parse_repo_url
from .generic_scan import generic_scan
from .eslint_runner import run_eslint, eslint_available

__all__ = [
    "run_ruff",
    "run_semgrep",
    "semgrep_available",
    "ast_findings",
    "python_skeleton",
    "code_skeleton",
    "run_dependency_audit",
    "run_pip_audit",
    "run_npm_audit",
    "parse_diff",
    "fetch_pr_diff",
    "clone_repo",
    "parse_repo_url",
    "generic_scan",
    "run_eslint",
    "eslint_available",
]
