#!/bin/bash

cd "$(dirname "$0")"

echo "========================================"
echo "ChatHomeBase Bot Setup"
echo "========================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python 3.9+ from python.org"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if already configured
if [ -f "config/settings.json" ]; then
    echo ""
    echo "========================================"
    echo "Account already configured!"
    echo "========================================"
    echo ""
    echo "To reconfigure, delete config/settings.json"
    echo "To start the bot, run LAUNCH.command"
    echo ""
    read -p "Press Enter to exit..."
    exit 0
fi

# Install dependencies (only first time)
if [ ! -f ".installed" ]; then
    echo "Installing dependencies... (this may take a few minutes)"
    pip3 install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install dependencies"
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    echo "Installing browser..."
    playwright install chromium
    
    touch .installed
    echo ""
    echo "========================================"
    echo "Installation complete!"
    echo "========================================"
    echo ""
fi

# Run setup wizard
python3 -c "from bootstrap.first_run_wizard import run_wizard; from pathlib import Path; run_wizard(Path('config/settings.json'))"

echo ""
read -p "Press Enter to exit..."