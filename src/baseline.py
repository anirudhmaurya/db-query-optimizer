"""Zero-shot LLM baseline optimizer and evaluation runner.

This module implements the ZeroShotBaseline class which requests query optimizations
from an LLM using a single, naive zero-shot prompt without EXPLAIN plan analysis,
index awareness, or data verification. It also provides a benchmark runner to evaluate
the validity, accuracy, and execution speedup of the generated queries.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tools import DatabaseExecutionError, DatabaseSandbox

logger = logging.getLogger(__name__)


def load_env_file(env_path: Optional[Union[str, Path]] = None) -> None:
    """Lightweight native .env file loader requiring no third-party dependencies."""
    if env_path is None:
        candidates = [Path(".env"), Path(__file__).resolve().parent.parent / ".env"]
        for candidate in candidates:
            if candidate.exists():
                env_path = candidate
                break
    else:
        env_path = Path(env_path)

    if env_path and Path(env_path).exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception as e:
            logger.warning("Could not read .env file at %s: %s", env_path, e)


# Auto-load .env on module import
load_env_file()


def clean_sql_response(raw_text: str) -> str:
    """Extract clean SQL query string by stripping markdown code blocks, comments, and DDL index statements.

    Args:
        raw_text: Raw text response from the LLM.

    Returns:
        Sanitized executable SQL query string.
    """
    text = raw_text.strip()

    # Match ```sql ... ``` or ``` ... ``` code blocks
    code_block_match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        content = code_block_match.group(1).strip()
    else:
        content = text

    # Remove block comments /* ... */
    content = re.sub(r"/\*[\s\S]*?\*/", "", content)

    # Filter line-by-line comments
    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("--", "#", "//", "Here is", "Optimized", "Note:", "Explanation:", "Below is")):
            continue
        lines.append(line)

    sql_text = "\n".join(lines).strip()

    # If the LLM returned multiple statements (e.g. CREATE INDEX followed by SELECT),
    # extract the primary query (SELECT or WITH)
    statements = [stmt.strip() for stmt in re.split(r";\s*", sql_text) if stmt.strip()]
    query_stmt = None

    # First look for a SELECT or WITH statement
    for stmt in statements:
        upper_stmt = stmt.upper()
        if upper_stmt.startswith("SELECT") or upper_stmt.startswith("WITH"):
            query_stmt = stmt
            break

    if not query_stmt:
        query_stmt = statements[-1] if statements else sql_text

    # Ensure semicolon at end
    if query_stmt and not query_stmt.endswith(";"):
        query_stmt += ";"

    return query_stmt


class LLMProvider:
    """Abstract interface for LLM completion providers."""

    def complete(self, prompt: str) -> str:
        """Send prompt to LLM and return raw response text."""
        raise NotImplementedError


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider (e.g. deepseek-chat, deepseek-reasoner) using native urllib HTTP with backoff."""

    def __init__(self, api_key: str, model: str = "deepseek-chat", max_retries: int = 5, timeout_sec: float = 60.0):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec
        self.endpoint = "https://api.deepseek.com/chat/completions"

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    choices = res_data.get("choices", [])
                    if not choices:
                        raise RuntimeError(f"DeepSeek API returned no choices: {res_data}")
                    content = choices[0].get("message", {}).get("content", "")
                    return content
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"DeepSeek API error ({e.code}): {error_body}")

                # Check for 429 Rate Limit
                if e.code == 429 and attempt < self.max_retries:
                    sleep_time = 2.0 * (2 ** (attempt - 1)) + 1.0
                    print(f"  ⏳ DeepSeek API rate limit hit (429). Pausing {sleep_time:.1f}s before retry {attempt}/{self.max_retries}...")
                    time.sleep(sleep_time)
                    continue

                if e.code in (500, 502, 503, 504) and attempt < self.max_retries:
                    time.sleep(3.0 * attempt)
                    continue
                raise last_error from e
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(2.0 * attempt)
                    continue
                raise RuntimeError(f"Failed to communicate with DeepSeek API after {self.max_retries} attempts: {e}") from e

        raise RuntimeError(f"Failed to communicate with DeepSeek API: {last_error}")


