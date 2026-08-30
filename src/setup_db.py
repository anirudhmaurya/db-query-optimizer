"""Database initialization and benchmark query generation module.

This module sets up a SQLite sandbox database with realistic schemas,
foreign keys, and synthetic data for database query optimization benchmarks.
It also outputs a curated test suite of unoptimized SQL queries demonstrating
common database performance anti-patterns.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DatabaseConfig:
    """Configuration options and data scale counts for database generation."""

    db_path: Path = Path("sandbox.db")
    test_cases_path: Path = Path("test_cases.json")
    num_users: int = 10_000
    num_orders: int = 25_000
    num_order_items: int = 50_000
    num_events: int = 40_000
    num_departments: int = 20
    num_employees: int = 5_000
    batch_size: int = 5_000
    seed: int = 42
    force: bool = False
    quiet: bool = False


# Realistic data pools for synthetic generator
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra", "Donald", "Ashley",
    "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle",
    "Kenneth", "Carol", "Kevin", "Amanda", "Brian", "Melissa", "George", "Deborah",
    "Timothy", "Stephanie", "Ronald", "Rebecca", "Jason", "Sharon", "Edward", "Laura",
    "Jeffrey", "Cynthia", "Ryan", "Dorothy", "Jacob", "Amy", "Gary", "Kathleen",
    "Nicholas", "Angela", "Eric", "Shirley", "Jonathan", "Emma", "Stephen", "Brenda",
    "Larry", "Pamela", "Justin", "Nicole", "Scott", "Anna", "Brandon", "Samantha",
    "Benjamin", "Katherine", "Samuel", "Christine", "Gregory", "Debra", "Alexander", "Rachel",
    "Patrick", "Carolyn", "Frank", "Janet", "Raymond", "Maria", "Jack", "Heather",
    "Dennis", "Diane", "Jerry", "Julie", "Tyler", "Joyce", "Aaron", "Victoria"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas",
    "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
    "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young",
    "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Gomez", "Phillips", "Evans", "Turner", "Diaz", "Parker",
    "Cruz", "Edwards", "Collins", "Reyes", "Stewart", "Morris", "Morales", "Murphy",
    "Cook", "Rogers", "Gutierrez", "Ortiz", "Morgan", "Cooper", "Peterson", "Bailey",
    "Reed", "Kelly", "Howard", "Ramos", "Kim", "Cox", "Ward", "Richardson",
    "Watson", "Brooks", "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza",
    "Ruiz", "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers",
    "Long", "Ross", "Foster", "Jimenez", "Powell", "Jenkins", "Perry", "Russell"
]

REGIONS = [
    "North America",
    "Europe",
    "Asia Pacific",
    "Latin America",
    "Middle East & Africa",
]

ORDER_STATUSES = ["completed", "pending", "shipped", "cancelled", "refunded"]

EVENT_TYPES = [
    "page_view",
    "add_to_cart",
    "checkout_initiated",
    "checkout_completed",
    "search",
    "user_login",
    "user_signup",
    "system_error",
    "review_posted",
    "coupon_applied"
]

DEPARTMENT_NAMES = [
    "Engineering", "Infrastructure", "Product Management", "Quality Assurance",
    "Data Science", "Security", "DevOps", "Sales - Enterprise", "Sales - SMB",
    "Marketing - Digital", "Marketing - Brand", "Customer Support", "Customer Success",
    "Human Resources", "Finance & Accounting", "Legal & Compliance",
    "Supply Chain & Logistics", "Procurement", "Business Operations", "Executive"
]

DEVICE_TYPES = ["desktop_chrome", "desktop_safari", "mobile_ios", "mobile_android", "tablet_ipad"]


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the SQLite database schema with foreign keys and integrity constraints.

    Args:
        conn: An active SQLite database connection.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Drop existing tables in reverse dependency order if any
    cursor.executescript("""
    DROP TABLE IF EXISTS order_items;
    DROP TABLE IF EXISTS events;
    DROP TABLE IF EXISTS orders;
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS employees;
    DROP TABLE IF EXISTS departments;
    """)

    # Create tables with explicit primary keys, column types, and foreign keys
    cursor.executescript("""
    CREATE TABLE departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_name TEXT NOT NULL,
        budget REAL NOT NULL CHECK (budget >= 0)
    );

    CREATE TABLE employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        salary REAL NOT NULL CHECK (salary >= 0),
        hire_date TEXT NOT NULL,
        FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE CASCADE
    );

    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        region TEXT NOT NULL,
        signup_date TEXT NOT NULL
    );

    CREATE TABLE orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL NOT NULL CHECK (amount >= 0),
        status TEXT NOT NULL,
        order_date TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );

    CREATE TABLE order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL CHECK (quantity > 0),
        unit_price REAL NOT NULL CHECK (unit_price >= 0),
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    );

    CREATE TABLE events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)
    conn.commit()


