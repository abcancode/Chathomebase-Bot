#!/bin/bash
cd "$(dirname "$0")"
echo "======================================="
echo "ChatHomeBase Bot Setup"
echo "======================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3 is not installed. Install it from python.org"
    read -p "Press Enter to close..."
    exit 1
fi

if [ -f "config/settings.json" ]; then
    echo "Account already configured."
    read -p "Update the existing configuration? (y/n): " ans
    if [[ ! "$ans" =~ ^[Yy] ]]; then
        echo "Nothing changed. Run LAUNCH.command to start the bot."
        read -p "Press Enter to close..."
        exit 0
    fi
    echo
fi

echo "Checking dependencies..."
python3 -m pip install -q -r requirements.txt || { echo "ERROR: Failed to install dependencies"; read -p "Press Enter to close..."; exit 1; }

if [ ! -f ".installed" ]; then
    echo "Installing browser... (this may take a few minutes)"
    python3 -m playwright install chromium || { echo "ERROR: Failed to install browser"; read -p "Press Enter to close..."; exit 1; }
    touch .installed
    echo "Installation complete!"
    echo
fi

python3 bootstrap/first_run_wizard.py
echo
read -p "Press Enter to close..."