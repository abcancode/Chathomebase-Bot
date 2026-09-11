#!/usr/bin/env python3
"""Launch bot with web automation."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import load_settings
from adapters.web_platform import run_web_bot


def main():
    config_file = Path(__file__).parent / "config" / "settings.json"
    
    if not config_file.exists():
        print("ERROR: Account not configured. Run SETUP.bat first.")
        sys.exit(1)
    
    settings = load_settings(config_file)
    
    # Check required settings
    required = ["deepseek_api_key", "chathomebase_login", "chathomebase_password"]
    missing = [k for k in required if not settings.get(k)]
    if missing:
        print(f"ERROR: Missing settings: {', '.join(missing)}")
        print("Run SETUP.bat to configure.")
        sys.exit(1)
    
    # Run bot - LIVE MODE (sends messages automatically)
    try:
        asyncio.run(run_web_bot(settings, dry_run=False))
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()