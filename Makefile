# ==============================================================================
# Multi-Agent Database Query Optimizer - Makefile
# ==============================================================================

PYTHON := python3
VENV_PYTHON := ./venv/bin/python
VENV_PIP := ./venv/bin/pip
VENV_PYTEST := ./venv/bin/pytest

.PHONY: help setup install db baseline agent eval verify test clean

help:
	@echo "=================================================================="
	@echo "Multi-Agent SQL Query Optimizer - Makefile Commands"
	@echo "=================================================================="
	@echo "make setup     : Set up venv, install dependencies, and init database"
	@echo "make install   : Create venv and install dependencies"
	@echo "make db        : Reset and initialize the benchmark database"
	@echo "make baseline  : Run Zero-Shot Baseline query evaluator"
	@echo "make agent     : Run Multi-Agent Optimizer Orchestrator"
	@echo "make eval      : Run complete comparative evaluation suite"
	@echo "make verify    : Run automated submission sanity checker"
	@echo "make test      : Run full pytest test suite"
	@echo "make clean     : Remove temporary caches and scratch databases"
	@echo "=================================================================="

setup:
	@bash setup.sh

install:
	@$(PYTHON) -m venv venv
	@$(VENV_PIP) install --upgrade pip --quiet
	@$(VENV_PIP) install -r requirements.txt --quiet
	@echo "Dependencies successfully installed into venv."

db:
	@$(VENV_PYTHON) setup_db.py --force

baseline:
	@$(VENV_PYTHON) baseline.py

agent:
	@$(VENV_PYTHON) agent_optimizer.py

eval:
	@$(VENV_PYTHON) evaluate.py

verify:
	@$(VENV_PYTHON) verify_submission.py

test:
	@$(VENV_PYTEST)

clean:
	@rm -rf __pycache__ */__pycache__ .pytest_cache
	@rm -rf trajectories/scratch
	@echo "Cleaned cache and temporary scratch files."
