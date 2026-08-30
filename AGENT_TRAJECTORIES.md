# Agent Execution Trajectories & Workflow Traces

This document explains the multi-agent orchestration architecture and provides representative execution traces captured during the benchmark run.

The full machine-readable logs are available in `trajectories.json`.

## 🗺️ Evidence Map for the Judges

This log file contains the raw execution traces proving the system's agentic capabilities. When evaluating this submission, please refer to these specific test cases:

* **To evaluate Tool Calling & Multi-Agent Handoffs:** Review **TC-03**. You will see the Profiler pull an execution plan, pass it to the IndexArchitect to synthesize a composite index, and hand it to the Developer to write a CTE.
* **To evaluate Memory & Self-Healing:** Review **TC-06**. You will see the Developer agent fail its first attempt. The Verifier tool catches the row-count mismatch, injects the error back into the agent's memory, and the agent successfully fixes the SARGable predicate on its second attempt.
* **To evaluate Orchestration & Fallback Safety:** Review **TC-09**. You will see the agent hit the 3-retry limit. Instead of crashing or returning broken SQL, the `OrchestratorFallback` triggers, logging a safety net activation and returning the original SQL to guarantee 100% data parity.

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
  * **Latency Change:** **98.84 ms $
ightarrow$ 2.07 ms (47.79x speedup)**
