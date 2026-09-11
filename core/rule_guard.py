"""Post-generation rule guard."""

import json
import re
from pathlib import Path
from typing import List, Optional


class RuleGuard:
    """Filters and guards bot responses."""
    
    def __init__(self, rules_file: Path, banned_file: Path, customer_first_name: str = "Customer"):
        self.rules_file = rules_file
        self.banned_file = banned_file
        self.customer_first_name = customer_first_name
        self.banned_phrases: List[str] = []
        self.replacement_map: Dict[str, str] = {}
        
        self._load_banned()
        
    def _load_banned(self):
        """Load banned phrases."""
        try:
            if self.banned_file.exists():
                with open(self.banned_file, 'r') as f:
                    self.banned_phrases = json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load banned phrases: {e}")
            self.banned_phrases = []
    
    def set_customer_name(self, name: str):
        """Update customer first name."""
        self.customer_first_name = name.split()[0] if name else "Customer"
    
    def filter(self, text: str) -> str:
        """Filter response text."""
        # Check banned phrases
        for phrase in self.banned_phrases:
            if phrase.lower() in text.lower():
                print(f"[GUARD] Banned phrase detected: {phrase}")
                text = text.replace(phrase, "[removed]")
        
        # Ensure customer name is correct
        # (This would be customized based on your rules)
        
        return text.strip()
    
    def check_response(self, text: str, customer_msg: str) -> tuple[bool, Optional[str]]:
        """Check if response violates rules."""
        # Check for banned content
        for phrase in self.banned_phrases:
            if phrase.lower() in text.lower():
                return False, f"Contains banned phrase: {phrase}"
        
        return True, None