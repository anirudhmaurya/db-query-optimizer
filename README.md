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
# Automated setup (creates venv, installs requirements, inits database)
chmod +x setup.sh && ./setup.sh

# Or using Makefile
make setup
```

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
# DeepSeek API Key (Get from: https://platform.deepseek.com/api_keys)
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
```

### Step 3: Execution Order

Execute the following commands sequentially:

```bash
# 1. Initialize SQLite benchmark database with realistic synthetic data across 10 tables
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

> **Expected Runtime**: Under **2 minutes** for the complete 10-query benchmark suite.

### Offline / Mock Execution (Zero API Costs)
For instantaneous offline testing without API keys, append `--mock` to any command:
```bash
python verify_submission.py --mock
```

---

## 3. Improvement Changelog

| Stage | What I tried and why | Evidence | Decision / Learning |
| :--- | :--- | :--- | :--- |
| **Stage 1: Zero-Shot DBA Prompting (Baseline)** | Issued a single ungrounded DBA optimization prompt (*"You are a DBA. Make this query faster..."*) directly to the LLM without schema inspection or plan analysis. | Produced frequent hallucinations, dropped `HAVING` filters, or returned identical SQL. Achieved zero physical index utilization and failed on anti-patterns requiring schema-level changes. | **Learning**: LLMs cannot reliably optimize database performance in a vacuum without direct visibility into physical cost plans (`EXPLAIN`) and table indexes. |
| **Stage 2: Single Agent with Profiling Tool (`EXPLAIN`)** | Connected a single LLM agent to `EXPLAIN QUERY PLAN` outputs and database DDL schemas, asking it to diagnose bottlenecks and propose both indexes and SQL rewrites. | The agent correctly identified `SCAN` vs `SEARCH` operations, but suffered cognitive overload when attempting to simultaneously design composite indexes, fix syntax, and restructure queries in a single completion pass. | **Decision**: Decoupled responsibilities into specialized agent roles: **ProfilerAgent** for bottleneck isolation, **IndexArchitectAgent** for DDL indexing, and **DeveloperAgent** for query restructuring. |
| **Stage 3: Multi-Agent System with Verifier Retry-Loop** | Engineered a 4-agent orchestrator (`Profiler` $\rightarrow$ `IndexArchitect` $\rightarrow$ `Developer` $\rightarrow$ `Verifier`). The Verifier tests candidate SQL in an isolated sandbox, validates row counts and multiset equivalence, and feeds diagnostic errors back into a closed-loop retry loop (up to 3 attempts). | Achieved up to **44x speedup** on quadratic subqueries (TC-03: `97.76ms` $\rightarrow$ `2.22ms`), successfully recovered from syntax and row-count mismatches on attempt 2, and achieved **90.0% verified accuracy** with comprehensive physical index acceleration. | **Learning**: Closed-loop diagnostic error feedback is essential. When a developer agent generates a syntax error or semantic mismatch, providing the exact verification diff allows it to self-correct within 1 retry. |

---

## 4. Hot Take & Failure Mode

### The Main Failure Mode: Silent Semantic Drift
The most pervasive and dangerous failure mode encountered in LLM-driven query optimization is **silent semantic drift**:
- The model produces a rewritten query that is syntactically flawless and executes with blistering speed (e.g., 20x faster), but silently corrupts business logic.
- Common examples observed during testing include:
  - Dropping `WHERE` conditions containing non-SARGable functions rather than mathematically converting them to range filters.
  - Converting a `LEFT OUTER JOIN` into an `INNER JOIN`, silently dropping non-matching entities.
  - Changing `COUNT(DISTINCT col)` to `COUNT(col)` to avoid sorting overhead.

Without automated mathematical verification, these faulty queries would pass code reviews and corrupt analytics or transactional integrity in production.

### The Hot Take
> **"Agentic AI in data engineering is only as good as the deterministic sandbox verifying it."**

LLMs are probabilistic token predictors, not formal relational query optimizers. Leaving an LLM unconstrained in a database environment is a critical production liability. True agentic engineering requires grounding the LLM within a rigid, deterministic sandbox that enforces strict execution constraints:
1. Physical query plan analysis before and after changes.
2. Isolated sandbox database execution to test index modifications without production risk.
3. Mathematical multiset result-set equivalence validation with zero tolerance for row or column discrepancies.
4. Error-feedback retry loops that treat compiler and execution errors as diagnostic prompts.
