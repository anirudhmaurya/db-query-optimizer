# Quantitative Evaluation & Results Comparison

Comprehensive benchmark comparing the **Zero-Shot LLM Baseline** against the **Multi-Agent Optimizer** across 13 complex SQL performance anti-patterns.

---

## 1. Aggregate Benchmark Summary

| Metric | Zero-Shot Baseline | Multi-Agent Optimizer | Delta / Impact |
| :--- | :---: | :---: | :--- |
| **Total Test Cases** | 13 | 13 | Complete test suite |
| **Data Parity Accuracy** | 92.3% (12/13) | **100.0% (13/13)** | **Zero hallucinations allowed** |
| **Failed / Mismatch Cases** | 1 (TC-11) | **0** | Sandbox verifier catches errors |
| **Average Execution Speedup** | 29.91x (on valid) | **5.96x (Overall)** | Consistent, verified speedups |
| **Peak Single-Query Speedup** | 115.26x | **47.79x (TC-03)** | Drastic reduction in query cost |
| **Target Indexes Synthesized** | 0 | **28 Indexes** | Automated schema tuning |
| **Feedback Iteration Cycles** | 0 (Single shot) | **13 Attempts** | Multi-step agentic refinement |

---

## 2. Detailed Per-Query Breakdown

| Query ID | Anti-Pattern Description | Baseline Accuracy | Agent Accuracy | Agent Speedup | Indexes Synthesized |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-01** | Multi-table nested loop without composite indexes | 100% | 100% | 1.79x | 3 |
| **TC-02** | Non-SARGable date function (`strftime` in WHERE) | 100% | 100% | 2.87x | 2 |
| **TC-03** | Correlated subquery calculating group average salary | 100% | 100% | **47.79x** | 3 |
| **TC-04** | Unindexed leading wildcard search on JSON payload | 100% | 100% | 1.76x | 3 |
| **TC-05** | Heavy aggregations on unindexed filter predicates | 100% | 100% | 1.59x | 3 |
| **TC-06** | NULL Trap: Unindexed LEFT JOIN with IS NULL filter | 100% | 100% | 1.17x | 2 |
| **TC-07** | Correlated EXISTS subquery with non-indexed filters | 100% | 100% | 2.13x | 2 |
| **TC-08** | Unindexed ORDER BY pagination scan with OFFSET | 100% | 100% | 2.39x | 1 |
| **TC-09** | Multi-level correlated subquery ranking simulation | 100% | 100% | **5.89x** | 3 |
| **TC-10** | Unindexed computed arithmetic expression aggregation | 100% | 100% | 1.87x | 0 |
| **TC-11** | **The Fan-Out Trap:** Unnested multi-table join | **0.0% (FAILED)** | **100.0%** | **1.98x** | 3 |
| **TC-12** | Three-Valued Logic Trap: NULL FK in anti-joins | 100% | 100% | 1.35x | 1 |
| **TC-13** | Top-Record Tie Trap: Correlated MAX() with ties | 100% | 100% | 4.94x | 2 |

---

## 3. Analysis of Key Failure Modes

### The Baseline Failure Case: TC-11 (Fan-Out Trap)
* **The Query:** Computes `SUM(o.amount)` and `COUNT(oi.id)` across `users`, `orders`, and `order_items`.
* **Baseline Flaw:** The zero-shot prompt left the query unverified, failing to recognize that joining 1:N and 1:M relationships inflated row aggregations, leading to a `RESULT_MISMATCH`.
* **Agent Solution:** The agentic workflow synthesized targeted B-Tree indexes (`idx_orders_user_id_amt`, `idx_order_items_order_id`) and verified multiset row parity in the sandbox before committing the change.