class GeminiProvider(LLMProvider):
    """Google Gemini API provider (e.g. Gemini 3.6 Flash) using native urllib HTTP with intelligent rate-limit backoff."""

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash", max_retries: int = 5, timeout_sec: float = 60.0):
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self.timeout_sec = timeout_sec

    def complete(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0
            }
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json"
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    candidates = res_data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError(f"Gemini API returned no candidates: {res_data}")
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        raise RuntimeError(f"Gemini API returned empty parts: {res_data}")
                    # Brief pacing sleep to avoid bursting free tier RPM
                    time.sleep(1.0)
                    return parts[0].get("text", "")
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"Gemini API error ({e.code}): {error_body}")
                
                # Check for 429 Rate Limit
                if e.code == 429 and attempt < self.max_retries:
                    # Extract suggested retry delay if available in error message
                    delay_match = re.search(r"retry in (\d+(?:\.\d+)?)s", error_body, re.IGNORECASE)
                    if not delay_match:
                        delay_match = re.search(r'"retryDelay":\s*"(\d+)s"', error_body)
                    sleep_time = float(delay_match.group(1)) + 2.0 if delay_match else (20.0 + attempt * 5.0)
                    print(f"  ⏳ Gemini API rate limit hit (429). Pausing {sleep_time:.1f}s before retry {attempt}/{self.max_retries}...")
                    time.sleep(sleep_time)
                    continue

                if e.code in (500, 503, 504) and attempt < self.max_retries:
                    time.sleep(3.0 * attempt)
                    continue
                raise last_error from e
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(3.0 * attempt)
                    continue
                raise RuntimeError(f"Failed to communicate with Gemini API after {self.max_retries} attempts: {e}") from e

        raise RuntimeError(f"Failed to communicate with Gemini API: {last_error}")


