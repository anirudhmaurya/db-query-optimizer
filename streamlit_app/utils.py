"""
streamlit_app/utils.py
Backend utility helpers for the Multi-Agent SQL Query Optimizer Streamlit app.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

DB_PATH = WORKSPACE_ROOT / "sandbox.db"
TEST_CASES_PATH = WORKSPACE_ROOT / "test_cases.json"
EVALUATION_RESULTS_PATH = WORKSPACE_ROOT / "evaluation_results.json"
TRAJECTORIES_PATH = WORKSPACE_ROOT / "trajectories.json"
TRAJECTORIES_DIR = WORKSPACE_ROOT / "trajectories"
BASELINE_RESULTS_PATH = WORKSPACE_ROOT / "baseline_results.json"
AGENT_RESULTS_PATH = WORKSPACE_ROOT / "agent_results.json"
ENV_PATH = WORKSPACE_ROOT / ".env"


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_evaluation_results() -> Optional[Dict[str, Any]]:
    if EVALUATION_RESULTS_PATH.exists():
        try:
            with open(EVALUATION_RESULTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def load_trajectories() -> List[Dict[str, Any]]:
    if TRAJECTORIES_PATH.exists():
        try:
            with open(TRAJECTORIES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def load_test_cases() -> List[Dict[str, Any]]:
    if TEST_CASES_PATH.exists():
        with open(TEST_CASES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("test_cases", [])
    return []


def load_agent_results() -> Optional[Dict[str, Any]]:
    if AGENT_RESULTS_PATH.exists():
        try:
            with open(AGENT_RESULTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def load_baseline_results() -> Optional[Dict[str, Any]]:
    if BASELINE_RESULTS_PATH.exists():
        try:
            with open(BASELINE_RESULTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# LLM provider helpers
# ---------------------------------------------------------------------------

PROVIDER_MODELS: Dict[str, List[str]] = {
    "mock": ["mock-orchestrator"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-3.6-flash"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
}


def get_env_api_key(provider: str) -> Optional[str]:
    try:
        from src.baseline import load_env_file
        load_env_file(ENV_PATH)
    except Exception:
        pass
    mapping = {
        "deepseek": "DEEPSEEK_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_var = mapping.get(provider)
    if env_var:
        return os.environ.get(env_var)
    return None


# ---------------------------------------------------------------------------
# Single-query optimization
# ---------------------------------------------------------------------------

def run_single_query_optimization(
    query: str,
    provider: str = "mock",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_retries: int = 3,
    timeout_sec: float = 10.0,
    on_stage: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    from src.agent_optimizer import OptimizerOrchestrator
    from src.tools import DatabaseSandbox

    if on_stage:
        on_stage("init", f"Initializing optimizer — provider={provider}, model={model or 'default'}")

    orchestrator = OptimizerOrchestrator(
        provider=provider,
        model=model,
        api_key=api_key,
        max_retries=max_retries,
        timeout_sec=timeout_sec,
    )

    schema = DatabaseSandbox.get_schema(DB_PATH)

    test_case = {
        "id": "CUSTOM",
        "name": "custom_query",
        "anti_pattern": "User-submitted query",
        "query": query,
    }

    scratch_dir = WORKSPACE_ROOT / "trajectories" / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    if on_stage:
        on_stage("profiler", "🔍 ProfilerAgent: Analyzing EXPLAIN QUERY PLAN...")

    result = orchestrator.optimize_query(
        test_case=test_case,
        schema=schema,
        base_db_path=DB_PATH,
        scratch_dir=scratch_dir,
    )

    if scratch_dir.exists():
        shutil.rmtree(scratch_dir, ignore_errors=True)

    return result


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_benchmark(
    provider: str = "mock",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    max_retries: int = 3,
    timeout_sec: float = 10.0,
) -> Dict[str, Any]:
    from src.evaluate import run_evaluation

    result = run_evaluation(
        db_path=DB_PATH,
        test_cases_path=TEST_CASES_PATH,
        evaluation_results_path=EVALUATION_RESULTS_PATH,
        trajectories_path=TRAJECTORIES_PATH,
        trajectories_dir=TRAJECTORIES_DIR,
        baseline_results_path=BASELINE_RESULTS_PATH,
        agent_results_path=AGENT_RESULTS_PATH,
        provider=provider,
        model=model,
        api_key=api_key,
        timeout_sec=timeout_sec,
        max_retries=max_retries,
        quiet=True,
    )

    return result


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def format_ms(ms: Optional[float]) -> str:
    if ms is None:
        return "N/A"
    return f"{ms:.2f} ms"


def speedup_badge_color(speedup: Optional[float]) -> str:
    if speedup is None:
        return "#6b7280"
    if speedup >= 5.0:
        return "#10b981"
    if speedup >= 2.0:
        return "#3b82f6"
    if speedup >= 1.0:
        return "#f59e0b"
    return "#ef4444"
