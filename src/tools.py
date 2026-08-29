"""Deterministic database profiling, query plan analysis, and verification tools.

This module provides the DatabaseSandbox class for analyzing SQLite execution plans,
safely benchmarking queries with timeout controls, managing indexes, and verifying
mathematical and structural equivalence between original and optimized result sets.
"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)


class DatabaseExecutionError(Exception):
    """Raised when query execution or database operation fails or times out."""


class VerificationMismatchError(Exception):
    """Raised when verification between original and optimized result sets fails."""


class DatabaseSandbox:
    """Sandbox environment providing deterministic profiling and verification for SQLite databases."""

    @staticmethod
    def get_schema(db_path: Union[str, Path]) -> str:
        """Extract clean CREATE TABLE and CREATE INDEX DDL statements from the database.

        Args:
            db_path: Path to the SQLite database.

        Returns:
            Formatted DDL string containing all table and index creation statements.

        Raises:
            DatabaseExecutionError: If database connection or schema reading fails.
        """
        path_str = str(db_path)
        if not Path(path_str).exists():
            raise DatabaseExecutionError(f"Database file not found: {path_str}")

        try:
            conn = sqlite3.connect(f"file:{path_str}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type, name, sql
                FROM sqlite_master
                WHERE type IN ('table', 'index')
                  AND name NOT LIKE 'sqlite_%'
                  AND sql IS NOT NULL
                ORDER BY
                    CASE type WHEN 'table' THEN 1 ELSE 2 END,
                    name ASC;
            """)
            rows = cursor.fetchall()
            conn.close()

            ddl_statements: List[str] = []
            for item_type, name, sql in rows:
                clean_sql = sql.strip()
                if not clean_sql.endswith(";"):
                    clean_sql += ";"
                ddl_statements.append(clean_sql)

            schema_ddl = "\n\n".join(ddl_statements)
            logger.debug("Successfully extracted schema from %s (%d statements)", path_str, len(ddl_statements))
            return schema_ddl

        except sqlite3.Error as e:
            logger.error("Failed to extract schema from %s: %s", path_str, e)
            raise DatabaseExecutionError(f"Failed to extract schema: {e}") from e

    @staticmethod
    def get_explain_plan(db_path: Union[str, Path], sql_query: str) -> List[Dict[str, Any]]:
        """Execute EXPLAIN QUERY PLAN and return structured JSON outlining scan types and indexes.

        Args:
            db_path: Path to the SQLite database.
            sql_query: The SQL query to analyze.

        Returns:
            List of structured dictionary nodes detailing each step of the query plan.

        Raises:
            DatabaseExecutionError: If query plan explanation fails.
        """
        path_str = str(db_path)
        if not Path(path_str).exists():
            raise DatabaseExecutionError(f"Database file not found: {path_str}")

        try:
            conn = sqlite3.connect(f"file:{path_str}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {sql_query}")
            plan_rows = cursor.fetchall()
            conn.close()

            structured_plan: List[Dict[str, Any]] = []
            table_regex = re.compile(r"(?:SCAN|SEARCH)\s+(?:TABLE\s+)?([a-zA-Z0-9_]+)", re.IGNORECASE)
            index_regex = re.compile(r"USING\s+(?:COVERING\s+)?INDEX\s+([a-zA-Z0-9_]+)", re.IGNORECASE)

            for row in plan_rows:
                # Format of EXPLAIN QUERY PLAN in SQLite: (id, parent, notused, detail)
                step_id = row[0]
                parent_id = row[1]
                detail = row[3]

                detail_upper = detail.upper()
                is_scan = "SCAN" in detail_upper
                is_search = "SEARCH" in detail_upper
                uses_temp_btree = "USE TEMP B-TREE" in detail_upper or "TEMP B-TREE" in detail_upper
                uses_covering_index = "COVERING INDEX" in detail_upper

                # Determine operation classification
                if is_scan:
                    op_type = "SCAN"
                elif is_search:
                    op_type = "SEARCH"
                elif uses_temp_btree:
                    op_type = "TEMP_BTREE"
                elif "COMPOUND" in detail_upper:
                    op_type = "COMPOUND"
                elif "SUBQUERY" in detail_upper:
                    op_type = "SUBQUERY"
                else:
                    op_type = "OTHER"

                # Extract targeted table and index names if present
                table_match = table_regex.search(detail)
                target_table = table_match.group(1) if table_match else None

                index_match = index_regex.search(detail)
                target_index = index_match.group(1) if index_match else None

                structured_plan.append({
                    "id": step_id,
                    "parent_id": parent_id,
                    "detail": detail,
                    "operation_type": op_type,
                    "table": target_table,
                    "index": target_index,
                    "is_scan": is_scan,
                    "is_search": is_search,
                    "uses_temp_btree": uses_temp_btree,
                    "uses_covering_index": uses_covering_index
                })

            logger.debug("Generated query plan with %d steps for query: %.80s...", len(structured_plan), sql_query)
            return structured_plan

        except sqlite3.Error as e:
            logger.error("Failed to explain query plan for '%s': %s", sql_query, e)
            raise DatabaseExecutionError(f"EXPLAIN QUERY PLAN error: {e}") from e

    @staticmethod
    def execute_query(
        db_path: Union[str, Path],
        sql_query: str,
        timeout_sec: float = 5.0
    ) -> Tuple[List[Tuple[Any, ...]], float]:
        """Execute a query safely with deterministic timeout enforcement and precision timing.

        Args:
            db_path: Path to the SQLite database.
            sql_query: The SQL query to execute.
            timeout_sec: Maximum execution time allowed before aborting (default 5.0s).

        Returns:
            Tuple containing:
                - List of raw result rows as tuples.
                - Execution time in milliseconds (float).

        Raises:
            DatabaseExecutionError: If query fails or exceeds timeout.
        """
        path_str = str(db_path)
        if not Path(path_str).exists():
            raise DatabaseExecutionError(f"Database file not found: {path_str}")

        start_time = time.perf_counter()
        deadline = start_time + timeout_sec
        timed_out = False

        def progress_handler() -> int:
            nonlocal timed_out
            if time.perf_counter() > deadline:
                timed_out = True
                return 1  # Non-zero return interrupts SQLite execution
            return 0

        try:
            conn = sqlite3.connect(f"file:{path_str}?mode=ro", uri=True)
            # Check progress every 1000 SQLite VM instructions
            conn.set_progress_handler(progress_handler, 1000)
            cursor = conn.cursor()

            cursor.execute(sql_query)
            rows = cursor.fetchall()
            conn.close()

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.debug("Executed query in %.3fms returning %d rows", elapsed_ms, len(rows))
            return rows, round(elapsed_ms, 3)

        except sqlite3.OperationalError as e:
            if timed_out or "interrupted" in str(e).lower():
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                raise DatabaseExecutionError(
                    f"Query execution timed out after {timeout_sec:.2f}s ({elapsed_ms:.1f}ms elapsed)"
                ) from e
            raise DatabaseExecutionError(f"Operational error executing query: {e}") from e
        except sqlite3.Error as e:
            raise DatabaseExecutionError(f"Database error executing query: {e}") from e

    @staticmethod
    def apply_index(db_path: Union[str, Path], ddl: str) -> bool:
        """Safely attempt to apply a CREATE INDEX statement to the database.

        Args:
            db_path: Path to the SQLite database.
            ddl: DDL statement creating an index (e.g. 'CREATE INDEX ...').

        Returns:
            True if the index was created successfully.

        Raises:
            DatabaseExecutionError: If DDL syntax is invalid or index creation fails.
        """
        path_str = str(db_path)
        if not Path(path_str).exists():
            raise DatabaseExecutionError(f"Database file not found: {path_str}")

        clean_ddl = ddl.strip()
        if not re.match(r"^CREATE\s+(UNIQUE\s+)?INDEX", clean_ddl, re.IGNORECASE):
            raise DatabaseExecutionError(
                f"Invalid index DDL statement: must begin with CREATE [UNIQUE] INDEX. Received: {ddl}"
            )

        try:
            conn = sqlite3.connect(path_str)
            cursor = conn.cursor()
            cursor.execute(clean_ddl)
            conn.commit()
            conn.close()
            logger.info("Successfully applied index: %s", clean_ddl)
            return True

        except sqlite3.Error as e:
            logger.error("Failed to apply index '%s': %s", clean_ddl, e)
            raise DatabaseExecutionError(f"Failed to create index: {e}") from e

    @staticmethod
    def compare_result_sets(
        original_rows: Sequence[Sequence[Any]],
        optimized_rows: Sequence[Sequence[Any]],
        check_order: bool = False,
        float_rel_tol: float = 1e-5,
        float_abs_tol: float = 1e-7
    ) -> Tuple[bool, str]:
        """Validate mathematical and structural equivalence between two query result sets.

        Args:
            original_rows: Result rows from the baseline query.
            optimized_rows: Result rows from the candidate optimized query.
            check_order: If True, enforces identical row sequence; if False, validates multiset equivalence.
            float_rel_tol: Relative tolerance for floating-point comparisons.
            float_abs_tol: Absolute tolerance for floating-point comparisons.

        Returns:
            Tuple of (is_match: bool, explanation: str).
        """
        # 1. Check row counts
        if len(original_rows) != len(optimized_rows):
            msg = f"Row count mismatch: original produced {len(original_rows)} rows, optimized produced {len(optimized_rows)} rows."
            logger.warning(msg)
            return False, msg

        # Empty sets match
        if len(original_rows) == 0:
            return True, "Result sets match (both are empty)."

        # 2. Check column count on the first row
        orig_cols = len(original_rows[0])
        opt_cols = len(optimized_rows[0])
        if orig_cols != opt_cols:
            msg = f"Column count mismatch: original has {orig_cols} columns, optimized has {opt_cols} columns."
            logger.warning(msg)
            return False, msg

        def values_match(val1: Any, val2: Any) -> bool:
            """Check if two individual cell values match, with floating-point tolerance."""
            if val1 is None or val2 is None:
                return val1 is val2

            # Check if both are numeric (float, int)
            if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                return math.isclose(float(val1), float(val2), rel_tol=float_rel_tol, abs_tol=float_abs_tol)

            # Check if strings could be numeric values
            if isinstance(val1, (int, float, str)) and isinstance(val2, (int, float, str)):
                try:
                    f1 = float(val1)
                    f2 = float(val2)
                    return math.isclose(f1, f2, rel_tol=float_rel_tol, abs_tol=float_abs_tol)
                except (ValueError, TypeError):
                    pass

            return val1 == val2

        def rows_match(r1: Sequence[Any], r2: Sequence[Any]) -> bool:
            """Check if two tuples are element-wise equivalent."""
            if len(r1) != len(r2):
                return False
            return all(values_match(v1, v2) for v1, v2 in zip(r1, r2))

        # 3. Ordered comparison
        if check_order:
            for idx, (r1, r2) in enumerate(zip(original_rows, optimized_rows)):
                if not rows_match(r1, r2):
                    msg = f"Row mismatch at index {idx}:\n  Original:  {r1}\n  Optimized: {r2}"
                    logger.warning(msg)
                    return False, msg
            return True, f"Result sets match perfectly in sequential order ({len(original_rows)} rows)."

        # 4. Unordered multiset comparison
        # Fast path: Try canonical key hash comparison
        def make_canonical_key(row: Sequence[Any]) -> Tuple[Any, ...]:
            key_items = []
            for item in row:
                if isinstance(item, float):
                    key_items.append(round(item, 5))
                elif isinstance(item, int):
                    key_items.append(float(item))
                else:
                    key_items.append(item)
            return tuple(key_items)

        orig_counter = Counter(make_canonical_key(r) for r in original_rows)
        opt_counter = Counter(make_canonical_key(r) for r in optimized_rows)

        if orig_counter == opt_counter:
            return True, f"Result sets match perfectly as multiset ({len(original_rows)} rows)."

        # Slower fallback path: Greedy paired matching handling edge float precision
        unmatched_opt = list(optimized_rows)
        for r_orig in original_rows:
            matched_idx = -1
            for idx, r_opt in enumerate(unmatched_opt):
                if rows_match(r_orig, r_opt):
                    matched_idx = idx
                    break
            if matched_idx != -1:
                unmatched_opt.pop(matched_idx)
            else:
                msg = f"Unmatched row in original results not found in optimized set:\n  {r_orig}"
                logger.warning(msg)
                return False, msg

        if len(unmatched_opt) > 0:
            msg = f"{len(unmatched_opt)} extra row(s) found in optimized results:\n  {unmatched_opt[0]}"
            logger.warning(msg)
            return False, msg

        return True, f"Result sets match equivalence checks ({len(original_rows)} rows)."
