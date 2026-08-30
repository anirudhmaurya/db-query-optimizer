# Multi-Agent SQL Query Optimizer Orchestrator
**micro1 Frontier Engineering Challenge Deliverable**

An execution-guided, multi-agent AI system designed to profile, index, rewrite, and mathematically verify relational SQL queries, eliminating performance bottlenecks on high-throughput database workloads.

---

## 1. The Problem & User Value

### Intended Users
This system is built for **Database Administrators (DBAs)**, **Backend Engineers**, and **Data Infrastructure Teams** responsible for maintaining performant, low-latency relational databases under demanding query workloads.

### The Bottleneck
When developers turn to general-purpose zero-shot LLMs for query optimization, they encounter severe reliability bottlenecks:
1. **Schema & Index Hallucinations**: Zero-shot models hallucinate non-existent database indexes, columns, or tables because they lack runtime connection to the database engine.
2. **Silent Semantic Alteration**: Models frequently drop filter predicates (e.g., `WHERE` or `HAVING` clauses), alter aggregation groupings, or convert `LEFT JOIN`s into `INNER JOIN`s. While the resulting query runs faster, it produces corrupted or truncated result sets.
3. **Lack of Cost Plan Awareness**: Optimization without examining the physical execution plan (`EXPLAIN QUERY PLAN`) results in naive syntactical shuffling that fails to eliminate sequential scans, temporary B-tree sorts, or nested loop thrashing.

### User Value
This system replaces ungrounded zero-shot guessing with a **closed-loop, execution-guided multi-agent pipeline**:
- **Execution-Guided Profiling**: Grounded analysis of physical `EXPLAIN QUERY PLAN` opcode trees.
- **Physical Index Architecture**: Synthesis of optimal composite and covering B-Tree indexes.
- **SARGable & Relational Rewriting**: Systematic conversion of quadratic correlated subqueries into Window Functions/CTEs and non-SARGable functions into range predicates.
- **Deterministic Verification**: Strict multiset result-set equivalence validation in isolated database sandboxes before any optimization is accepted.

---

## 2. Reproduction Guide

Follow these step-by-step instructions starting from a clean environment.

### Prerequisites
- Python 3.10+
- Internet connection (for API calls) or use `--mock` for local offline verification.

### Quickstart (Automated Setup)
Run the automated environment setup script or use `make`:
```bash
# Automated setup (creates venv, installs requirements, creates .env, inits database)
chmod +x setup.sh && ./setup.sh

# Or using Makefile
make setup
```

After setup, configure your API key in `.env`:
```bash
# DeepSeek API Key (Get from: https://platform.deepseek.com/api_keys)
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
# Or use GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
```
*(For offline evaluation with zero API cost, you can skip setting an API key and append `--mock` to any command).*

### Manual Setup (Step-by-Step)
```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install requirements
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
```
Edit `.env` and set your API key:
```bash
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
```

### Step 3: Execution Order

Execute the following commands sequentially:

```bash
# 1. Initialize SQLite benchmark database with realistic synthetic data across tables
python setup_db.py --force

# 2. Run Zero-Shot Baseline Evaluator
python baseline.py

# 3. Run Multi-Agent Optimizer Orchestrator
python agent_optimizer.py

# 4. Run Comparative Evaluator (prints summary table and outputs evaluation_results.json & trajectories.json)
python evaluate.py

# 5. Run Automated Clean Environment Sanity Check
python verify_submission.py
```

> **Expected Runtime**: Under **2 minutes** for the complete 13-query benchmark suite.

### Offline / Mock Execution (Zero API Costs)
For instantaneous offline testing without API keys, append `--mock` to any command:
```bash
python verify_submission.py --mock
```

---

## 3. Improvement Changelog

