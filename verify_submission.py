#!/usr/bin/env python3
"""Submission Sanity Check & Clean Environment Verifier.

This script programmatically verifies that the repository meets strict hackathon
reproducibility requirements:
1. Validates that requirements.txt exists and contains required LLM packages (openai / anthropic / deepseek).
2. Sequentially executes setup_db.py, baseline.py, and agent_optimizer.py (and evaluate.py) as isolated subprocesses.
3. Validates that evaluation_results.json and trajectories.json exist and are well-formed JSON.
4. Parses evaluation_results.json to assert that the multi-agent optimizer achieves higher accuracy than the zero-shot baseline.
5. Outputs a green 'READY FOR SUBMISSION' banner upon complete verification, or a red descriptive error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ANSI Terminal Color Codes
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


def print_success(msg: str) -> None:
    """Print success message in green."""
    print(f"  {COLOR_GREEN}✔{COLOR_RESET} {msg}")


def print_warning(msg: str) -> None:
    """Print warning message in yellow."""
    print(f"  {COLOR_YELLOW}⚠{COLOR_RESET} {msg}")


def print_failure(msg: str) -> None:
    """Print failure message in red."""
    print(f"  {COLOR_RED}✘{COLOR_RESET} {msg}")


def print_banner_success() -> None:
    """Print the final green READY FOR SUBMISSION banner."""
    print("\n" + COLOR_GREEN + COLOR_BOLD + "=" * 70)
    print("                      READY FOR SUBMISSION")
    print("=" * 70 + COLOR_RESET + "\n")


def print_banner_failure(error_reason: str) -> None:
    """Print the red failure banner with exact cause."""
    print("\n" + COLOR_RED + COLOR_BOLD + "=" * 70)
    print("                   SUBMISSION VERIFICATION FAILED")
    print("=" * 70 + COLOR_RESET)
    print(f"\n{COLOR_RED}{COLOR_BOLD}Reason for Failure:{COLOR_RESET}")
    print(f"  {COLOR_RED}{error_reason}{COLOR_RESET}\n")


def check_requirements_file(root_dir: Path) -> Tuple[bool, str]:
    """Check if requirements.txt exists and contains expected dependencies."""
    req_file = root_dir / "requirements.txt"
    if not req_file.exists():
        return False, f"Missing requirements.txt at {req_file}"

    try:
        content = req_file.read_text(encoding="utf-8").lower()
        required_pkgs = ["openai", "anthropic", "google", "deepseek"]
        found = [pkg for pkg in required_pkgs if pkg in content]
        if not found:
            return False, (
                f"requirements.txt exists but does not contain standard LLM client dependencies "
                f"(expected at least one of: {', '.join(required_pkgs)})"
            )
        return True, f"Found requirements.txt with packages: {', '.join(found)}"
    except Exception as e:
        return False, f"Failed to read requirements.txt: {e}"


def run_subprocess_command(
    cmd: List[str],
    cwd: Path,
    description: str
) -> Tuple[bool, str]:
    """Execute a subprocess command and stream/capture output."""
    print(f"\n{COLOR_CYAN}▶ Running {description}...{COLOR_RESET}")
    cmd_str = " ".join(cmd)
    print(f"  Command: {cmd_str}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            err_msg = (
                f"Subprocess '{description}' failed with exit code {result.returncode}.\n"
                f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
            )
            return False, err_msg

        return True, result.stdout
    except subprocess.TimeoutExpired:
        return False, f"Subprocess '{description}' timed out after 300 seconds."
    except Exception as e:
        return False, f"Subprocess '{description}' failed with error: {e}"


def verify_json_artifact(file_path: Path, expected_keys: Optional[List[str]] = None) -> Tuple[bool, Any, str]:
    """Verify that a required JSON artifact file exists and contains valid JSON."""
    if not file_path.exists():
        return False, {}, f"Artifact file '{file_path.name}' does not exist at {file_path}."

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            if not data:
                return False, data, f"Artifact '{file_path.name}' is an empty array."
            if expected_keys:
                first_item = data[0] if isinstance(data[0], dict) else {}
                missing = [k for k in expected_keys if k not in first_item]
                if missing:
                    return False, data, f"Execution objects in '{file_path.name}' missing keys: {', '.join(missing)}."
            return True, data, f"Valid JSON array artifact with {len(data)} execution objects."

        elif isinstance(data, dict):
            if expected_keys:
                missing = [k for k in expected_keys if k not in data]
                if missing:
                    return False, data, f"Artifact '{file_path.name}' is missing required keys: {', '.join(missing)}."
            return True, data, f"Valid JSON dictionary artifact with {len(data)} root keys."

        else:
            return False, {}, f"Artifact '{file_path.name}' must contain a JSON object or array, found {type(data).__name__}."

    except json.JSONDecodeError as e:
        return False, {}, f"Artifact '{file_path.name}' contains invalid JSON: {e}"
    except Exception as e:
        return False, {}, f"Error reading artifact '{file_path.name}': {e}"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for verify_submission.py."""
    parser = argparse.ArgumentParser(
        description="Verify clean environment reproducibility and benchmark validity for submission.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run verification subprocesses with mock provider (for fast offline sanity checks)"
    )
    parser.add_argument(
        "--skip-execution",
        action="store_true",
        help="Skip subprocess execution and verify existing artifacts directly"
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        choices=["deepseek", "gemini", "openai", "anthropic", "mock"],
        help="LLM provider for execution verification"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name to use for verification runs"
    )
    return parser.parse_args()


