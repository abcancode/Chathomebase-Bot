#!/bin/bash

cd "$(dirname "$0")"

# CONFIGURE THESE URLS
VERSION_URL="https://raw.githubusercontent.com/abcancode/Chathomebase-Bot/main/version.txt"
DOWNLOAD_URL="https://github.com/abcancode/Chathomebase-Bot/releases/download/v1.0.0/latest.zip"

echo "========================================"
echo "ChatHomeBase Bot Updater"
echo "========================================"
echo ""

# Check curl
if ! command -v curl &> /dev/null; then
    echo "ERROR: curl not found"
    read -p "Press Enter..."
    exit 1
fi

echo "Checking for updates..."

# Download version
curl -s -L "$VERSION_URL" > .latest_version

if [ ! -f .latest_version ]; then
    echo "ERROR: Could not check for updates"
    read -p "Press Enter..."
    exit 1
fi

LATEST=$(cat .latest_version)
CURRENT=$(cat version.txt 2>/dev/null || echo "0.0.0")

echo "Current: $CURRENT"
echo "Latest: $LATEST"

if [ "$CURRENT" == "$LATEST" ]; then
    echo ""
    echo "========================================"
    echo "You are up to date!"
    echo "========================================"
    rm .latest_version
    read -p "Press Enter..."
    exit 0
fi

echo ""
echo "Update available: $CURRENT -> $LATEST"
echo ""

# Backup
if [ -f "config/settings.json" ]; then
    cp config/settings.json config/settings.json.backup
    echo "[OK] Settings backed up"
fi

# Download
echo "Downloading..."
curl -L -o update.zip "$DOWNLOAD_URL"

if [ ! -f update.zip ]; then
    echo "ERROR: Download failed"
    rm .latest_version
    read -p "Press Enter..."
    exit 1
fi

# Extract
echo "Extracting..."
unzip -o update.zip

# Restore settings
if [ -f "config/settings.json.backup" ]; then
    cp config/settings.json.backup config/settings.json
    rm config/settings.json.backup
    echo "[OK] Settings restored"
fi

# Update version
cp .latest_version version.txt

# Cleanup
rm update.zip
rm .latest_version

echo ""
echo "========================================"
echo "Update complete! Version $LATEST"
echo "========================================"
read -p "Press Enter..."