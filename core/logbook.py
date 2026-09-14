"""Persistent memory of invented facts.

Facts are scoped per PLAYER profile (a fact invented while playing 'Anna' must
never leak into 'Sofia'), and per customer inside that. Files have no date in
the name so consistency survives across days.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def _slug(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "unknown").lower()).strip("_") or "unknown"


def _load(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[WARNING] Failed to load {path.name}: {e}")
    return default


def _save(path: Path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"[WARNING] Failed to save {path.name}: {e}")


class Logbook:
    CATEGORIES = ["Work", "Sexual", "Health", "Update", "Client_Work", "Other"]

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.player_name: Optional[str] = None
        self.customer_name: Optional[str] = None
        self.entries: List[Dict] = []
        self.customer_facts: Dict[str, str] = {}
        self.player_facts: Dict[str, str] = {}
        self.customer_file: Optional[Path] = None
        self.facts_file: Optional[Path] = None

    def bind(self, player_name: str, customer_name: str):
        """Switch to a (player, customer) pair. Called on every new assignment."""
        self.player_name, self.customer_name = player_name, customer_name
        player_dir = self.log_dir / _slug(player_name)
        self.customer_file = player_dir / f"{_slug(customer_name)}.json"
        self.facts_file = player_dir / "player_facts.json"
        data = _load(self.customer_file, {})
        if isinstance(data, list):  # old format
            data = {"facts": {}, "entries": data}
        self.entries = data.get("entries", [])
        self.customer_facts = data.get("facts", {})
        self.player_facts = _load(self.facts_file, {})

    def _persist(self):
        if self.customer_file:
            _save(self.customer_file, {"customer": self.customer_name, "facts": self.customer_facts,
                                       "entries": self.entries})
        if self.facts_file:
            _save(self.facts_file, self.player_facts)

    def add_entry(self, category: str, comment: str, client: Optional[str] = None):
        if category not in self.CATEGORIES:
            category = "Other"
        if any(e["comment"] == comment for e in self.entries):
            return
        self.entries.append({"timestamp": datetime.now().isoformat(timespec="seconds"),
                             "category": category, "comment": comment,
                             "client": client or self.customer_name})
        self._persist()

    # player facts (global to this player profile)
    def set_profession(self, base: str, detail: Optional[str] = None, client: Optional[str] = None):
        self.player_facts["profession"] = base
        if detail:
            self.player_facts["profession_detail"] = detail
        self.add_entry("Work", f"Profession: {base}" + (f" - {detail}" if detail else ""), client)
        self._persist()

    def get_player_profession(self) -> Optional[str]:
        return self.player_facts.get("profession")

    def get_profession_detail(self, detail_type: str = "detail") -> Optional[str]:
        return self.player_facts.get(f"profession_{detail_type}")

    def set_player_fact(self, key: str, value: str):
        self.player_facts[key] = value
        self._persist()

    # customer-scoped facts (e.g. which town we told THIS customer we live in)
    def set_customer_fact(self, key: str, value: str):
        self.customer_facts[key] = value
        self._persist()

    def get_customer_fact(self, key: str) -> Optional[str]:
        return self.customer_facts.get(key)

    def get_facts_by_category(self, category: str) -> List[Dict]:
        return [e for e in self.entries if e["category"] == category]

    def all_entries(self) -> List[Dict]:
        return self.entries

    def get_summary_for_prompt(self) -> str:
        lines = []
        prof = self.get_player_profession()
        if prof:
            detail = self.get_profession_detail()
            lines.append(f"Work: {prof}" + (f" ({detail})" if detail else ""))
        for k, v in self.customer_facts.items():
            lines.append(f"{k.replace('_', ' ').title()}: {v}")
        for cat in ("Sexual", "Health", "Update", "Client_Work"):
            for e in self.get_facts_by_category(cat)[-3:]:
                lines.append(f"{cat}: {e['comment'][:100]}")
        return "\n".join(lines) if lines else "No established facts yet."