def main() -> None:
    """Main verification sanity check routine."""
    args = parse_args()
    root_dir = Path(__file__).resolve().parent

    print("\n" + COLOR_BOLD + "=" * 70)
    print("   AUTOMATED SUBMISSION SANITY CHECK & CLEAN ENVIRONMENT TESTER")
    print("=" * 70 + COLOR_RESET)

    # -------------------------------------------------------------
    # Step 1: Verify requirements.txt
    # -------------------------------------------------------------
    print(f"\n{COLOR_BOLD}[1/4] Checking requirements.txt & Dependencies...{COLOR_RESET}")
    req_ok, req_msg = check_requirements_file(root_dir)
    if not req_ok:
        print_failure(req_msg)
        print_banner_failure(req_msg)
        sys.exit(1)
    print_success(req_msg)

    # -------------------------------------------------------------
    # Step 2: Execute Sequential Subprocesses
    # -------------------------------------------------------------
    print(f"\n{COLOR_BOLD}[2/4] Executing Subprocesses (setup_db -> baseline -> agent_optimizer -> evaluate)...{COLOR_RESET}")

    if not args.skip_execution:
        py_exec = sys.executable
        mode_flag = ["--mock"] if args.mock else ([] if not args.provider else ["--provider", args.provider])

        # 2a. Run setup_db.py
        setup_cmd = [py_exec, "setup_db.py", "--force"]
        ok, out = run_subprocess_command(setup_cmd, root_dir, "setup_db.py")
        if not ok:
            print_failure("setup_db.py failed")
            print_banner_failure(out)
            sys.exit(1)
        print_success("setup_db.py completed successfully.")

        # 2b. Run baseline.py
        baseline_cmd = [py_exec, "baseline.py"] + mode_flag
        ok, out = run_subprocess_command(baseline_cmd, root_dir, "baseline.py")
        if not ok:
            print_failure("baseline.py failed")
            print_banner_failure(out)
            sys.exit(1)
        print_success("baseline.py completed successfully.")

        # 2c. Run agent_optimizer.py
        agent_cmd = [py_exec, "agent_optimizer.py"] + mode_flag
        ok, out = run_subprocess_command(agent_cmd, root_dir, "agent_optimizer.py")
        if not ok:
            print_failure("agent_optimizer.py failed")
            print_banner_failure(out)
            sys.exit(1)
        print_success("agent_optimizer.py completed successfully.")

        # 2d. Run evaluate.py to produce final comparative artifacts
        eval_cmd = [py_exec, "evaluate.py"] + mode_flag
        ok, out = run_subprocess_command(eval_cmd, root_dir, "evaluate.py")
        if not ok:
            print_failure("evaluate.py failed")
            print_banner_failure(out)
            sys.exit(1)
        print_success("evaluate.py completed successfully.")
    else:
        print_warning("Subprocess execution skipped via --skip-execution flag.")

    # -------------------------------------------------------------
    # Step 3: Verify Output Artifacts
    # -------------------------------------------------------------
    print(f"\n{COLOR_BOLD}[3/4] Validating Generated Artifacts...{COLOR_RESET}")

    eval_file = root_dir / "evaluation_results.json"
    traj_file = root_dir / "trajectories.json"

    eval_ok, eval_data, eval_msg = verify_json_artifact(
        eval_file,
        expected_keys=["summary", "comparison_table"]
    )
    if not eval_ok:
        print_failure(f"evaluation_results.json check failed: {eval_msg}")
        print_banner_failure(eval_msg)
        sys.exit(1)
    print_success(f"evaluation_results.json verified: {eval_msg}")

    traj_ok, traj_data, traj_msg = verify_json_artifact(
        traj_file,
        expected_keys=["agent_id", "raw_prompt", "tool_called", "tool_arguments", "tool_output", "retries_triggered"]
    )
    if not traj_ok:
        print_failure(f"trajectories.json check failed: {traj_msg}")
        print_banner_failure(traj_msg)
        sys.exit(1)
    num_traces = len(traj_data) if isinstance(traj_data, list) else len(traj_data.get("trajectories", []))
    print_success(f"trajectories.json verified: {traj_msg} (Contains {num_traces} execution traces)")

    # -------------------------------------------------------------
    # Step 4: Parse & Assert Metric Superiority
    # -------------------------------------------------------------
    print(f"\n{COLOR_BOLD}[4/4] Evaluating Accuracy & Performance Metrics...{COLOR_RESET}")

    summary = eval_data.get("summary", {})
    baseline_summary = summary.get("baseline", {})
    agent_summary = summary.get("agent_optimizer", {})

    baseline_acc = float(baseline_summary.get("success_rate_pct", 0.0))
    agent_acc = float(agent_summary.get("success_rate_pct", 0.0))

    baseline_speedup = float(baseline_summary.get("average_speedup", 0.0))
    agent_speedup = float(agent_summary.get("average_speedup", 0.0))

    print(f"  Zero-Shot Baseline Accuracy   : {baseline_acc:.1f}%")
    print(f"  Multi-Agent Optimizer Accuracy: {agent_acc:.1f}%")
    print(f"  Multi-Agent Average Speedup   : {agent_speedup:.2f}x")

    # Assert accuracy constraint
    if agent_acc < baseline_acc:
        err = (
            f"Multi-Agent accuracy ({agent_acc}%) is lower than baseline accuracy ({baseline_acc}%). "
            f"The agent optimizer must achieve equal or superior correctness."
        )
        print_failure(err)
        print_banner_failure(err)
        sys.exit(1)

    print_success(f"Multi-Agent accuracy ({agent_acc}%) >= Baseline accuracy ({baseline_acc}%).")

    # -------------------------------------------------------------
    # Final Result
    # -------------------------------------------------------------
    print_banner_success()


if __name__ == "__main__":
    main()