def random_date(rng: random.Random, start_year: int = 2023, end_year: int = 2026) -> str:
    """Generate a random ISO format date string between start_year and end_year."""
    start = datetime(start_year, 1, 1, 0, 0, 0)
    end = datetime(end_year, 8, 1, 23, 59, 59)
    delta_seconds = int((end - start).total_seconds())
    offset = rng.randint(0, delta_seconds)
    random_dt = start + timedelta(seconds=offset)
    return random_dt.strftime("%Y-%m-%d %H:%M:%S")


def populate_data(
    conn: sqlite3.Connection,
    config: DatabaseConfig,
    log_func: Optional[Any] = None
) -> Dict[str, int]:
    """Populate database tables with realistic synthetic data using batch transactions.

    Args:
        conn: An active SQLite database connection.
        config: Database configuration containing counts and batching parameters.
        log_func: Optional logging/callback function for progress reporting.

    Returns:
        Dictionary containing counts of inserted rows per table.
    """
    if log_func is None:
        log_func = print if not config.quiet else lambda *args, **kwargs: None

    rng = random.Random(config.seed)
    cursor = conn.cursor()

    # Optimization pragmas for high-throughput initial population
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA journal_mode = MEMORY;")
    cursor.execute("PRAGMA foreign_keys = OFF;")  # temporarily disable during bulk insert

    row_counts: Dict[str, int] = {}

    # 1. Departments
    log_func(f"Populating departments ({config.num_departments:,} records)...")
    dept_records: List[Tuple[int, str, float]] = []
    for i in range(1, config.num_departments + 1):
        dept_name = DEPARTMENT_NAMES[(i - 1) % len(DEPARTMENT_NAMES)]
        if i > len(DEPARTMENT_NAMES):
            dept_name = f"{dept_name} {i // len(DEPARTMENT_NAMES) + 1}"
        budget = round(rng.uniform(100_000.0, 5_000_000.0), 2)
        dept_records.append((i, dept_name, budget))

    cursor.executemany(
        "INSERT INTO departments (id, dept_name, budget) VALUES (?, ?, ?);",
        dept_records
    )
    conn.commit()
    row_counts["departments"] = len(dept_records)

    # 2. Employees
    log_func(f"Populating employees ({config.num_employees:,} records)...")
    emp_records: List[Tuple[int, int, str, float, str]] = []
    for i in range(1, config.num_employees + 1):
        dept_id = rng.randint(1, config.num_departments)
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        salary = round(rng.gauss(85_000.0, 25_000.0), 2)
        salary = max(35_000.0, min(300_000.0, salary))  # clamp
        hire_date = random_date(rng, 2020, 2026)
        emp_records.append((i, dept_id, name, salary, hire_date))

    # Guarantee identical top salaries (ties) within each department for TC-13 (Top-Record Tie Trap)
    dept_to_indices: Dict[int, List[int]] = {}
    for idx, emp in enumerate(emp_records):
        dept_to_indices.setdefault(emp[1], []).append(idx)

    for dept_id, indices in dept_to_indices.items():
        if len(indices) >= 2:
            top_salary = 280_000.00 + (dept_id * 500.0)
            # Give top 2 employees in this department the exact same max salary
            for top_idx in indices[:2]:
                e = emp_records[top_idx]
                emp_records[top_idx] = (e[0], e[1], e[2], top_salary, e[4])

    for chunk_start in range(0, len(emp_records), config.batch_size):
        chunk = emp_records[chunk_start : chunk_start + config.batch_size]
        cursor.executemany(
            "INSERT INTO employees (id, department_id, name, salary, hire_date) VALUES (?, ?, ?, ?, ?);",
            chunk
        )
    conn.commit()
    row_counts["employees"] = len(emp_records)

    # 3. Users
    log_func(f"Populating users ({config.num_users:,} records)...")
    user_records: List[Tuple[int, str, str, str]] = []
    for i in range(1, config.num_users + 1):
        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        region = rng.choice(REGIONS)
        signup_date = random_date(rng, 2023, 2026)
        user_records.append((i, name, region, signup_date))

    for chunk_start in range(0, len(user_records), config.batch_size):
        chunk = user_records[chunk_start : chunk_start + config.batch_size]
        cursor.executemany(
            "INSERT INTO users (id, name, region, signup_date) VALUES (?, ?, ?, ?);",
            chunk
        )
    conn.commit()
    row_counts["users"] = len(user_records)

    # 4. Orders
    log_func(f"Populating orders ({config.num_orders:,} records)...")
    # Reserve top 15% of users (e.g. user_id > 8,500) to NEVER have orders.
    # This guarantees at least 1,500 users with ZERO orders to test The NULL Trap!
    order_user_pool_max = int(config.num_users * 0.85)
    order_records: List[Tuple[int, Optional[int], float, str, str]] = []
    for i in range(1, config.num_orders + 1):
        # Insert rows with NULL user_id for Three-Valued Logic Trap (TC-12)
        if i <= 500:
            user_id = None
        else:
            user_id = rng.randint(1, order_user_pool_max)
        amount = round(rng.uniform(15.0, 1500.0), 2)
        status = rng.choices(
            ORDER_STATUSES,
            weights=[0.60, 0.15, 0.12, 0.08, 0.05],
            k=1
        )[0]
        order_date = random_date(rng, 2023, 2026)
        order_records.append((i, user_id, amount, status, order_date))

    for chunk_start in range(0, len(order_records), config.batch_size):
        chunk = order_records[chunk_start : chunk_start + config.batch_size]
        cursor.executemany(
            "INSERT INTO orders (id, user_id, amount, status, order_date) VALUES (?, ?, ?, ?, ?);",
            chunk
        )
    conn.commit()
    row_counts["orders"] = len(order_records)

    # 5. Order Items
    log_func(f"Populating order_items ({config.num_order_items:,} records)...")
    order_item_records: List[Tuple[int, int, int, int, float]] = []
    for i in range(1, config.num_order_items + 1):
        order_id = rng.randint(1, config.num_orders)
        product_id = rng.randint(1, 500)
        quantity = rng.choices([1, 2, 3, 4, 5, 10], weights=[0.5, 0.25, 0.12, 0.06, 0.04, 0.03], k=1)[0]
        unit_price = round(rng.uniform(5.0, 350.0), 2)
        order_item_records.append((i, order_id, product_id, quantity, unit_price))

    for chunk_start in range(0, len(order_item_records), config.batch_size):
        chunk = order_item_records[chunk_start : chunk_start + config.batch_size]
        cursor.executemany(
            "INSERT INTO order_items (id, order_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?, ?);",
            chunk
        )
    conn.commit()
    row_counts["order_items"] = len(order_item_records)

    # 6. Events
    log_func(f"Populating events ({config.num_events:,} records)...")
    event_records: List[Tuple[int, int, str, str, str]] = []
    for i in range(1, config.num_events + 1):
        user_id = rng.randint(1, config.num_users)
        event_type = rng.choice(EVENT_TYPES)
        created_at = random_date(rng, 2024, 2026)
        
        # Realistic JSON payload
        status_code = rng.choice([200, 200, 200, 201, 400, 403, 404, 500])
        payload_data = {
            "device": rng.choice(DEVICE_TYPES),
            "ip_address": f"192.168.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
            "session_id": f"sess_{rng.randint(100000, 999999)}",
            "response_status": status_code,
            "latency_ms": rng.randint(10, 850),
            "error_code": status_code if status_code >= 400 else None,
            "status": "failed" if status_code >= 400 else "success"
        }
        payload = json.dumps(payload_data)
        event_records.append((i, user_id, event_type, created_at, payload))

    for chunk_start in range(0, len(event_records), config.batch_size):
        chunk = event_records[chunk_start : chunk_start + config.batch_size]
        cursor.executemany(
            "INSERT INTO events (id, user_id, event_type, created_at, payload) VALUES (?, ?, ?, ?, ?);",
            chunk
        )
    conn.commit()
    row_counts["events"] = len(event_records)

    # Restore standard pragmas and verify integrity
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    conn.commit()

    return row_counts


