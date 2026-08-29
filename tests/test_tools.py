"""Unit tests for DatabaseSandbox profiling, verification, and execution tools."""

import math
import sqlite3
import pytest
from pathlib import Path
from src.tools import DatabaseExecutionError, DatabaseSandbox, VerificationMismatchError


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with realistic schema and sample rows."""
    db_file = tmp_path / "test_sandbox.db"
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            region TEXT,
            score REAL
        );
        INSERT INTO users (id, name, region, score) VALUES
            (1, 'Alice', 'North America', 95.5),
            (2, 'Bob', 'Europe', 82.3),
            (3, 'Charlie', 'Europe', 74.0),
            (4, 'Diana', 'Asia Pacific', NULL);
    """)
    conn.commit()
    conn.close()
    return db_file


class TestCompareResultSets:
    """Tests for DatabaseSandbox.compare_result_sets."""

    def test_identical_sets(self):
        """Test identical result sets match both ordered and unordered."""
        r1 = [(1, "Alice", 100.5), (2, "Bob", 200.75)]
        r2 = [(1, "Alice", 100.5), (2, "Bob", 200.75)]

        ok_ord, msg_ord = DatabaseSandbox.compare_result_sets(r1, r2, check_order=True)
        assert ok_ord is True
        assert "match" in msg_ord.lower()

        ok_unord, msg_unord = DatabaseSandbox.compare_result_sets(r1, r2, check_order=False)
        assert ok_unord is True

    def test_unordered_sets(self):
        """Test permuted rows match with check_order=False and fail with check_order=True."""
        r1 = [(1, "Alice", 100.0), (2, "Bob", 200.0), (3, "Charlie", 300.0)]
        r2 = [(2, "Bob", 200.0), (3, "Charlie", 300.0), (1, "Alice", 100.0)]

        # Ordered comparison should fail
        ok_ord, msg_ord = DatabaseSandbox.compare_result_sets(r1, r2, check_order=True)
        assert ok_ord is False
        assert "Row mismatch at index" in msg_ord

        # Unordered comparison should pass
        ok_unord, msg_unord = DatabaseSandbox.compare_result_sets(r1, r2, check_order=False)
        assert ok_unord is True
        assert "match" in msg_unord.lower()

    def test_row_count_mismatch(self):
        """Test mismatched row counts are detected and reported."""
        r1 = [(1, "Alice"), (2, "Bob"), (3, "Charlie")]
        r2 = [(1, "Alice"), (2, "Bob")]

        ok, msg = DatabaseSandbox.compare_result_sets(r1, r2)
        assert ok is False
        assert "Row count mismatch: original produced 3 rows, optimized produced 2 rows." in msg

    def test_column_count_mismatch(self):
        """Test mismatched column counts are detected and reported."""
        r1 = [(1, "Alice", "USA")]
        r2 = [(1, "Alice")]

        ok, msg = DatabaseSandbox.compare_result_sets(r1, r2)
        assert ok is False
        assert "Column count mismatch: original has 3 columns, optimized has 2 columns." in msg

    def test_float_rounding_differences(self):
        """Test floating-point comparison within tolerance passes, and exceeding tolerance fails."""
        # Within standard tolerance (rel_tol=1e-5)
        r1 = [(1, 100.500000), (2, 200.123456)]
        r2 = [(1, 100.500001), (2, 200.123458)]
        ok, msg = DatabaseSandbox.compare_result_sets(r1, r2, float_rel_tol=1e-4)
        assert ok is True

        # Exceeding tolerance
        r3 = [(1, 100.500000), (2, 205.000000)]
        ok_fail, msg_fail = DatabaseSandbox.compare_result_sets(r1, r3)
        assert ok_fail is False

    def test_null_value_handling(self):
        """Test NULL / None value comparison across ordered and unordered sets."""
        r1 = [(1, "Diana", None), (2, "Eve", 50.0)]
        r2 = [(1, "Diana", None), (2, "Eve", 50.0)]
        ok, _ = DatabaseSandbox.compare_result_sets(r1, r2, check_order=True)
        assert ok is True

        # Unordered with None
        r2_perm = [(2, "Eve", 50.0), (1, "Diana", None)]
        ok_perm, _ = DatabaseSandbox.compare_result_sets(r1, r2_perm, check_order=False)
        assert ok_perm is True

        # None vs 0 or empty string should NOT match
        r_zero = [(1, "Diana", 0), (2, "Eve", 50.0)]
        ok_zero, msg_zero = DatabaseSandbox.compare_result_sets(r1, r_zero)
        assert ok_zero is False

    def test_empty_sets(self):
        """Test empty result sets match cleanly."""
        ok, msg = DatabaseSandbox.compare_result_sets([], [])
        assert ok is True
        assert "empty" in msg.lower()


