#!/usr/bin/env python3
"""Launch the ChatHomeBase bot.

  python launch_bot.py               live, maximised window
  python launch_bot.py --dry-run     types replies but never presses send
  python launch_bot.py --inspect     small window + Playwright Inspector + DOM/event logger
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config.settings import load_settings          # noqa: E402
from adapters.web_platform import run_web_bot      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="never press send")
    ap.add_argument("--inspect", action="store_true", help="small window, inspector, event logging")
    args = ap.parse_args()

    config_file = ROOT / "config" / "settings.json"
    if not config_file.exists():
        print("ERROR: Account not configured. Run SETUP first.")
        sys.exit(1)

    settings = load_settings(config_file)
    missing = [k for k in ("deepseek_api_key", "chathomebase_login", "chathomebase_password") if not settings.get(k)]
    if missing:
        print(f"ERROR: Missing settings: {', '.join(missing)}. Run SETUP to configure.")
        sys.exit(1)

    try:
        asyncio.run(run_web_bot(settings, dry_run=args.dry_run, inspect=args.inspect))
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user")
    except Exception as e:  # noqa: BLE001
        print(f"\n[ERROR] {e}")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()