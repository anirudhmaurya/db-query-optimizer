"""Comparative Evaluation Suite: Zero-Shot Baseline vs. Multi-Agent Optimizer.

This module evaluates all benchmark queries on both the Zero-Shot LLM DBA Baseline
and the Multi-Agent Optimizer Orchestrator. It produces:
1. A clean CLI summary table comparing accuracy, latency, speedup, index creation, and retries.
2. 'evaluation_results.json': Complete comparative quantitative dataset.
3. 'trajectories.json': Consolidated evidence trace of every agent prompt, tool response, and verification step.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.agent_optimizer import OptimizerOrchestrator
from src.baseline import ZeroShotBaseline, load_env_file, run_baseline

logger = logging.getLogger(__name__)

# Ensure .env is loaded
load_env_file()


def format_table(
    headers: List[str],
    rows: List[List[str]],
    alignments: Optional[List[str]] = None
) -> str:
    """Format a clean, readable ASCII grid table for CLI reporting.

    Args:
        headers: List of column header strings.
        rows: List of rows, where each row is a list of cell strings.
        alignments: List of alignment indicators ('left', 'right', 'center').

    Returns:
        Formatted ASCII table string.
    """
    if not alignments:
        alignments = ["left"] * len(headers)

    # Compute maximum width for each column
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Add 2 spaces padding per column
    padded_widths = [w + 2 for w in col_widths]

    def build_separator(char_left: str, char_mid: str, char_right: str, fill: str = "-") -> str:
        parts = [fill * w for w in padded_widths]
        return char_left + char_mid.join(parts) + char_right

    top_border = build_separator("+", "+", "+", "-")
    header_separator = build_separator("+", "+", "+", "=")
    row_separator = build_separator("+", "+", "+", "-")
    bottom_border = build_separator("+", "+", "+", "-")

    def format_row(cells: List[str]) -> str:
        formatted_cells = []
        for i, cell in enumerate(cells):
            cell_str = str(cell)
            align = alignments[i] if i < len(alignments) else "left"
            width = padded_widths[i] - 2
            if align == "right":
                aligned = cell_str.rjust(width)
            elif align == "center":
                aligned = cell_str.center(width)
            else:
                aligned = cell_str.ljust(width)
            formatted_cells.append(f" {aligned} ")
        return "|" + "|".join(formatted_cells) + "|"

    output_lines = [
        top_border,
        format_row(headers),
        header_separator,
    ]

    for row in rows:
        output_lines.append(format_row(row))
        output_lines.append(row_separator)

    return "\n".join(output_lines)


def consolidate_trajectories(trajectories_dir: Path) -> List[Dict[str, Any]]:
    """Read and aggregate all individual trajectory execution objects into a consolidated array.

    Args:
        trajectories_dir: Directory containing individual test case trajectory files.

    Returns:
        Consolidated list of execution objects.
    """
    execution_objects: List[Dict[str, Any]] = []
    if trajectories_dir.exists():
        for file_path in sorted(trajectories_dir.glob("*.json")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    traj_data = json.load(f)
                    if isinstance(traj_data, dict) and "execution_steps" in traj_data:
                        execution_objects.extend(traj_data["execution_steps"])
                    elif isinstance(traj_data, list):
                        execution_objects.extend(traj_data)
            except Exception as e:
                logger.warning("Could not read trajectory file %s: %s", file_path, e)

    return execution_objects


def run_evaluation(
    db_path: Path = Path("sandbox.db"),
    test_cases_path: Path = Path("test_cases.json"),
    evaluation_results_path: Path = Path("evaluation_results.json"),
    trajectories_path: Path = Path("trajectories.json"),
    trajectories_dir: Path = Path("trajectories"),
    baseline_results_path: Path = Path("baseline_results.json"),
    agent_results_path: Path = Path("agent_results.json"),
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout_sec: float = 10.0,
    max_retries: int = 3,
    quiet: bool = False
) -> Dict[str, Any]:
    """Run both baseline and multi-agent optimizer on all queries, print CLI table, and produce artifacts.

    Args:
        db_path: Path to database SQLite file.
        test_cases_path: Path to test cases JSON file.
        evaluation_results_path: Output path for evaluation_results.json.
        trajectories_path: Output path for consolidated trajectories.json.
        trajectories_dir: Directory for storing trajectory files.
        baseline_results_path: Path for baseline intermediate results.
        agent_results_path: Path for agent intermediate results.
        provider: LLM provider name ('deepseek', 'gemini', 'openai', 'anthropic', 'mock').
        model: Target LLM model name.
        api_key: Optional explicit API key.
        timeout_sec: Execution timeout in seconds per query.
        max_retries: Max retry attempts for multi-agent optimizer.
        quiet: If True, suppress verbose step output.

    Returns:
        Structured comparative evaluation dictionary.
    """
    def log(msg: str = "") -> None:
        if not quiet:
            print(msg)

    log("\n" + "=" * 70)
    log("  BENCHMARK EVALUATION: ZERO-SHOT BASELINE vs. MULTI-AGENT OPTIMIZER")
    log("=" * 70 + "\n")

    # Step 1: Initialize Baseline and Multi-Agent Orchestrator
    baseline = ZeroShotBaseline(
        provider=provider,
        model=model,
        api_key=api_key
    )

    orchestrator = OptimizerOrchestrator(
        provider=provider,
        model=model,
        api_key=api_key,
        max_retries=max_retries,
        timeout_sec=timeout_sec
    )

    model_display = orchestrator.model_name

    # Step 2: Run Baseline Evaluation
    log(">>> STAGE 1: Running Zero-Shot Baseline Evaluation...")
    baseline_summary = run_baseline(
        db_path=db_path,
        test_cases_path=test_cases_path,
        output_path=baseline_results_path,
        baseline_optimizer=baseline,
        timeout_sec=timeout_sec,
        quiet=quiet
    )

    # Step 3: Run Multi-Agent Optimizer Evaluation
    log("\n>>> STAGE 2: Running Multi-Agent Optimizer Orchestrator...")
    agent_summary = orchestrator.run_optimization_suite(
        db_path=db_path,
        test_cases_path=test_cases_path,
        output_path=agent_results_path,
        trajectories_dir=trajectories_dir,
        quiet=quiet
    )

    # Step 4: Compute Comparison Metrics and Build CLI Table
    baseline_map = {res["id"]: res for res in baseline_summary.get("results", [])}
    agent_map = {res["id"]: res for res in agent_summary.get("results", [])}

    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_suite = json.load(f)
    test_cases = test_suite.get("test_cases", [])

    table_rows = []
    comparison_items = []
    total_indexes_created = 0
    total_retries = 0

    for idx, tc in enumerate(test_cases, 1):
        tc_id = tc.get("id", f"TC-{idx:02d}")
        tc_name = tc.get("name", f"test_case_{idx}")
        anti_pattern = tc.get("anti_pattern", "None")

        b_res = baseline_map.get(tc_id, {})
        a_res = agent_map.get(tc_id, {})

        # Baseline accuracy & latency
        b_valid = b_res.get("is_valid", False)
        b_acc_str = "100%" if b_valid else "0%"
        b_acc_pct = 100.0 if b_valid else 0.0
        b_opt_ms = b_res.get("optimized_execution_time_ms")
        b_speedup = b_res.get("speedup_ratio") or 1.0

        # Agent accuracy & latency
        a_valid = a_res.get("is_valid", False)
        a_acc_str = "100%" if a_valid else "0%"
        a_acc_pct = 100.0 if a_valid else 0.0
        orig_ms = a_res.get("original_execution_time_ms") or b_res.get("original_execution_time_ms")
        a_opt_ms = a_res.get("optimized_execution_time_ms")
        a_speedup = a_res.get("speedup_ratio")

        # Indexes applied
        applied_indexes = a_res.get("applied_indexes", [])
        num_indexes = len(applied_indexes)
        total_indexes_created += num_indexes
        index_created_str = f"Yes ({num_indexes})" if num_indexes > 0 else "No"

        # Iterations / Retries
        attempts = a_res.get("total_attempts", 1)
        total_retries += attempts
        retries_str = str(attempts)

        # Format strings for table
        orig_ms_str = f"{orig_ms:.2f}" if orig_ms is not None else "N/A"
        opt_ms_str = f"{a_opt_ms:.2f}" if a_opt_ms is not None else "N/A"
        speedup_str = f"{a_speedup:.2f}x" if (a_speedup is not None and a_valid) else "—"

        table_rows.append([
            tc_id,
            b_acc_str,
            a_acc_str,
            orig_ms_str,
            opt_ms_str,
            speedup_str,
            index_created_str,
            retries_str
        ])

        comparison_items.append({
            "query_id": tc_id,
            "name": tc_name,
            "anti_pattern": anti_pattern,
            "baseline": {
                "accuracy_pct": b_acc_pct,
                "status": b_res.get("status", "UNKNOWN"),
                "is_valid": b_valid,
                "optimized_latency_ms": b_opt_ms,
                "speedup_ratio": b_speedup
            },
            "agent": {
                "accuracy_pct": a_acc_pct,
                "status": a_res.get("status", "UNKNOWN"),
                "is_valid": a_valid,
                "original_latency_ms": orig_ms,
                "optimized_latency_ms": a_opt_ms,
                "speedup_ratio": a_speedup,
                "indexes_created": index_created_str,
                "applied_indexes_count": num_indexes,
                "applied_indexes": applied_indexes,
                "retries_needed": attempts,
                "applied_techniques": a_res.get("applied_techniques", [])
            }
        })

    headers = [
        "Query ID",
        "Baseline Acc",
        "Agent Acc",
        "Orig Latency (ms)",
        "Opt Latency (ms)",
        "Speedup Factor",
        "Index Created",
        "Retries"
    ]
    alignments = ["center", "center", "center", "right", "right", "right", "center", "center"]

    table_output = format_table(headers, table_rows, alignments)

    # Print Clean CLI Summary
    log("\n" + "=" * 90)
    log(f"  QUANTITATIVE EVALUATION SUMMARY TABLE ({model_display})")
    log("=" * 90)
    log(table_output)

    log("\n" + "-" * 90)
    log("  AGGREGATE BENCHMARK COMPARISON")
    log("-" * 90)
    log(f"  Total Queries Evaluated       : {len(test_cases)}")
    log(f"  Zero-Shot Baseline Accuracy   : {baseline_summary.get('success_rate_pct', 0.0)}% ({baseline_summary.get('successful_cases', 0)}/{len(test_cases)})")
    log(f"  Multi-Agent Optimizer Accuracy: {agent_summary.get('success_rate_pct', 0.0)}% ({agent_summary.get('successful_cases', 0)}/{len(test_cases)})")
    log(f"  Baseline Average Speedup      : {baseline_summary.get('average_speedup_on_successful', 0.0):.2f}x")
    log(f"  Multi-Agent Average Speedup   : {agent_summary.get('average_speedup_on_verified', 0.0):.2f}x")
    log(f"  Multi-Agent Max Speedup       : {agent_summary.get('max_speedup', 0.0):.2f}x")
    log(f"  Total Indexes Synthesized     : {total_indexes_created}")
    log(f"  Total Iteration Attempts      : {total_retries}")
    log("-" * 90 + "\n")

    # Step 5: Save Artifact 1: evaluation_results.json
    evaluation_dataset = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": model_display,
        "database": str(db_path),
        "total_queries": len(test_cases),
        "summary": {
            "baseline": {
                "total_cases": baseline_summary.get("total_cases", len(test_cases)),
                "successful_cases": baseline_summary.get("successful_cases", 0),
                "mismatch_cases": baseline_summary.get("mismatch_cases", 0),
                "error_cases": baseline_summary.get("error_cases", 0),
                "success_rate_pct": baseline_summary.get("success_rate_pct", 0.0),
                "average_speedup": baseline_summary.get("average_speedup_on_successful", 0.0)
            },
            "agent_optimizer": {
                "total_cases": agent_summary.get("total_cases", len(test_cases)),
                "successful_cases": agent_summary.get("successful_cases", 0),
                "failed_cases": agent_summary.get("failed_cases", 0),
                "success_rate_pct": agent_summary.get("success_rate_pct", 0.0),
                "average_speedup": agent_summary.get("average_speedup_on_verified", 0.0),
                "max_speedup": agent_summary.get("max_speedup", 0.0),
                "total_indexes_created": total_indexes_created,
                "total_iteration_attempts": total_retries
            }
        },
        "comparison_table": comparison_items,
        "baseline_raw_results": baseline_summary,
        "agent_raw_results": agent_summary
    }

    evaluation_results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(evaluation_results_path, "w", encoding="utf-8") as ef:
        json.dump(evaluation_dataset, ef, indent=2)
    log(f"✅ Generated Evaluation Results Artifact: {evaluation_results_path}")

    # Step 6: Save Artifact 2: trajectories.json
    consolidated_trajectories = consolidate_trajectories(trajectories_dir)
    OptimizerOrchestrator.export_trajectories(trajectories_path, consolidated_trajectories)
    log(f"✅ Generated Consolidated Trajectories Artifact: {trajectories_path} ({len(consolidated_trajectories)} execution objects)")
    log("=" * 90 + "\n")

    return evaluation_dataset


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for comparative evaluation suite."""
    parser = argparse.ArgumentParser(
        description="Run comparative evaluation suite: Zero-Shot Baseline vs Multi-Agent Optimizer.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--db-path", type=Path, default=Path("sandbox.db"), help="Path to SQLite database")
    parser.add_argument("--test-cases-path", type=Path, default=Path("test_cases.json"), help="Path to test cases JSON")
    parser.add_argument("--evaluation-results-path", type=Path, default=Path("evaluation_results.json"), help="Output path for evaluation_results.json")
    parser.add_argument("--trajectories-path", type=Path, default=Path("trajectories.json"), help="Output path for trajectories.json")
    parser.add_argument("--trajectories-dir", type=Path, default=Path("trajectories"), help="Directory storing individual trajectory JSONs")
    parser.add_argument("--baseline-results-path", type=Path, default=Path("baseline_results.json"), help="Output path for baseline_results.json")
    parser.add_argument("--agent-results-path", type=Path, default=Path("agent_results.json"), help="Output path for agent_results.json")
    parser.add_argument("--provider", choices=["deepseek", "gemini", "openai", "anthropic", "mock"], default=None, help="LLM Provider to use")
    parser.add_argument("--model", type=str, default=None, help="Model name (e.g. deepseek-chat, gemini-3.6-flash, gpt-4o)")
    parser.add_argument("--api-key", type=str, default=None, help="API key for provider")
    parser.add_argument("--mock", action="store_true", help="Run offline with mock LLM provider")
    parser.add_argument("--timeout", type=float, default=10.0, help="Execution timeout in seconds per query")
    parser.add_argument("--max-retries", type=int, default=3, help="Max retry attempts for multi-agent optimizer")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    return parser.parse_args(args)


def main() -> None:
    """CLI entry point for src/evaluate.py."""
    parsed = parse_args()
    provider = "mock" if parsed.mock else parsed.provider

    try:
        run_evaluation(
            db_path=parsed.db_path,
            test_cases_path=parsed.test_cases_path,
            evaluation_results_path=parsed.evaluation_results_path,
            trajectories_path=parsed.trajectories_path,
            trajectories_dir=parsed.trajectories_dir,
            baseline_results_path=parsed.baseline_results_path,
            agent_results_path=parsed.agent_results_path,
            provider=provider,
            model=parsed.model,
            api_key=parsed.api_key,
            timeout_sec=parsed.timeout,
            max_retries=parsed.max_retries,
            quiet=parsed.quiet
        )
    except Exception as e:
        print(f"Error during comparative evaluation: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