def get_benchmark_test_cases() -> List[Dict[str, Any]]:
    """Return 10 distinct, complex unoptimized SQL queries representing classic anti-patterns."""
    return [
        {
            "id": "TC-01",
            "name": "multi_table_nested_loop_no_composite_index",
            "anti_pattern": "Multi-table nested loop joins without composite indexes",
            "description": "Joins users, orders, and order_items filtering on region, order status, and item quantity without supporting multi-column indexes, causing repetitive nested full scans.",
            "tables_involved": ["users", "orders", "order_items"],
            "query": (
                "SELECT u.id AS user_id, u.name, u.region, o.id AS order_id, o.amount, oi.product_id, oi.quantity, oi.unit_price "
                "FROM users u "
                "JOIN orders o ON u.id = o.user_id "
                "JOIN order_items oi ON o.id = oi.order_id "
                "WHERE u.region = 'North America' "
                "  AND o.status = 'completed' "
                "  AND oi.quantity >= 3 "
                "  AND oi.unit_price > 50.0 "
                "ORDER BY o.amount DESC "
                "LIMIT 50;"
            ),
            "expected_anti_pattern_explanation": "Performs exhaustive nested loop joins and sequential scans on unindexed foreign keys and filter columns (users.region, orders.status, order_items.order_id).",
            "optimization_hint": "Create composite indexes on (user_id, status) on orders and (order_id, quantity, unit_price) on order_items, or filter with indexed covering columns."
        },
        {
            "id": "TC-02",
            "name": "non_sargable_date_trap",
            "anti_pattern": "The Non-SARGable Trap: Date formatting function strftime() in WHERE clause",
            "description": "Filters events by extracting the year using strftime('%Y', created_at) = '2025', preventing SQLite from utilizing B-Tree range indexes on the created_at column.",
            "tables_involved": ["events"],
            "query": (
                "SELECT user_id, event_type, COUNT(*) AS event_count "
                "FROM events "
                "WHERE strftime('%Y', created_at) = '2025' "
                "GROUP BY user_id, event_type "
                "HAVING COUNT(*) >= 1 "
                "ORDER BY event_count DESC "
                "LIMIT 25;"
            ),
            "expected_anti_pattern_explanation": "Wrapping created_at inside strftime() forces a full table scan and function evaluation for every single row in the table.",
            "optimization_hint": "Rewrite to standard SARGable range predicate: `created_at >= '2025-01-01 00:00:00' AND created_at < '2026-01-01 00:00:00'` with an index on `(created_at, event_type)`."
        },
        {
            "id": "TC-03",
            "name": "correlated_math_trap_department_salary",
            "anti_pattern": "The Correlated Math Trap: Quadratic correlated subquery calculating department average salary in WHERE clause",
            "description": "Finds employees who make more than their department's average salary using a correlated subquery in the WHERE clause, causing O(N^2) repeated scans across departments.",
            "tables_involved": ["employees", "departments"],
            "query": (
                "SELECT e.id, e.name, e.department_id, e.salary, "
                "       (SELECT AVG(e2.salary) FROM employees e2 WHERE e2.department_id = e.department_id) AS dept_avg_salary "
                "FROM employees e "
                "WHERE e.salary > ( "
                "    SELECT AVG(e3.salary) * 1.15 "
                "    FROM employees e3 "
                "    WHERE e3.department_id = e.department_id "
                ") "
                "ORDER BY e.salary DESC;"
            ),
            "expected_anti_pattern_explanation": "Executes the inner department aggregate twice per employee row, leading to 10,000+ repetitive table scans instead of a single grouping pass.",
            "optimization_hint": "Use window functions like `AVG(salary) OVER(PARTITION BY department_id)` or compute department stats once in a CTE/derived table and JOIN."
        },
        {
            "id": "TC-04",
            "name": "unindexed_wildcard_search",
            "anti_pattern": "Unindexed LIKE with leading wildcard on JSON payload and names",
            "description": "Searches unindexed JSON string payloads using leading wildcard `LIKE '%\"status\": \"failed\"%'` combined with wildcard name matching.",
            "tables_involved": ["events", "users"],
            "query": (
                "SELECT e.id AS event_id, e.user_id, u.name, e.event_type, e.created_at, e.payload "
                "FROM events e "
                "JOIN users u ON e.user_id = u.id "
                "WHERE e.payload LIKE '%\"status\": \"failed\"%' "
                "  AND e.payload LIKE '%\"response_status\": 500%' "
                "  AND u.name LIKE '%Smith%' "
                "ORDER BY e.created_at DESC "
                "LIMIT 50;"
            ),
            "expected_anti_pattern_explanation": "Leading wildcard patterns (%term) bypass standard B-Tree index lookups, forcing full text scans and JSON pattern matching on every record.",
            "optimization_hint": "Extract JSON attributes into dedicated indexed columns (or generated columns with json_extract in SQLite) and use structured predicates."
        },
        {
            "id": "TC-05",
            "name": "heavy_aggregation_on_unindexed_predicate",
            "anti_pattern": "Heavy aggregations on unindexed filter predicates",
            "description": "Performs multi-column aggregation across users and orders with unindexed date and amount thresholds, requiring temp tables and unindexed sorting.",
            "tables_involved": ["users", "orders"],
            "query": (
                "SELECT u.region, o.status, "
                "       COUNT(o.id) AS total_orders, "
                "       AVG(o.amount) AS avg_order_amount, "
                "       SUM(o.amount) AS total_revenue "
                "FROM orders o "
                "JOIN users u ON o.user_id = u.id "
                "WHERE o.amount >= 200.0 "
                "  AND o.order_date >= '2024-01-01' "
                "GROUP BY u.region, o.status "
                "HAVING SUM(o.amount) > 25000.0 "
                "ORDER BY total_revenue DESC;"
            ),
            "expected_anti_pattern_explanation": "Scans orders table without composite index on (order_date, amount, user_id), joins users via scan, and populates unindexed B-Tree aggregation groups in memory/temp disk.",
            "optimization_hint": "Add composite covering index on `orders(order_date, amount, user_id, status)`."
        },
        {
            "id": "TC-06",
            "name": "null_trap_users_without_orders",
            "anti_pattern": "The NULL Trap: Unindexed LEFT JOIN filtering for NULL right-table keys",
            "description": "Finds users who have never placed an order using a LEFT JOIN on orders and WHERE orders.id IS NULL. Basic LLMs often rewrite this to an INNER JOIN for speed, which returns 0 rows and fails accuracy.",
            "tables_involved": ["users", "orders"],
            "query": (
                "SELECT u.id, u.name, u.region, u.signup_date "
                "FROM users u "
                "LEFT JOIN orders o ON u.id = o.user_id "
                "WHERE o.id IS NULL "
                "ORDER BY u.id ASC "
                "LIMIT 50;"
            ),
            "expected_anti_pattern_explanation": "Performs full outer join scan without an index on orders.user_id, evaluating join matches before filtering for NULL right keys.",
            "optimization_hint": "Create index on `orders(user_id)` or rewrite to `NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)` with index support."
        },
        {
            "id": "TC-07",
            "name": "correlated_exists_vs_indexed_join",
            "anti_pattern": "Correlated EXISTS subquery with non-indexed filter conditions",
            "description": "Evaluates correlated EXISTS subquery for each user against orders table with multi-condition checks.",
            "tables_involved": ["users", "orders"],
            "query": (
                "SELECT u.id, u.name, u.region, u.signup_date "
                "FROM users u "
                "WHERE EXISTS ( "
                "    SELECT 1 FROM orders o "
                "    WHERE o.user_id = u.id "
                "      AND o.status = 'completed' "
                "      AND o.amount > 750.0 "
                "      AND o.order_date >= '2025-01-01' "
                ") "
                "ORDER BY u.id ASC "
                "LIMIT 100;"
            ),
            "expected_anti_pattern_explanation": "Executes 10,000 subqueries scanning the orders table per user without composite indexing on (user_id, status, amount, order_date).",
            "optimization_hint": "Convert to an inner JOIN with DISTINCT / GROUP BY on an indexed derived table or index `orders(user_id, status, order_date, amount)`."
        },
        {
            "id": "TC-08",
            "name": "unindexed_sort_pagination_scan",
            "anti_pattern": "Unindexed order by and pagination scan on filtered event types",
            "description": "Performs pagination query with ORDER BY created_at DESC and event_type filter across large unindexed events table.",
            "tables_involved": ["events"],
            "query": (
                "SELECT id, user_id, event_type, created_at, payload "
                "FROM events "
                "WHERE event_type = 'checkout_initiated' "
                "ORDER BY created_at DESC "
                "LIMIT 50 OFFSET 1000;"
            ),
            "expected_anti_pattern_explanation": "SQLite must scan all matching rows, load them into a temporary sorting B-Tree / memory sort buffer, sort everything, and discard the first 1000 rows.",
            "optimization_hint": "Create composite index `idx_events_type_created ON events (event_type, created_at DESC)` and use keyset pagination instead of high OFFSET."
        },
        {
            "id": "TC-09",
            "name": "multi_level_correlated_subquery_ranking",
            "anti_pattern": "Correlated subquery ranking simulation instead of DENSE_RANK()",
            "description": "Simulates Top-N salary ranking per department using correlated COUNT subquery on employees table.",
            "tables_involved": ["employees", "departments"],
            "query": (
                "SELECT e.id, e.name, d.dept_name, e.salary "
                "FROM employees e "
                "JOIN departments d ON e.department_id = d.id "
                "WHERE ( "
                "    SELECT COUNT(*) "
                "    FROM employees e2 "
                "    WHERE e2.department_id = e.department_id "
                "      AND e2.salary > e.salary "
                ") < 3 "
                "ORDER BY d.dept_name ASC, e.salary DESC;"
            ),
            "expected_anti_pattern_explanation": "Executes N subqueries comparing salary against every other employee in the same department (quadratic complexity per department).",
            "optimization_hint": "Use modern Window Function `DENSE_RANK() OVER (PARTITION BY department_id ORDER BY salary DESC)` in a CTE."
        },
        {
            "id": "TC-10",
            "name": "unindexed_computed_expression_aggregation",
            "anti_pattern": "Heavy unindexed computed arithmetic join with multi-level grouping",
            "description": "Joins order_items and orders with arithmetic expressions (quantity * unit_price) inside WHERE and aggregate expressions without generated column indexes.",
            "tables_involved": ["order_items", "orders"],
            "query": (
                "SELECT oi.product_id, "
                "       COUNT(DISTINCT oi.order_id) AS total_distinct_orders, "
                "       SUM(oi.quantity) AS total_units_sold, "
                "       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_sales_value, "
                "       ROUND(AVG(oi.unit_price), 2) AS avg_unit_price "
                "FROM order_items oi "
                "JOIN orders o ON oi.order_id = o.id "
                "WHERE (oi.quantity * oi.unit_price) >= 150.0 "
                "  AND o.status NOT IN ('cancelled', 'refunded') "
                "GROUP BY oi.product_id "
                "HAVING SUM(oi.quantity * oi.unit_price) > 5000.0 "
                "ORDER BY total_sales_value DESC "
                "LIMIT 25;"
            ),
            "expected_anti_pattern_explanation": "Scans both order_items and orders, computes row-by-row multiplications dynamically during scan, and groups product IDs in temporary tables.",
            "optimization_hint": "Store computed line totals in a generated column with an index, or pre-index `order_items(order_id, product_id, quantity, unit_price)`."
        },
        {
            "id": "TC-11",
            "name": "fan_out_trap_duplicate_aggregation",
            "anti_pattern": "The Fan-Out Trap: Unnested multi-table join causing metric inflation",
            "description": "Calculates total user spending and total items ordered across users, orders, and order_items. Naive join without pre-aggregation multiplies order amounts by the count of items in each order.",
            "tables_involved": [
                "users",
                "orders",
                "order_items"
            ],
            "query": (
                "SELECT u.id, SUM(o.amount) as total_spent, COUNT(oi.id) as total_items "
                "FROM users u "
                "JOIN orders o ON u.id = o.user_id "
                "JOIN order_items oi ON o.id = oi.order_id "
                "GROUP BY u.id;"
            ),
            "expected_anti_pattern_explanation": "A naive LLM refactoring without CTE pre-aggregation will double/triple total_spent due to duplicate order_item rows.",
            "optimization_hint": "Pre-aggregate order_items counts per order in a CTE or derived table before joining orders and aggregating per user."
        },
        {
            "id": "TC-12",
            "name": "three_valued_logic_null_trap",
            "anti_pattern": "The Three-Valued Logic Trap: NULL foreign keys breaking NOT IN anti-joins",
            "description": "Finds users who have never placed an order using NOT EXISTS. Rewriting to NOT IN fails when orders table contains NULL user_id rows due to SQL three-valued logic returning UNKNOWN/empty result set.",
            "tables_involved": [
                "users",
                "orders"
            ],
            "query": (
                "SELECT u.id, u.name FROM users u "
                "WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id);"
            ),
            "expected_anti_pattern_explanation": "A zero-shot model rewriting this to WHERE u.id NOT IN (SELECT user_id FROM orders) will return 0 rows in SQLite because of the NULL values.",
            "optimization_hint": "Use indexed NOT EXISTS or LEFT JOIN WHERE o.id IS NULL or explicitly add WHERE user_id IS NOT NULL to NOT IN subqueries."
        },
        {
            "id": "TC-13",
            "name": "top_record_tie_trap_max_salary",
            "anti_pattern": "The Top-Record Tie Trap: Correlated MAX() subquery with multiple top-earner ties",
            "description": "Returns all employees who earn the highest salary in their department using a correlated subquery. Naive rewrites using ROW_NUMBER() = 1 drop ties arbitrarily, whereas DENSE_RANK() or window CTEs preserve all tied top earners.",
            "tables_involved": [
                "employees"
            ],
            "query": (
                "SELECT e.id, e.department_id, e.salary "
                "FROM employees e "
                "WHERE e.salary = (SELECT MAX(salary) FROM employees WHERE department_id = e.department_id);"
            ),
            "expected_anti_pattern_explanation": "Naive rewrites using ROW_NUMBER() arbitrarily drop tied top-earners unless DENSE_RANK() or window CTEs are correctly constructed.",
            "optimization_hint": "Use DENSE_RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) in a CTE or window MAX() to retain all tied top earners efficiently."
        }
    ]


