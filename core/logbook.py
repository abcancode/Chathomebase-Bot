"""Logbook for tracking invented details with categories."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class Logbook:
    """Tracks invented personal details for consistency across customers."""
    
    CATEGORIES = [
        "Work",           # Player's profession details
        "Sexual",         # Fantasies, preferences, experiences  
        "Health",         # Health issues, conditions
        "Update",         # Appointments, events, photos received
        "Client_Work",    # Customer's profession
        "Other"           # Anything else
    ]
    
    def __init__(self, log_dir: Path, customer_name: str):
        self.log_dir = log_dir
        self.customer_name = customer_name
        self.log_file = log_dir / f"{customer_name}_{datetime.now().strftime('%Y%m%d')}.json"
        self.entries: List[Dict] = []
        self.player_facts: Dict[str, str] = {}  # Global player facts across all customers
        self._load()
        self._load_global_facts()
    
    def _load(self):
        """Load existing logbook for this customer."""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r') as f:
                    self.entries = json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load logbook: {e}")
            self.entries = []
    
    def _load_global_facts(self):
        """Load global player facts across all customers."""
        global_file = self.log_dir / "player_facts.json"
        try:
            if global_file.exists():
                with open(global_file, 'r') as f:
                    self.player_facts = json.load(f)
        except:
            self.player_facts = {}
    
    def _save_global_facts(self):
        """Save global player facts."""
        global_file = self.log_dir / "player_facts.json"
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with open(global_file, 'w') as f:
                json.dump(self.player_facts, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Failed to save global facts: {e}")
    
    def add_entry(self, category: str, comment: str, client: str = None):
        """Add entry to logbook."""
        if category not in self.CATEGORIES:
            category = "Other"
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "comment": comment,
            "client": client or self.customer_name
        }
        self.entries.append(entry)
        self._save()
        
        # If it's a player work fact, save globally
        if category == "Work" and ":" in comment:
            key = comment.split(":")[0].strip().lower()
            value = comment.split(":", 1)[1].strip() if ":" in comment else comment
            self.player_facts[key] = value
            self._save_global_facts()
    
    def get_player_profession(self) -> Optional[str]:
        """Get player's established profession."""
        return self.player_facts.get("profession")
    
    def get_profession_detail(self, detail_type: str) -> Optional[str]:
        """Get specific profession detail."""
        return self.player_facts.get(f"profession_{detail_type}")
    
    def set_profession(self, base: str, detail: str = None, client: str = None):
        """Set player's profession."""
        self.player_facts["profession"] = base
        if detail:
            self.player_facts["profession_detail"] = detail
        
        comment = f"Profession: {base}"
        if detail:
            comment += f" - {detail}"
        
        self.add_entry("Work", comment, client)
        self._save_global_facts()
    
    def get_facts_by_category(self, category: str) -> List[Dict]:
        """Get all entries for a category."""
        return [e for e in self.entries if e["category"] == category]
    
    def get_summary_for_prompt(self) -> str:
        """Build summary for AI prompt."""
        lines = []
        
        # Work/Profession
        prof = self.get_player_profession()
        if prof:
            detail = self.get_profession_detail("detail")
            lines.append(f"Work: {prof}" + (f" ({detail})" if detail else ""))
        
        # Recent entries by category
        for cat in ["Sexual", "Health", "Update"]:
            entries = self.get_facts_by_category(cat)[-3:]
            for e in entries:
                lines.append(f"{cat}: {e['comment'][:80]}")
        
        return "\n".join(lines) if lines else "No established facts yet."
    
    def _save(self):
        """Save logbook."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, 'w') as f:
                json.dump(self.entries, f, indent=2)
        except Exception as e:
            print(f"[WARNING] Failed to save logbook: {e}")
    
    def all_entries(self) -> List[Dict]:
        """Get all entries."""
        return self.entries