class OpenAIProvider(LLMProvider):
    """OpenAI API provider using native urllib HTTP requests."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30.0) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error ({e.code}): {error_body}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with OpenAI API: {e}") from e


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider using native urllib HTTP requests."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://api.anthropic.com/v1/messages"

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30.0) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["content"][0]["text"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic API error ({e.code}): {error_body}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with Anthropic API: {e}") from e


class MockProvider(LLMProvider):
    """Deterministic mock provider for testing and offline evaluation."""

    def __init__(self, model: str = "mock-dba-llm"):
        self.model = model

    def complete(self, prompt: str) -> str:
        # Basic rule-based zero-shot rewrites for standard query optimization patterns
        if "strftime('%Y', created_at) = '2025'" in prompt or "strftime('%y', created_at)" in prompt.lower():
            # SARGable date rewrite
            return (
                "```sql\n"
                "SELECT user_id, event_type, COUNT(*) AS event_count\n"
                "FROM events\n"
                "WHERE created_at >= '2025-01-01 00:00:00' AND created_at < '2026-01-01 00:00:00'\n"
                "GROUP BY user_id, event_type\n"
                "HAVING COUNT(*) >= 1\n"
                "ORDER BY event_count DESC\n"
                "LIMIT 25;\n"
                "```"
            )
        elif "AVG(e2.salary)" in prompt or "AVG(e3.salary)" in prompt:
            # Window function rewrite
            return (
                "```sql\n"
                "WITH dept_stats AS (\n"
                "    SELECT id, name, department_id, salary,\n"
                "           AVG(salary) OVER(PARTITION BY department_id) AS dept_avg_salary\n"
                "    FROM employees\n"
                ")\n"
                "SELECT id, name, department_id, salary, dept_avg_salary\n"
                "FROM dept_stats\n"
                "WHERE salary > (dept_avg_salary * 1.15)\n"
                "ORDER BY salary DESC;\n"
                "```"
            )
        elif "o.id is null" in prompt.lower() or "orders.id is null" in prompt.lower():
            # The NULL Trap
            return (
                "```sql\n"
                "SELECT u.id, u.name, u.region, u.signup_date\n"
                "FROM users u\n"
                "LEFT JOIN orders o ON u.id = o.user_id\n"
                "WHERE o.id IS NULL\n"
                "ORDER BY u.id ASC\n"
                "LIMIT 50;\n"
                "```"
            )
        elif "where not exists (select 1 from orders o where o.user_id = u.id)" in prompt.lower():
            # TC-12: Three-Valued Logic Trap - Zero-shot LLM naively rewrites to NOT IN which fails on NULLs
            return (
                "```sql\n"
                "SELECT u.id, u.name\n"
                "FROM users u\n"
                "WHERE u.id NOT IN (SELECT user_id FROM orders);\n"
                "```"
            )
        elif "max(salary)" in prompt.lower() and "employees" in prompt.lower() and "department_id = e.department_id" in prompt.lower():
            # TC-13: Top-Record Tie Trap - Zero-shot LLM naively uses ROW_NUMBER() which drops ties
            return (
                "```sql\n"
                "WITH ranked AS (\n"
                "    SELECT id, department_id, salary,\n"
                "           ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC) AS rn\n"
                "    FROM employees\n"
                ")\n"
                "SELECT id, department_id, salary\n"
                "FROM ranked\n"
                "WHERE rn = 1;\n"
                "```"
            )
        elif "total_spent" in prompt.lower() and "total_items" in prompt.lower():
            # TC-11: Fan-Out Trap - Zero-shot LLM naively pre-aggregates without multiplying by items count
            return (
                "```sql\n"
                "WITH user_orders AS (\n"
                "    SELECT user_id, SUM(amount) AS total_spent\n"
                "    FROM orders\n"
                "    GROUP BY user_id\n"
                "),\n"
                "user_items AS (\n"
                "    SELECT o.user_id, COUNT(oi.id) AS total_items\n"
                "    FROM orders o\n"
                "    JOIN order_items oi ON o.id = oi.order_id\n"
                "    GROUP BY o.user_id\n"
                ")\n"
                "SELECT u.id, uo.total_spent, ui.total_items\n"
                "FROM users u\n"
                "JOIN user_orders uo ON u.id = uo.user_id\n"
                "JOIN user_items ui ON u.id = ui.user_id;\n"
                "```"
            )
        else:
            # Fallback: extract the query from prompt and return it directly
            query_match = re.search(r"SQL:\s*(.*?)\n\s*Schema:", prompt, re.DOTALL)
            if not query_match:
                query_match = re.search(r"Make this SQL query faster:\s*(.*?)\.\s*Here is the schema:", prompt, re.DOTALL)
            if query_match:
                return query_match.group(1).strip()
            return "SELECT 1;"


class ZeroShotBaseline:
    """Zero-shot LLM optimizer that issues a single ungrounded, unguided optimization prompt."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        client: Optional[LLMProvider] = None
    ) -> None:
        """Initialize the ZeroShotBaseline with an LLM provider or explicit client.

        Args:
            provider: 'deepseek', 'gemini', 'openai', 'anthropic', or 'mock'. If None, auto-detects from env vars.
            model: Name of the model to use (e.g. 'deepseek-chat', 'gemini-3.6-flash', 'gpt-4o', etc.).
            api_key: API key. If None, reads from DEEPSEEK_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY.
            client: Pre-instantiated LLMProvider instance.
        """
        if client is not None:
            self.client = client
            self.model_name = getattr(client, "model", "custom-client")
            return

        # Auto-detect or use specified provider
        deepseek_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        gemini_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        openai_key = api_key or os.environ.get("OPENAI_API_KEY")
        anthropic_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if provider == "deepseek" or (provider is None and deepseek_key):
            if not deepseek_key:
                raise ValueError("DeepSeek API key required. Set DEEPSEEK_API_KEY or pass api_key.")
            selected_model = model or "deepseek-chat"
            self.client = DeepSeekProvider(api_key=deepseek_key, model=selected_model)
            self.model_name = selected_model
        elif provider == "gemini" or (provider is None and gemini_key):
            if not gemini_key:
                raise ValueError("Gemini API key required. Set GEMINI_API_KEY / GOOGLE_API_KEY or pass api_key.")
            selected_model = model or "gemini-3.6-flash"
            self.client = GeminiProvider(api_key=gemini_key, model=selected_model)
            self.model_name = selected_model
        elif provider == "openai" or (provider is None and openai_key):
            if not openai_key:
                raise ValueError("OpenAI API key required. Set OPENAI_API_KEY or pass api_key.")
            selected_model = model or "gpt-4o"
            self.client = OpenAIProvider(api_key=openai_key, model=selected_model)
            self.model_name = selected_model
        elif provider == "anthropic" or (provider is None and anthropic_key):
            if not anthropic_key:
                raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key.")
            selected_model = model or "claude-3-5-sonnet-20241022"
            self.client = AnthropicProvider(api_key=anthropic_key, model=selected_model)
            self.model_name = selected_model
        elif provider == "mock" or (provider is None and not deepseek_key and not gemini_key and not openai_key and not anthropic_key):
            selected_model = model or "mock-dba-llm"
            self.client = MockProvider(model=selected_model)
            self.model_name = selected_model
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def optimize(self, query: str, schema: str) -> Dict[str, Any]:
        """Send a single zero-shot prompt to the LLM to rewrite the query.

        This baseline intentionally does NOT run EXPLAIN, check indexes, or verify data accuracy.

        Args:
            query: The unoptimized SQL query string.
            schema: Database schema DDL.

        Returns:
            Dictionary containing original_query, optimized_sql, raw_response, and model.
        """
        prompt = (
            "You are an SQL assistant. Rewrite the following SQL query to make it run faster on SQLite:\n\n"
            f"SQL: {query}\n"
            f"Schema: {schema}\n\n"
            "Return only the rewritten SQL query without markdown or explanations."
        )

        logger.debug("Dispatching zero-shot DBA prompt for query: %.60s...", query)
        raw_response = self.client.complete(prompt)
        optimized_sql = clean_sql_response(raw_response)

        return {
            "original_query": query,
            "optimized_sql": optimized_sql,
            "raw_response": raw_response,
            "model": self.model_name,
            "prompt": prompt
        }


