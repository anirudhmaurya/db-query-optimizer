"""Unit tests for verify_submission.py."""

import json
import pytest
from pathlib import Path

from verify_submission import check_requirements_file, verify_json_artifact


def test_check_requirements_file_success(tmp_path: Path):
    """Test checking requirements.txt when valid packages are present."""
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("openai>=1.0.0\nanthropic>=0.20.0\n", encoding="utf-8")

    ok, msg = check_requirements_file(tmp_path)
    assert ok is True
    assert "openai" in msg


def test_check_requirements_file_missing(tmp_path: Path):
    """Test checking requirements.txt when file is absent."""
    ok, msg = check_requirements_file(tmp_path)
    assert ok is False
    assert "Missing requirements.txt" in msg


def test_verify_json_artifact_valid(tmp_path: Path):
    """Test verifying a valid JSON artifact."""
    json_file = tmp_path / "eval.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"summary": {}, "comparison_table": []}, f)

    ok, data, msg = verify_json_artifact(json_file, expected_keys=["summary", "comparison_table"])
    assert ok is True
    assert "summary" in data


def test_verify_json_artifact_missing_keys(tmp_path: Path):
    """Test verifying a JSON artifact missing required keys."""
    json_file = tmp_path / "eval.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"wrong_key": 123}, f)

    ok, data, msg = verify_json_artifact(json_file, expected_keys=["summary"])
    assert ok is False
    assert "missing required keys" in msg