def export_test_cases(output_path: Path) -> None:
    """Export the benchmark test cases to a JSON file.

    Args:
        output_path: Target path for the output JSON file.
    """
    test_cases = get_benchmark_test_cases()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": "1.0.0",
                "description": "Benchmark test cases of unoptimized SQL queries for database query optimization engine.",
                "total_cases": len(test_cases),
                "test_cases": test_cases
            },
            f,
            indent=2
        )


def setup_database(config: DatabaseConfig) -> Dict[str, Any]:
    """Orchestrate schema creation, synthetic data population, and test cases generation.

    Args:
        config: Database configuration settings.

    Returns:
        Summary dictionary containing database stats and execution metrics.
    """
    start_time = time.perf_counter()

    db_path = Path(config.db_path)
    test_cases_path = Path(config.test_cases_path)

    if db_path.exists():
        if config.force:
            if not config.quiet:
                print(f"Removing existing database at {db_path}...")
            db_path.unlink()
        else:
            raise FileExistsError(
                f"Database file '{db_path}' already exists. "
                "Use --force to overwrite it."
            )

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not config.quiet:
        print(f"Connecting to SQLite database: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        if not config.quiet:
            print("Creating database schema with foreign keys and constraints...")
        create_schema(conn)

        row_counts = populate_data(conn, config)

        if not config.quiet:
            print(f"Generating benchmark test cases file: {test_cases_path}")
        export_test_cases(test_cases_path)

    finally:
        conn.close()

    elapsed_time = time.perf_counter() - start_time
    file_size_mb = db_path.stat().st_size / (1024 * 1024)

    summary = {
        "db_path": str(db_path),
        "test_cases_path": str(test_cases_path),
        "file_size_mb": round(file_size_mb, 2),
        "elapsed_seconds": round(elapsed_time, 3),
        "row_counts": row_counts,
        "total_rows": sum(row_counts.values())
    }

    if not config.quiet:
        print("\n" + "=" * 50)
        print("DATABASE INITIALIZATION SUMMARY")
        print("=" * 50)
        print(f"Database File   : {summary['db_path']} ({summary['file_size_mb']} MB)")
        print(f"Test Cases File : {summary['test_cases_path']}")
        print(f"Total Rows      : {summary['total_rows']:,}")
        for table, count in row_counts.items():
            print(f"  - {table:<15}: {count:,} rows")
        print(f"Completed in    : {summary['elapsed_seconds']:.3f} seconds")
        print("=" * 50 + "\n")

    return summary


def parse_args(args: Optional[List[str]] = None) -> DatabaseConfig:
    """Parse command-line arguments and construct a DatabaseConfig object.

    Args:
        args: List of command-line argument strings, or None to use sys.argv.

    Returns:
        Configured DatabaseConfig instance.
    """
    parser = argparse.ArgumentParser(
        description="Initialize SQLite benchmark database and generate test queries.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("sandbox.db"),
        help="Path to SQLite database file"
    )
    parser.add_argument(
        "--test-cases-path",
        type=Path,
        default=Path("test_cases.json"),
        help="Path to output test cases JSON file"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible synthetic data generation"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing database file if it exists"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress console progress output"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scaling factor for record counts"
    )
    parser.add_argument(
        "--users",
        type=int,
        default=10_000,
        help="Number of users to generate"
    )
    parser.add_argument(
        "--orders",
        type=int,
        default=25_000,
        help="Number of orders to generate"
    )
    parser.add_argument(
        "--order-items",
        type=int,
        default=50_000,
        help="Number of order items to generate"
    )
    parser.add_argument(
        "--events",
        type=int,
        default=40_000,
        help="Number of events to generate"
    )
    parser.add_argument(
        "--departments",
        type=int,
        default=20,
        help="Number of departments to generate"
    )
    parser.add_argument(
        "--employees",
        type=int,
        default=5_000,
        help="Number of employees to generate"
    )

    parsed = parser.parse_args(args)

    scale = parsed.scale
    return DatabaseConfig(
        db_path=parsed.db_path,
        test_cases_path=parsed.test_cases_path,
        num_users=int(parsed.users * scale),
        num_orders=int(parsed.orders * scale),
        num_order_items=int(parsed.order_items * scale),
        num_events=int(parsed.events * scale),
        num_departments=int(parsed.departments * scale),
        num_employees=int(parsed.employees * scale),
        seed=parsed.seed,
        force=parsed.force,
        quiet=parsed.quiet
    )


def main() -> None:
    """CLI entry point for src/setup_db.py."""
    try:
        config = parse_args()
        setup_database(config)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
