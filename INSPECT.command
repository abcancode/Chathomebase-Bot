#!/bin/bash
cd "$(dirname "$0")"
echo "Inspection mode: small window, Playwright Inspector, nothing is sent."
echo
exec "$(dirname "$0")/LAUNCH.command" --inspect --dry-run