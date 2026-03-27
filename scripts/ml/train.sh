#!/bin/bash
# valtunox AI HR & cloudsystem Platform - Training CLI Launcher (Linux/Mac)
# Usage: ./train.sh [command] [options]

# Find Python executable
if [ -f "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
elif [ -f "windows-venv/Scripts/python.exe" ]; then
    PYTHON_CMD="windows-venv/Scripts/python.exe"
else
    PYTHON_CMD="python3"
fi

# Change to project root
cd "$(dirname "$0")/.."

# Run CLI
$PYTHON_CMD scripts/train_cli.py "$@"