| Stage | What I tried and why | Evidence | Decision / Learning |
| :--- | :--- | :--- | :--- |
| **Stage 1: Zero-Shot DBA Prompting (Baseline)** | Issued a single ungrounded DBA optimization prompt (*"You are an SQL assistant. Rewrite the following SQL query to make it run faster on SQLite..."*) directly to the LLM without schema inspection or plan analysis. | Achieved **76.9% accuracy (10/13)**. Failed on **TC-11 (Fan-Out Trap)**, **TC-12 (Three-Valued Logic Trap)**, and **TC-13 (Top-Record Tie Trap)**. Achieved zero physical index utilization. | **Learning**: LLMs cannot reliably optimize database performance in a vacuum without direct visibility into physical cost plans (`EXPLAIN`) and table indexes. |
| **Stage 2: Single Agent with Profiling Tool (`EXPLAIN`)** | Connected a single LLM agent to `EXPLAIN QUERY PLAN` outputs and database DDL schemas, asking it to diagnose bottlenecks and propose both indexes and SQL rewrites. | The agent correctly identified `SCAN` vs `SEARCH` operations, but suffered cognitive overload when attempting to simultaneously design composite indexes, fix syntax, and restructure queries in a single completion pass. | **Decision**: Decoupled responsibilities into specialized agent roles: **ProfilerAgent** for bottleneck isolation, **IndexArchitectAgent** for DDL indexing, and **DeveloperAgent** for query restructuring. |
| **Stage 3: Multi-Agent System with Verifier Retry-Loop** | Engineered a 4-agent orchestrator (`Profiler` → `IndexArchitect` → `Developer` → `Verifier`). The Verifier tests candidate SQL in an isolated sandbox, validates row counts and multiset equivalence, and feeds diagnostic errors back into a closed-loop retry loop (up to 3 attempts). | Achieved **100.0% verified accuracy (13/13)**, synthesized **15 B-Tree indexes**, and reached an average speedup of **1.50x** (with up to **6.15x** / **47.79x** peak on quadratic subqueries). | **Learning**: Closed-loop diagnostic error feedback is essential. When a developer agent generates a syntax error or semantic mismatch, providing the exact verification diff allows it to self-correct within 1 retry. |

---

## 4. Hot Take & Failure Mode

### The Main Failure Mode: Silent Semantic Drift
The most pervasive and dangerous failure mode encountered in LLM-driven query optimization is **silent semantic drift**:
- The model produces a rewritten query that is syntactically flawless and executes with blistering speed, but silently corrupts business logic.
- Prominent semantic failure modes observed during testing include:
  1. **The Fan-Out Trap (TC-11)**: Naive multi-table joins without CTE pre-aggregation multiplying aggregated sums (`SUM(amount)`) due to duplicate child rows.
  2. **The Three-Valued Logic Trap (TC-12)**: Rewriting `NOT EXISTS` to `WHERE u.id NOT IN (SELECT user_id FROM orders)`, returning 0 rows in SQLite when the table contains `NULL` foreign keys.
  3. **The Top-Record Tie Trap (TC-13)**: Rewriting correlated subqueries with `ROW_NUMBER() = 1` which arbitrarily drops tied top earners instead of using `DENSE_RANK()`.
  4. **The Non-SARGable Trap (TC-02)**: Dropping `WHERE` conditions containing date functions rather than mathematically converting them to range filters.
  5. **The NULL Trap (TC-06)**: Converting a `LEFT JOIN ... WHERE right.id IS NULL` into an `INNER JOIN`, dropping non-matching entities.

Without automated mathematical verification, these faulty queries would pass code reviews and corrupt analytics or transactional integrity in production.

### The Hot Take
> **"Agentic AI in data engineering is only as good as the deterministic sandbox verifying it."**

LLMs are probabilistic token predictors, not formal relational query optimizers. Leaving an LLM unconstrained in a database environment is a critical production liability. True agentic engineering requires grounding the LLM within a rigid, deterministic sandbox that enforces strict execution constraints:
1. Physical query plan analysis before and after changes.
2. Isolated sandbox database execution to test index modifications without production risk.
3. Mathematical multiset result-set equivalence validation with zero tolerance for row or column discrepancies.
4. Error-feedback retry loops that treat compiler and execution errors as diagnostic prompts.