def run_baseline(
    db_path: Union[str, Path] = "sandbox.db",
    test_cases_path: Union[str, Path] = "test_cases.json",
    output_path: Union[str, Path] = "baseline_results.json",
    baseline_optimizer: Optional[ZeroShotBaseline] = None,
    timeout_sec: float = 10.0,
    quiet: bool = False
) -> Dict[str, Any]:
    """Run baseline zero-shot optimization evaluation on all test cases.

    Args:
        db_path: Path to SQLite sandbox database.
        test_cases_path: Path to test cases JSON.
        output_path: Path to output baseline results JSON.
        baseline_optimizer: ZeroShotBaseline instance (defaults to auto-initialized).
        timeout_sec: Query execution timeout in seconds.
        quiet: If True, suppress console progress output.

    Returns:
        Summary results dictionary.
    """
    log_func = print if not quiet else lambda *args, **kwargs: None

    db_path = Path(db_path)
    test_cases_path = Path(test_cases_path)
    output_path = Path(output_path)

    if not db_path.exists():
        raise FileNotFoundError(f"Sandbox database not found at {db_path}")
    if not test_cases_path.exists():
        raise FileNotFoundError(f"Test cases file not found at {test_cases_path}")

    if baseline_optimizer is None:
        baseline_optimizer = ZeroShotBaseline()

    log_func(f"Extracting schema from {db_path}...")
    schema = DatabaseSandbox.get_schema(db_path)

    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_suite = json.load(f)

    test_cases: List[Dict[str, Any]] = test_suite.get("test_cases", [])
    log_func(f"Evaluating {len(test_cases)} test cases using ZeroShotBaseline ({baseline_optimizer.model_name})...\n")

    results: List[Dict[str, Any]] = []
    total_speedups: List[float] = []
    successful_cases = 0
    mismatch_cases = 0
    error_cases = 0

    for idx, tc in enumerate(test_cases, 1):
        tc_id = tc.get("id", f"TC-{idx:02d}")
        tc_name = tc.get("name", f"test_case_{idx}")
        original_query = tc["query"]
        anti_pattern = tc.get("anti_pattern", "Unknown")

        log_func(f"[{idx}/{len(test_cases)}] Evaluating {tc_id}: {tc_name}...")

        # 1. Execute original baseline query
        try:
            orig_rows, orig_ms = DatabaseSandbox.execute_query(db_path, original_query, timeout_sec=timeout_sec)
            orig_row_count = len(orig_rows)
            orig_error = None
        except DatabaseExecutionError as e:
            orig_rows = []
            orig_ms = None
            orig_row_count = 0
            orig_error = str(e)
            log_func(f"  ❌ Original query execution failed: {orig_error}")

        # 2. Get Zero-Shot optimization from LLM
        opt_start = time.perf_counter()
        opt_info = baseline_optimizer.optimize(original_query, schema)
        opt_elapsed_sec = time.perf_counter() - opt_start
        optimized_sql = opt_info["optimized_sql"]

        # 3. Attempt execution of candidate optimized query
        opt_rows: List[Tuple[Any, ...]] = []
        opt_ms: Optional[float] = None
        opt_row_count: int = 0
        opt_error: Optional[str] = None
        is_match: bool = False
        match_explanation: str = ""

        if orig_error is None:
            try:
                opt_rows, opt_ms = DatabaseSandbox.execute_query(db_path, optimized_sql, timeout_sec=timeout_sec)
                opt_row_count = len(opt_rows)

                # 4. Compare result sets for mathematical & structural equivalence
                is_match, match_explanation = DatabaseSandbox.compare_result_sets(
                    original_rows=orig_rows,
                    optimized_rows=opt_rows,
                    check_order=False
                )
            except DatabaseExecutionError as e:
                opt_error = str(e)
                match_explanation = f"Execution failed: {opt_error}"
        else:
            match_explanation = f"Original query failed: {orig_error}"

        # 5. Classify outcome status
        if opt_error is not None:
            status = "EXECUTION_ERROR"
            error_cases += 1
            speedup = None
            log_func(f"  ⚠️ Optimized query error: {opt_error}")
        elif not is_match:
            status = "RESULT_MISMATCH"
            mismatch_cases += 1
            speedup = None
            log_func(f"  ❌ Result mismatch: {match_explanation}")
        else:
            status = "SUCCESS"
            successful_cases += 1
            speedup = round(orig_ms / opt_ms, 2) if (orig_ms and opt_ms and opt_ms > 0) else 1.0
            total_speedups.append(speedup)
            log_func(f"  ✅ Equivalent results verified! Original: {orig_ms:.2f}ms -> Optimized: {opt_ms:.2f}ms ({speedup:.2f}x speedup)")

        results.append({
            "id": tc_id,
            "name": tc_name,
            "anti_pattern": anti_pattern,
            "status": status,
            "is_valid": is_match and opt_error is None,
            "original_query": original_query,
            "optimized_sql": optimized_sql,
            "original_execution_time_ms": orig_ms,
            "optimized_execution_time_ms": opt_ms,
            "speedup_ratio": speedup,
            "original_row_count": orig_row_count,
            "optimized_row_count": opt_row_count,
            "verification_message": match_explanation,
            "execution_error": opt_error,
            "llm_latency_sec": round(opt_elapsed_sec, 3),
            "raw_llm_response": opt_info["raw_response"]
        })

    avg_speedup = round(sum(total_speedups) / len(total_speedups), 2) if total_speedups else 0.0

    summary_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": baseline_optimizer.model_name,
        "database": str(db_path),
        "total_cases": len(test_cases),
        "successful_cases": successful_cases,
        "mismatch_cases": mismatch_cases,
        "error_cases": error_cases,
        "success_rate_pct": round((successful_cases / len(test_cases)) * 100.0, 1) if test_cases else 0.0,
        "average_speedup_on_successful": avg_speedup,
        "results": results
    }

    # Save to baseline_results.json
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    log_func("\n" + "=" * 55)
    log_func("BASELINE ZERO-SHOT EVALUATION SUMMARY")
    log_func("=" * 55)
    log_func(f"Model Evaluated     : {summary_data['model']}")
    log_func(f"Total Test Cases    : {summary_data['total_cases']}")
    log_func(f"Successful (Valid)  : {summary_data['successful_cases']}")
    log_func(f"Mismatched Results  : {summary_data['mismatch_cases']}")
    log_func(f"Execution Errors    : {summary_data['error_cases']}")
    log_func(f"Success Rate        : {summary_data['success_rate_pct']}%")
    log_func(f"Avg Speedup (Valid) : {summary_data['average_speedup_on_successful']}x")
    log_func(f"Output Saved To     : {output_path}")
    log_func("=" * 55 + "\n")

    return summary_data


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for baseline evaluation."""
    parser = argparse.ArgumentParser(
        description="Evaluate Zero-Shot LLM SQL query optimization baseline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--db-path", type=Path, default=Path("sandbox.db"), help="Path to SQLite sandbox database")
    parser.add_argument("--test-cases-path", type=Path, default=Path("test_cases.json"), help="Path to test cases JSON")
    parser.add_argument("--output-path", type=Path, default=Path("baseline_results.json"), help="Output path for results JSON")
    parser.add_argument("--provider", choices=["deepseek", "gemini", "openai", "anthropic", "mock"], default=None, help="LLM Provider to use (deepseek, gemini, openai, anthropic, mock)")
    parser.add_argument("--model", type=str, default=None, help="Model name (e.g. deepseek-chat, gemini-3.6-flash, gpt-4o, claude-3-5-sonnet-20241022)")
    parser.add_argument("--api-key", type=str, default=None, help="API key for LLM provider")
    parser.add_argument("--mock", action="store_true", help="Run with mock provider without making network requests")
    parser.add_argument("--timeout", type=float, default=10.0, help="Query timeout in seconds")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    return parser.parse_args(args)


def main() -> None:
    """CLI entry point for src/baseline.py."""
    parsed = parse_args()
    provider = "mock" if parsed.mock else parsed.provider

    try:
        baseline = ZeroShotBaseline(
            provider=provider,
            model=parsed.model,
            api_key=parsed.api_key
        )
        run_baseline(
            db_path=parsed.db_path,
            test_cases_path=parsed.test_cases_path,
            output_path=parsed.output_path,
            baseline_optimizer=baseline,
            timeout_sec=parsed.timeout,
            quiet=parsed.quiet
        )
    except Exception as e:
        print(f"Error executing baseline: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
