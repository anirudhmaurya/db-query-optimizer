# Clean-Environment Reproduction Guide

This guide provides exact instructions for evaluators and judges to reproduce the baseline comparison, agent workflows, and test suite on a clean environment.

---

## 1. System Requirements & Environment

* **Operating System:** Linux, macOS, or Windows (WSL2 recommended)
* **Python Runtime:** Python 3.10, 3.11, or 3.12
* **Database Engine:** SQLite 3.35+ (bundled with standard Python runtime)
* **Expected Runtime:** ~90–120 seconds for full 13-query benchmark execution
* **API Cost:** < $0.15 USD total (using DeepSeek or OpenAI models)

---

## 2. One-Step Automated Setup

If running on macOS/Linux:

```bash
chmod +x setup.sh
./setup.sh
```

The setup script automatically initializes the virtual environment, installs dependencies, creates `.env` from `.env.example`, and generates the benchmark sandbox database with 100,000+ synthetic records.

> **Configure API Key:**
> After running `./setup.sh`, open `.env` and set your API key:
> ```bash
> # Edit .env and enter your key:
> DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
> # Or use GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY
> ```
> *(For offline execution with zero API cost, you can skip adding an API key and pass `--mock` to any command).*

---

## 3. Manual Step-by-Step Setup

If setting up manually from terminal:

```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure API Key
cp .env.example .env
# Edit .env and enter your DEEPSEEK_API_KEY or OPENAI_API_KEY

# 4. Generate SQLite Benchmark Sandbox
python setup_db.py --force
```

---

## 4. Execution & Verification Commands

### Run Full Comparative Benchmark
Executes the Zero-Shot Baseline and the Multi-Agent Optimizer across all 13 test queries:

```bash
python evaluate.py
```

* **Expected Terminal Output:** A formatted comparison table detailing per-query speedups, accuracy checks, synthesized indexes, and aggregate benchmark metrics.
* **Generated Artifacts:** `evaluation_results.json` and `trajectories.json`.

### Run Qualification Gate & Sanity Checks
Validates submission readiness, artifact existence, and accuracy constraints:

```bash
python verify_submission.py
```

### Run Unit Test Suite
Runs the complete test suite verifying tool integrity, sandbox rollbacks, and retry state machines:

```bash
pytest -v
```

### Launch Interactive Streamlit UI (Optional)
```bash
streamlit run streamlit_app/app.py
```
