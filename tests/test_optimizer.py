"""Unit tests for Multi-Agent Optimizer Orchestrator, retry state machines, and trajectory logs."""

from __future__ import annotations

import json
import sqlite3
import pytest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.agent_optimizer import (
    DeveloperAgent,
    IndexArchitectAgent,
    OptimizerOrchestrator,
    ProfilerAgent,
    VerifierAgent,
)
from src.baseline import LLMProvider


@pytest.fixture
def sample_db(tmp_path: Path) -> Path:
    """Create a sample database for testing the optimizer state machine."""
    db_file = tmp_path / "optimizer_test.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            region TEXT,
            signup_date TEXT
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT,
            order_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        INSERT INTO users (id, name, region, signup_date) VALUES
            (1, 'Alice Smith', 'North America', '2024-01-15 10:00:00'),
            (2, 'Bob Jones', 'Europe', '2024-03-20 14:30:00'),
            (3, 'Charlie Brown', 'North America', '2025-02-10 09:15:00');
        INSERT INTO orders (id, user_id, amount, status, order_date) VALUES
            (1, 1, 150.0, 'completed', '2024-02-01 12:00:00'),
            (2, 1, 300.0, 'completed', '2024-04-05 15:00:00'),
            (3, 2, 50.0, 'cancelled', '2024-05-10 11:00:00'),
            (4, 3, 400.0, 'completed', '2025-03-01 16:20:00');
    """)
    conn.commit()
    conn.close()
    return db_file


class ProgrammableMockLLM(LLMProvider):
    """Mock LLM provider with custom sequential or condition-based responses."""

    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = list(responses) if responses else []
        self.call_count = 0
        self.prompts_received: List[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts_received.append(prompt)
        if self.responses and self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp

        # Default fallback JSON responses by agent prompt type
        if "Database Profiler" in prompt:
            return json.dumps({
                "identified_bottlenecks": [
                    {"type": "FULL_TABLE_SCAN", "table": "orders", "detail": "Full scan on orders", "severity": "HIGH"}
                ],
                "critical_tables": ["orders"],
                "has_temp_btree_sort": False,
                "optimization_strategy": "Add index on orders(user_id, status)"
            })
        elif "Index Architect" in prompt:
            return json.dumps({
                "recommended_indexes": [
                    {"table": "orders", "ddl": "CREATE INDEX idx_test_orders ON orders (user_id, status);", "purpose": "Speed up join and status filter"}
                ],
                "rationale": "Direct composite index"
            })
        elif "SQL Developer" in prompt:
            return json.dumps({
                "rewritten_sql": (
                    "SELECT u.id, u.name, o.id, o.amount "
                    "FROM users u "
                    "JOIN orders o ON u.id = o.user_id "
                    "WHERE o.status = 'completed' "
                    "ORDER BY o.amount DESC;"
                ),
                "applied_techniques": ["Index Alignment"],
                "rationale": "Optimized join order and predicate filters"
            })

        return "{}"


class TestOptimizerStateMachine:
    """Tests for OptimizerOrchestrator state machine and agents."""

    def test_single_pass_optimization_success(self, sample_db: Path, tmp_path: Path):
        """Test successful end-to-end optimization on first attempt."""
        client = ProgrammableMockLLM()
        orchestrator = OptimizerOrchestrator(client=client, max_retries=3)

        test_case = {
            "id": "TC-TEST-01",
            "name": "sample_join_test",
            "anti_pattern": "Unindexed join",
            "query": (
                "SELECT u.id, u.name, o.id, o.amount "
                "FROM users u "
                "JOIN orders o ON u.id = o.user_id "
                "WHERE o.status = 'completed' "
                "ORDER BY o.amount DESC;"
            )
        }

        schema = (
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, region TEXT, signup_date TEXT);\n"
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, status TEXT, order_date TEXT);"
        )

        outcome = orchestrator.optimize_query(
            test_case=test_case,
            schema=schema,
            base_db_path=sample_db,
            scratch_dir=tmp_path / "scratch"
        )

        assert outcome["status"] == "SUCCESS"
        assert outcome["is_valid"] is True
        assert outcome["total_attempts"] == 1
        assert outcome["speedup_ratio"] is not None
        assert len(outcome["applied_indexes"]) == 1

    def test_retry_loop_on_developer_syntax_error(self, sample_db: Path, tmp_path: Path):
        """Test that syntax errors in attempt 1 trigger a retry with error feedback and succeed on attempt 2."""
        # 1. Profiler response
        r1_profiler = json.dumps({
            "identified_bottlenecks": [{"type": "FULL_TABLE_SCAN", "table": "orders", "detail": "Scan", "severity": "HIGH"}],
            "critical_tables": ["orders"],
            "has_temp_btree_sort": False,
            "optimization_strategy": "Rewrite join"
        })
        # 2. Architect response
        r2_architect = json.dumps({
            "recommended_indexes": [{"table": "orders", "ddl": "CREATE INDEX idx_ord_user ON orders(user_id);", "purpose": "Join"}],
            "rationale": "Index"
        })
        # 3. Developer Attempt 1: Returns broken SQL syntax
        r3_dev_fail = json.dumps({
            "rewritten_sql": "SELECT FROM BROKEN SYNTAX WHERE 1=;",
            "applied_techniques": ["Faulty Rewrite"],
            "rationale": "Faulty"
        })
        # 4. Developer Attempt 2: Fixed SQL syntax after receiving feedback
        r4_dev_success = json.dumps({
            "rewritten_sql": (
                "SELECT u.id, u.name, o.id, o.amount "
                "FROM users u "
                "JOIN orders o ON u.id = o.user_id "
                "WHERE o.status = 'completed' "
                "ORDER BY o.amount DESC;"
            ),
            "applied_techniques": ["Fixed Syntax", "Indexed Join"],
            "rationale": "Fixed previous syntax error"
        })

        client = ProgrammableMockLLM(responses=[r1_profiler, r2_architect, r3_dev_fail, r4_dev_success])
        orchestrator = OptimizerOrchestrator(client=client, max_retries=3)

        test_case = {
            "id": "TC-RETRY-01",
            "name": "syntax_retry_test",
            "anti_pattern": "Unindexed join",
            "query": (
                "SELECT u.id, u.name, o.id, o.amount "
                "FROM users u "
                "JOIN orders o ON u.id = o.user_id "
                "WHERE o.status = 'completed' "
                "ORDER BY o.amount DESC;"
            )
        }

        schema = "CREATE TABLE users (id INT); CREATE TABLE orders (id INT, user_id INT, status TEXT, amount REAL);"

        outcome = orchestrator.optimize_query(
            test_case=test_case,
            schema=schema,
            base_db_path=sample_db,
            scratch_dir=tmp_path / "scratch"
        )

        assert outcome["status"] == "SUCCESS"
        assert outcome["is_valid"] is True
        assert outcome["total_attempts"] == 2

        # Verify that prompt in attempt 2 received error feedback
        dev_prompt_attempt_2 = client.prompts_received[3]
        assert "PREVIOUS ATTEMPT FAILED VERIFICATION" in dev_prompt_attempt_2
        assert "SELECT FROM BROKEN SYNTAX" in dev_prompt_attempt_2

    def test_maximum_retry_cutoff(self, sample_db: Path, tmp_path: Path):
        """Test that orchestrator stops after exactly 3 retries when candidate SQL persistently fails."""
        r_profiler = json.dumps({"identified_bottlenecks": [], "critical_tables": [], "has_temp_btree_sort": False, "optimization_strategy": "None"})
        r_architect = json.dumps({"recommended_indexes": [], "rationale": "None"})
        # 3 consecutive bad SQL responses
        r_bad_sql = json.dumps({"rewritten_sql": "SELECT INVALID SQL FAIL;", "applied_techniques": [], "rationale": "Bad"})

        client = ProgrammableMockLLM(responses=[r_profiler, r_architect, r_bad_sql, r_bad_sql, r_bad_sql])
        orchestrator = OptimizerOrchestrator(client=client, max_retries=3)

        test_case = {
            "id": "TC-FAIL-01",
            "name": "max_retries_test",
            "anti_pattern": "Testing cutoff",
            "query": "SELECT count(*) FROM users;"
        }

        outcome = orchestrator.optimize_query(
            test_case=test_case,
            schema="CREATE TABLE users (id INT);",
            base_db_path=sample_db,
            scratch_dir=tmp_path / "scratch"
        )

        assert outcome["status"] in ("ERROR", "FAILED")
        assert outcome["is_valid"] is False
        assert outcome["total_attempts"] == 3

    def test_trajectory_structure_and_formatting(self, sample_db: Path, tmp_path: Path):
        """Test that the generated execution trajectory captures all required stages, prompts, and tool outputs."""
        client = ProgrammableMockLLM()
        orchestrator = OptimizerOrchestrator(client=client, max_retries=3)

        test_case = {
            "id": "TC-TRAJ-01",
            "name": "trajectory_test",
            "anti_pattern": "Trajectory Verification",
            "query": (
                "SELECT u.id, u.name, o.id, o.amount "
                "FROM users u "
                "JOIN orders o ON u.id = o.user_id "
                "WHERE o.status = 'completed' "
                "ORDER BY o.amount DESC;"
            )
        }

        traj_dir = tmp_path / "trajectories"
        output_results = tmp_path / "test_results.json"

        # Create temporary test_cases.json
        tc_file = tmp_path / "test_cases.json"
        with open(tc_file, "w") as f:
            json.dump({"test_cases": [test_case]}, f)

        summary = orchestrator.run_optimization_suite(
            db_path=sample_db,
            test_cases_path=tc_file,
            output_path=output_results,
            trajectories_dir=traj_dir,
            quiet=True
        )

        assert summary["successful_cases"] == 1
        assert summary["total_cases"] == 1

        # Check trajectory file on disk
        traj_file = traj_dir / "TC-TRAJ-01_trajectory_test.json"
        assert traj_file.exists()

        with open(traj_file, "r", encoding="utf-8") as f:
            traj_data = json.load(f)

        assert traj_data["test_case_id"] == "TC-TRAJ-01"
        assert "stages" in traj_data
        assert "profiler" in traj_data["stages"]
        assert "index_architect" in traj_data["stages"]
        assert "developer_verifier_loop" in traj_data["stages"]

        loop = traj_data["stages"]["developer_verifier_loop"]
        assert loop["total_attempts"] == 1
        assert loop["succeeded"] is True
        assert len(loop["attempts"]) == 1

        first_attempt = loop["attempts"][0]
        assert "developer_report" in first_attempt
        assert "verification_report" in first_attempt
        assert first_attempt["verification_report"]["status"] == "PASSED"

        # Check execution_steps array
        assert "execution_steps" in traj_data
        steps = traj_data["execution_steps"]
        assert len(steps) >= 3
        profiler_step = steps[0]
        assert profiler_step["agent_id"] == "Profiler"
        assert profiler_step["tool_called"] == "DatabaseSandbox.get_explain_plan"
        assert "tool_arguments" in profiler_step
        assert "tool_output" in profiler_step
        assert profiler_step["retries_triggered"] == 0

        architect_step = steps[1]
        assert architect_step["agent_id"] == "IndexArchitect"
        assert architect_step["tool_called"] == "DatabaseSandbox.apply_index"

        developer_step = steps[2]
        assert developer_step["agent_id"] == "Developer"
        assert developer_step["tool_called"] == "DatabaseSandbox.verify"
        assert "tool_output" in developer_step
        assert developer_step["retries_triggered"] == 0

    def test_orchestrator_deepseek_provider_init(self, monkeypatch):
        """Test that OptimizerOrchestrator initializes DeepSeek provider with default model."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-sk-abc")
        orchestrator = OptimizerOrchestrator(provider="deepseek")
        assert orchestrator.model_name == "deepseek-chat"
        assert orchestrator.llm_client.api_key == "test-deepseek-sk-abc"

    def test_orchestrator_deepseek_missing_key(self, monkeypatch):
        """Test that OptimizerOrchestrator raises ValueError when deepseek provider requested without key."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(ValueError, match="DeepSeek API key required"):
            OptimizerOrchestrator(provider="deepseek", api_key=None)

