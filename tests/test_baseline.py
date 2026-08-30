"""Unit tests for ZeroShotBaseline and baseline evaluation runner."""

import json
import sqlite3
import pytest
from pathlib import Path

from src.baseline import ZeroShotBaseline, clean_sql_response, run_baseline, LLMProvider


class MockTestEchoClient(LLMProvider):
    """Simple test client returning predictable responses."""

    def __init__(self, response: str = "SELECT 1;"):
        self.response = response
        self.last_prompt = ""

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


def test_clean_sql_response_markdown():
    """Test extracting clean SQL from markdown code fences."""
    raw = "```sql\nSELECT u.id, u.name FROM users u;\n```"
    assert clean_sql_response(raw) == "SELECT u.id, u.name FROM users u;"


def test_clean_sql_response_multi_statement():
    """Test extracting primary query from multi-statement LLM response."""
    raw = (
        "```sql\n"
        "-- Suggested Index\n"
        "CREATE INDEX idx_user ON users(id);\n\n"
        "-- Query\n"
        "SELECT * FROM users WHERE id = 1;\n"
        "```"
    )
    assert clean_sql_response(raw) == "SELECT * FROM users WHERE id = 1;"


def test_zero_shot_baseline_prompt_format():
    """Test that ZeroShotBaseline issues the exact ungrounded, concise prompt."""
    client = MockTestEchoClient("SELECT * FROM users;")
    optimizer = ZeroShotBaseline(client=client)

    result = optimizer.optimize("SELECT * FROM users;", "CREATE TABLE users (id INT);")
    assert "You are an SQL assistant. Rewrite the following SQL query to make it run faster on SQLite:" in result["prompt"]
    assert "SQL: SELECT * FROM users;" in result["prompt"]
    assert "Schema: CREATE TABLE users (id INT);" in result["prompt"]
    assert "Return only the rewritten SQL query without markdown or explanations." in result["prompt"]
    assert result["optimized_sql"] == "SELECT * FROM users;"


def test_run_baseline_execution(tmp_path: Path):
    """Test running baseline evaluation on a mini test suite."""
    db_file = tmp_path / "baseline_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob');")
    conn.commit()
    conn.close()

    tc_file = tmp_path / "test_cases.json"
    with open(tc_file, "w") as f:
        json.dump({
            "test_cases": [
                {
                    "id": "TC-01",
                    "name": "simple_select",
                    "anti_pattern": "None",
                    "query": "SELECT name FROM users WHERE id = 1;"
                }
            ]
        }, f)

    out_file = tmp_path / "results.json"
    client = MockTestEchoClient("```sql\nSELECT name FROM users WHERE id = 1;\n```")
    baseline = ZeroShotBaseline(client=client)

    summary = run_baseline(
        db_path=db_file,
        test_cases_path=tc_file,
        output_path=out_file,
        baseline_optimizer=baseline,
        quiet=True
    )

    assert summary["total_cases"] == 1
    assert summary["successful_cases"] == 1
    assert summary["results"][0]["status"] == "SUCCESS"
    assert out_file.exists()


def test_deepseek_provider_request(monkeypatch):
    """Test that DeepSeekProvider sends expected payload and headers."""
    from src.baseline import DeepSeekProvider
    import io

    captured_requests = []

    class MockResponse:
        def __init__(self, data: dict):
            self.data = json.dumps(data).encode("utf-8")

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=60.0):
        captured_requests.append(req)
        return MockResponse({
            "choices": [
                {"message": {"content": "SELECT 42;"}}
            ]
        })

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    provider = DeepSeekProvider(api_key="test-sk-deepseek-123", model="deepseek-chat")
    res = provider.complete("Optimize this query")

    assert res == "SELECT 42;"
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.full_url == "https://api.deepseek.com/chat/completions"
    assert req.headers["Authorization"] == "Bearer test-sk-deepseek-123"
    assert req.headers["Content-type"] == "application/json"

    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "deepseek-chat"
    assert body["messages"] == [{"role": "user", "content": "Optimize this query"}]
    assert body["temperature"] == 0.0


def test_zero_shot_baseline_deepseek_init(monkeypatch):
    """Test that ZeroShotBaseline initializes DeepSeekProvider when provider='deepseek'."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
    baseline = ZeroShotBaseline(provider="deepseek")
    assert baseline.model_name == "deepseek-chat"
    assert baseline.client.api_key == "test-key-123"

