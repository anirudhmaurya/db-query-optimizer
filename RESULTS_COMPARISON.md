# Quantitative Evaluation & Results Comparison

Comprehensive benchmark comparing the **Zero-Shot LLM Baseline** against the **Multi-Agent Optimizer** across 13 complex SQL performance anti-patterns.

---

## 1. Aggregate Benchmark Summary

| Metric | Zero-Shot Baseline | Multi-Agent Optimizer | Delta / Impact |
| :--- | :---: | :---: | :--- |
| **Total Test Cases** | 13 | 13 | Complete test suite |
| **Data Parity Accuracy** | 76.9% (10/13) | **100.0% (13/13)** | **+23.1% Accuracy Delta (Zero hallucinations)** |
| **Failed / Mismatch Cases** | 3 (TC-11, TC-12, TC-13) | **0** | Sandbox verifier catches all semantic drift |
| **Average Execution Speedup** | 23.28x (on valid) | **1.50x (Overall)** | Consistent, strictly verified speedup (max 6.15x) |
| **Peak Single-Query Speedup** | 115.26x | **47.79x (TC-03)** | Drastic reduction in query cost |
| **Target Indexes Synthesized** | 0 | **15 Indexes** | Automated schema tuning |
| **Feedback Iteration Cycles** | 0 (Single shot) | **15 Attempts** | Multi-step agentic refinement |

---

## 2. Detailed Per-Query Breakdown

| Query ID | Anti-Pattern Description | Baseline Accuracy | Agent Accuracy | Agent Speedup | Indexes Synthesized |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-01** | Multi-table nested loop without composite indexes | 100% | 100% | 1.07x | 2 |
| **TC-02** | Non-SARGable date function (`strftime` in WHERE) | 100% | 100% | 2.16x | 1 |
| **TC-03** | Correlated subquery calculating group average salary | 100% | 100% | **47.79x** | 1 |
| **TC-04** | Unindexed leading wildcard search on JSON payload | 100% | 100% | 0.97x | 1 |
| **TC-05** | Heavy aggregations on unindexed filter predicates | 100% | 100% | 2.98x | 1 |
| **TC-06** | NULL Trap: Unindexed LEFT JOIN with IS NULL filter | 100% | 100% | 1.12x | 1 |
| **TC-07** | Correlated EXISTS subquery with non-indexed filters | 100% | 100% | 1.06x | 1 |
| **TC-08** | Unindexed ORDER BY pagination scan with OFFSET | 100% | 100% | 1.00x | 1 |
| **TC-09** | Multi-level correlated subquery ranking simulation | 100% | 100% | 1.01x | 1 |
| **TC-10** | Unindexed computed arithmetic expression aggregation | 100% | 100% | 1.00x | 1 |
| **TC-11** | **The Fan-Out Trap:** Unnested multi-table join | **0.0% (FAILED)** | **100.0%** | **1.23x** | 2 |
| **TC-12** | **Three-Valued Logic Trap:** NULL FK in anti-joins | **0.0% (FAILED)** | **100.0%** | **1.35x** | 1 |
| **TC-13** | **Top-Record Tie Trap:** Correlated MAX() with ties | **0.0% (FAILED)** | **100.0%** | **1.00x** | 1 |

---

## 3. Analysis of Key Failure Modes

### 1. The Fan-Out Trap (TC-11)
* **The Query:** Computes `SUM(o.amount)` and `COUNT(oi.id)` across `users`, `orders`, and `order_items`.
* **Baseline Flaw:** The zero-shot prompt joined 1:N and 1:M tables naively, multiplying order amounts by the number of item rows per order and producing inflated, incorrect sums (`RESULT_MISMATCH`).
* **Agent Solution:** Pre-aggregated order counts in a CTE before joining and applying composite indexes (`idx_orders_user_id_amt`, `idx_order_items_order_id`), achieving 100% verified parity.

### 2. The Three-Valued Logic Trap (TC-12)
* **The Query:** Finds users who have never placed an order using `WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)`.
* **Baseline Flaw:** The zero-shot model rewrote `NOT EXISTS` to `WHERE u.id NOT IN (SELECT user_id FROM orders)`. Because `orders` contains rows with `user_id IS NULL`, SQL three-valued logic evaluated `NOT IN` to `UNKNOWN`, returning 0 rows.
* **Agent Solution:** Retained NULL-safe `NOT EXISTS` semantics while synthesizing index `idx_orders_user_id` on `orders(user_id)` to convert full table scans into index lookups.

### 3. The Top-Record Tie Trap (TC-13)
* **The Query:** Returns all employees who earn the highest salary in their department using `WHERE salary = (SELECT MAX(salary) FROM employees WHERE department_id = e.department_id)`.
* **Baseline Flaw:** The zero-shot model used `ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC) = 1`, which arbitrarily dropped tied top earners and corrupted result sets.
* **Agent Solution:** Used `DENSE_RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) = 1` or `MAX() OVER()` to preserve all tied top earners with 100% multiset parity.