class TestGetExplainPlan:
    """Tests for DatabaseSandbox.get_explain_plan."""

    def test_explain_plan_full_scan(self, temp_db: Path):
        """Test query plan detects SCAN on unindexed table."""
        plan = DatabaseSandbox.get_explain_plan(temp_db, "SELECT * FROM users WHERE region = 'Europe';")
        assert len(plan) > 0
        scan_step = plan[0]
        assert scan_step["is_scan"] is True
        assert scan_step["table"] == "users"
        assert scan_step["operation_type"] == "SCAN"

    def test_explain_plan_search_index(self, temp_db: Path):
        """Test query plan detects SEARCH ... USING INDEX after index creation."""
        DatabaseSandbox.apply_index(temp_db, "CREATE INDEX idx_users_region ON users (region);")
        plan = DatabaseSandbox.get_explain_plan(temp_db, "SELECT * FROM users WHERE region = 'Europe';")
        assert len(plan) > 0
        search_step = plan[0]
        assert search_step["is_search"] is True
        assert search_step["table"] == "users"
        assert search_step["index"] == "idx_users_region"
        assert search_step["operation_type"] == "SEARCH"

    def test_explain_plan_temp_btree(self, temp_db: Path):
        """Test query plan detects USE TEMP B-TREE for unindexed sorting."""
        plan = DatabaseSandbox.get_explain_plan(temp_db, "SELECT region, count(*) FROM users GROUP BY region ORDER BY count(*) DESC;")
        has_temp_btree = any(step.get("uses_temp_btree") for step in plan)
        assert has_temp_btree is True


class TestExecuteQueryTimeout:
    """Tests for DatabaseSandbox.execute_query and timeout controls."""

    def test_successful_query_execution(self, temp_db: Path):
        """Test fast execution returns valid rows and timing in milliseconds."""
        rows, elapsed_ms = DatabaseSandbox.execute_query(temp_db, "SELECT name, region FROM users ORDER BY id;")
        assert len(rows) == 4
        assert rows[0] == ("Alice", "North America")
        assert elapsed_ms >= 0.0

    def test_query_timeout_interruption(self, temp_db: Path):
        """Test runaway infinite recursive query is aborted by timeout handler."""
        runaway_sql = (
            "WITH RECURSIVE cnt(x) AS ( "
            "    SELECT 1 "
            "    UNION ALL "
            "    SELECT x + 1 FROM cnt "
            ") "
            "SELECT count(*) FROM cnt;"
        )
        with pytest.raises(DatabaseExecutionError) as exc_info:
            DatabaseSandbox.execute_query(temp_db, runaway_sql, timeout_sec=0.25)
        assert "timed out" in str(exc_info.value).lower()

    def test_nonexistent_database_raises_error(self, tmp_path: Path):
        """Test querying nonexistent database raises DatabaseExecutionError."""
        missing_db = tmp_path / "does_not_exist.db"
        with pytest.raises(DatabaseExecutionError):
            DatabaseSandbox.execute_query(missing_db, "SELECT 1;")


class TestApplyIndex:
    """Tests for DatabaseSandbox.apply_index."""

    def test_apply_valid_index(self, temp_db: Path):
        """Test creating a valid single and composite index."""
        applied = DatabaseSandbox.apply_index(temp_db, "CREATE INDEX idx_users_score ON users (score);")
        assert applied is True

        schema = DatabaseSandbox.get_schema(temp_db)
        assert "idx_users_score" in schema

    def test_apply_invalid_ddl_statement(self, temp_db: Path):
        """Test non-CREATE INDEX statements are rejected with DatabaseExecutionError."""
        with pytest.raises(DatabaseExecutionError) as exc_info:
            DatabaseSandbox.apply_index(temp_db, "DROP TABLE users;")
        assert "must begin with CREATE [UNIQUE] INDEX" in str(exc_info.value)

    def test_apply_syntax_error_index(self, temp_db: Path):
        """Test SQL syntax errors during index creation raise DatabaseExecutionError."""
        with pytest.raises(DatabaseExecutionError) as exc_info:
            DatabaseSandbox.apply_index(temp_db, "CREATE INDEX idx_invalid ON nonexistent_table (col1);")
        assert "Failed to create index" in str(exc_info.value)
