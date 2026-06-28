#!/bin/bash
set -e
echo "Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
echo "Installing dependencies..."
pip install -r requirements.txt
echo "Installing Playwright browsers..."
playwright install chromium
echo "Setup complete. Activate with: source .venv/bin/activate"
