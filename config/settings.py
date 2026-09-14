"""Settings management. Google key lives in config/google_key.txt (shared, not in settings.json)."""

import json
from pathlib import Path
from typing import Any, Dict


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_settings(config_file: Path) -> dict:
    settings = _load_json(config_file) if config_file.exists() else {}
    google_key_file = config_file.parent / "google_key.txt"
    if google_key_file.exists():
        key = google_key_file.read_text(encoding="utf-8").strip()
        if key:
            settings["google_api_key"] = key
    return settings


def save_settings(config_file: Path, settings: dict) -> None:
    _save_json(config_file, {k: v for k, v in settings.items() if k != "google_api_key"})