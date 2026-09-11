"""Settings management."""

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
    """Load settings with shared Google key."""
    settings = _load_json(config_file) if config_file.exists() else {}
    
    # Load shared Google key from separate file
    google_key_file = config_file.parent / "google_key.txt"
    if google_key_file.exists():
        settings["google_api_key"] = google_key_file.read_text().strip()
    
    return settings


def save_settings(config_file: Path, settings: dict) -> None:
    """Save settings (without Google key - that's in separate file)."""
    settings_to_save = {k: v for k, v in settings.items() if k != "google_api_key"}
    _save_json(config_file, settings_to_save)