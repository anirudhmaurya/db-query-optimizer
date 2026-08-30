# Improvement Changelog

This document details the progressive engineering iterations from baseline prompting to the final 4-agent orchestrator architecture.

---

## Evolution Stages

| Stage | What We Tried & Why | Evidence & Benchmark Results | Decision / Learning |
| :--- | :--- | :--- | :--- |
| **Stage 1: Zero-Shot Baseline Prompting** | Issued a single ungrounded DBA optimization prompt (*"You are an SQL assistant. Rewrite the following SQL query to make it run faster on SQLite..."*) without schema inspection, plan analysis, or sandbox verification. | **76.9% Accuracy (10/13)**<br>• Failed on **TC-11 (Fan-Out Trap)** by duplicating aggregated sums.<br>• Failed on **TC-12 (Three-Valued Logic Trap)** by rewriting `NOT EXISTS` to `NOT IN` with NULL foreign keys.<br>• Failed on **TC-13 (Top-Record Tie Trap)** by using `ROW_NUMBER()` and dropping tied top earners.<br>• Synthesized **0 physical indexes**. | **Learning:** LLMs cannot reliably optimize relational queries in a vacuum without direct visibility into physical cost plans (`EXPLAIN`), index state, and mathematical result verification. |
| **Stage 2: Single-Agent with Profiling Tool (`EXPLAIN`)** | Connected a single LLM agent to `EXPLAIN QUERY PLAN` outputs and database DDL schemas, asking it to simultaneously diagnose bottlenecks, propose indexes, and rewrite SQL in a single completion pass. | Correctly identified `SCAN` vs `SEARCH` operations, but suffered severe cognitive overload and hallucinated SQLite syntax (e.g. `INCLUDE` clauses). Optimization success was inconsistent across multi-table queries. | **Decision:** Decoupled responsibilities into specialized agent roles: **ProfilerAgent** for bottleneck isolation, **IndexArchitectAgent** for DDL indexing, and **DeveloperAgent** for query restructuring. |
| **Stage 3: Multi-Agent Orchestrator with Closed-Loop Verifier** | Built a 4-agent orchestrator (`Profiler` → `IndexArchitect` → `Developer` → `Verifier`). The Verifier executes candidate SQL in an isolated sandbox, validates row counts and multiset equivalence, and feeds diagnostic errors back into a closed-loop retry loop (up to 3 attempts). | **100.0% Accuracy (13/13)**<br>• Average Speedup: **1.50x** (with a max of **6.15x** / **47.79x** on quadratic subqueries).<br>• Synthesized **15 high-impact B-Tree indexes**.<br>• Successfully eliminated sequential scans and recovered from all semantic trap queries. | **Learning:** Closed-loop diagnostic error feedback and sandbox multiset verification are mandatory to prevent silent data corruption in data engineering agents. |
