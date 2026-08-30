# Agent Execution Trajectories & Workflow Traces

This document explains the multi-agent orchestration architecture and provides representative execution traces captured during the benchmark run.

The full machine-readable logs are available in `trajectories.json`.

---

## 1. Multi-Agent Architecture

```
             ┌───────────────────────────┐
             │     Input SQL Query       │
             └─────────────┬─────────────┘
                           │
                           ▼
             ┌───────────────────────────┐
             │       ProfilerAgent       │ ◄─── Tool: DatabaseSandbox.get_explain_plan
             └─────────────┬─────────────┘
                           │ (Bottleneck Report JSON)
                           ▼
             ┌───────────────────────────┐
             │    IndexArchitectAgent    │ ◄─── Tool: DatabaseSandbox.apply_index
             └─────────────┬─────────────┘
                           │ (Synthesized Indexes DDL)
                           ▼
             ┌───────────────────────────┐
      ┌─────►│      DeveloperAgent       │ (Transforms SQL to SARGable / CTE forms)
      │      └─────────────┬─────────────┘
      │                    │ (Candidate SQL)
      │                    ▼
(Retry on │  ┌───────────────────────────┐
 Mismatch)└──┤       VerifierAgent       │ ◄─── Tool: DatabaseSandbox.verify
             └─────────────┬─────────────┘
                           │ (Verified Data Parity)
                           ▼
             ┌───────────────────────────┐
             │ Output High-Perf SQL & DDL│
             └───────────────────────────┘
```

---

## 2. Representative Trajectory: TC-03 (Correlated Subquery)

### Step 1: Profiler Agent
* **Input Query:** Correlated scalar subquery computing department average salary in the `WHERE` clause.
* **Tool Called:** `DatabaseSandbox.get_explain_plan`.
* **Tool Output:** Detected `SCAN e`, `CORRELATED SCALAR SUBQUERY`, and `USE TEMP B-TREE FOR ORDER BY`.
* **Agent Diagnostic:** Identified quadratic $O(N^2)$ execution cost due to nested table scans.

### Step 2: Index Architect Agent
* **Tool Called:** `DatabaseSandbox.apply_index`.
* **Applied Indexes:**
  1. `CREATE INDEX idx_emp_dept_salary ON employees (department_id, salary);`
  2. `CREATE INDEX idx_emp_salary ON employees (salary DESC);`
* **Tool Output:** Execution plan updated to use index range lookups.

### Step 3: Developer Agent
* **Technique Applied:** Rewrote correlated scalar subquery into a Common Table Expression (CTE) with a single `GROUP BY` pass.
* **Rewritten Query:**
  ```sql
  WITH dept_stats AS (
      SELECT department_id, AVG(salary) AS avg_salary 
      FROM employees 
      GROUP BY department_id
  ) 
  SELECT e.id, e.name, e.department_id, e.salary, d.avg_salary AS dept_avg_salary 
  FROM employees e 
  JOIN dept_stats d ON e.department_id = d.department_id 
  WHERE e.salary > d.avg_salary * 1.15 
  ORDER BY e.salary DESC;
  ```

### Step 4: Verifier Agent (Closed-Loop Parity Check)
* **Tool Called:** `DatabaseSandbox.verify`.
* **Tool Output:**
  * **Status:** `PASSED`
  * **Parity Check:** Exact multiset match.
  * **Latency Change:** **98.84 ms $ightarrow$ 2.07 ms (47.79x speedup)**
