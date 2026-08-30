"""Unit tests for src/evaluate.py and root evaluate.py runner."""

import json
import sqlite3
import pytest
from pathlib import Path

from src.evaluate import consolidate_trajectories, format_table, run_evaluation


def test_format_table():
    """Test ASCII table formatting logic."""
    headers = ["ID", "Accuracy", "Latency (ms)"]
    rows = [
        ["TC-01", "100%", "12.34"],
        ["TC-02", "0%", "56.78"]
    ]
    alignments = ["center", "center", "right"]

    rendered = format_table(headers, rows, alignments)
    assert "+-------+----------+--------------+" in rendered
    assert "TC-01" in rendered
    assert "100%" in rendered
    assert "12.34" in rendered


def test_consolidate_trajectories(tmp_path: Path):
    """Test consolidating individual trajectory JSON files into a single artifact."""
    traj_dir = tmp_path / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)

    t1 = {"test_case_id": "TC-01", "test_case_name": "tc1", "stages": {"profiler": {}}}
    t2 = {"test_case_id": "TC-02", "test_case_name": "tc2", "stages": {"profiler": {}}}

    with open(traj_dir / "TC-01_tc1.json", "w", encoding="utf-8") as f:
        json.dump(t1, f)
    with open(traj_dir / "TC-02_tc2.json", "w", encoding="utf-8") as f:
        json.dump(t2, f)

    consolidated = consolidate_trajectories(traj_dir)
    assert consolidated["total_trajectories"] == 2
    assert len(consolidated["trajectories"]) == 2
    assert consolidated["trajectories"][0]["test_case_id"] == "TC-01"
    assert consolidated["trajectories"][1]["test_case_id"] == "TC-02"


def test_run_evaluation_mock(tmp_path: Path):
    """Test end-to-end evaluation execution with mock provider."""
    db_file = tmp_path / "eval_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE users (id INT PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob');")
    conn.commit()
    conn.close()

    tc_file = tmp_path / "test_cases.json"
    with open(tc_file, "w", encoding="utf-8") as f:
        json.dump({
            "test_cases": [
                {
                    "id": "TC-01",
                    "name": "sample_eval",
                    "anti_pattern": "Unindexed lookup",
                    "query": "SELECT name FROM users WHERE id = 1;"
                }
            ]
        }, f)

    eval_out = tmp_path / "evaluation_results.json"
    traj_out = tmp_path / "trajectories.json"
    traj_dir = tmp_path / "trajectories"

    res = run_evaluation(
        db_path=db_file,
        test_cases_path=tc_file,
        evaluation_results_path=eval_out,
        trajectories_path=traj_out,
        trajectories_dir=traj_dir,
        baseline_results_path=tmp_path / "baseline_results.json",
        agent_results_path=tmp_path / "agent_results.json",
        provider="mock",
        quiet=True
    )

    assert eval_out.exists()
    assert traj_out.exists()
    assert res["total_queries"] == 1
    assert "summary" in res
    assert "comparison_table" in res
    assert len(res["comparison_table"]) == 1

    item = res["comparison_table"][0]
    assert item["query_id"] == "TC-01"
    assert "baseline" in item
    assert "agent" in item
    assert item["agent"]["accuracy_pct"] == 100.0
