#!/usr/bin/env bash
# ==============================================================================
# Multi-Agent Database Query Optimizer - Environment Setup Script
# ==============================================================================
set -euo pipefail

# ANSI Colors
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RESET="\033[0m"

echo -e "${CYAN}==================================================================${RESET}"
echo -e "${CYAN}   Setting Up Multi-Agent Database Query Optimizer Environment   ${RESET}"
echo -e "${CYAN}==================================================================${RESET}"

# Step 1: Detect Python 3
PYTHON_CMD="python3"
if ! command -v "$PYTHON_CMD" &>/dev/null; then
    echo -e "${YELLOW}Error: python3 is not installed on your system.${RESET}" >&2
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "✔ Detected Python version: ${GREEN}${PYTHON_VERSION}${RESET}"

# Step 2: Create Virtual Environment
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "▶ Creating virtual environment in ${GREEN}./${VENV_DIR}${RESET}..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "✔ Virtual environment created."
else
    echo -e "✔ Virtual environment already exists in ./${VENV_DIR}."
fi

# Step 3: Activate Virtual Environment
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
echo -e "✔ Virtual environment activated."

# Step 4: Upgrade pip & Install Requirements
echo -e "▶ Installing project dependencies from ${GREEN}requirements.txt${RESET}..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo -e "✔ Dependencies installed successfully."

# Step 5: Setup .env file
if [ ! -f ".env" ]; then
    echo -e "▶ Creating default .env from .env.example..."
    cp .env.example .env
    echo -e "✔ Created .env. Please configure your DEEPSEEK_API_KEY if running live queries."
else
    echo -e "✔ Existing .env file found."
fi

# Step 6: Initialize Database
echo -e "▶ Initializing benchmark sandbox database..."
python setup_db.py --force
echo -e "✔ Database initialized successfully."

echo -e "\n${GREEN}==================================================================${RESET}"
echo -e "${GREEN}   Environment Setup Complete!                                   ${RESET}"
echo -e "${GREEN}==================================================================${RESET}"
echo -e "To activate the virtual environment anytime, run:"
echo -e "  ${CYAN}source venv/bin/activate${RESET}\n"
echo -e "Available commands:"
echo -e "  • ${CYAN}python evaluate.py${RESET}            # Run comparative benchmark"
echo -e "  • ${CYAN}python verify_submission.py${RESET}   # Run sanity check verifier"
echo -e "  • ${CYAN}pytest${RESET}                        # Run test suite\n"
