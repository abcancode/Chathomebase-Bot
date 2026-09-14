#!/bin/bash
cd "$(dirname "$0")"
if [ ! -f "config/settings.json" ]; then
    echo "Account not configured! Run SETUP.command first."
    read -p "Press Enter to close..."
    exit 1
fi
echo "======================================="
echo "Starting ChatHomeBase Bot..."
echo "======================================="
echo
python3 launch_bot.py "$@"
echo
echo "Bot stopped."
read -p "Press Enter to close..."