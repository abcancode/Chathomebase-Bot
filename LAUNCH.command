#!/bin/bash

# Get the directory where this script is located
cd "$(dirname "$0")"

# Check if configured
if [ ! -f "config/settings.json" ]; then
    echo "========================================"
    echo "Account not configured!"
    echo "========================================"
    echo ""
    echo "Please run SETUP.command first to enter your credentials."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "========================================"
echo "Starting ChatHomeBase Bot..."
echo "========================================"
echo ""

python3 launch_bot.py

echo ""
echo "Bot stopped."
echo ""
read -p "Press Enter to exit..."