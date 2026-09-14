"""Validate and clean model output before it is typed."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class RuleGuard:
    AI_TELLS = ["as an ai", "language model", "i am an ai", "i'm an ai", "i am a bot", "i'm a bot",
                "i cannot assist", "i can't assist", "openai", "deepseek", "chatbot", "virtual assistant",
                "as a chat operator", "i'm here to help"]

    def __init__(self, rules_file: Path, banned_file: Path, customer_first_name: str = "Customer"):
        self.customer_first_name = customer_first_name
        self.banned_phrases: List[str] = []
        self.replacement_map: Dict[str, str] = {}
        rules = {}
        try:
            rules = json.loads(rules_file.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[WARNING] Failed to load rules: {e}")
        try:
            if banned_file.exists():
                self.banned_phrases = json.loads(banned_file.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[WARNING] Failed to load banned phrases: {e}")
        limits = rules.get("response_limits", {})
        self.min_chars = int(limits.get("min_characters", 150))
        self.max_chars = int(limits.get("max_characters", 500))
        self.followup_min_chars = int(rules.get("followup_min_characters", 100))

    def set_customer_name(self, name: str):
        self.customer_first_name = name.split()[0] if name else "Customer"

    def sanitize(self, text: str, player_name: Optional[str] = None) -> str:
        t = text.strip()
        if player_name:
            t = re.sub(rf"^\s*{re.escape(player_name)}\s*:\s*", "", t, flags=re.I)
        t = re.sub(r"^\s*(?:reply|response|message)\s*:\s*", "", t, flags=re.I)
        if len(t) > 1 and t[0] in "\"'\u201c" and t[-1] in "\"'\u201d":
            t = t[1:-1]
        t = re.sub(r"[*_`#]+", "", t)
        t = re.sub(r"\s*\n+\s*", " ", t)
        return re.sub(r" {2,}", " ", t).strip()

    def check(self, text: str, is_follow_up: bool = False) -> Tuple[bool, Optional[str]]:
        if not text:
            return False, "empty"
        low = text.lower()
        for phrase in self.banned_phrases:
            if re.search(rf"\b{re.escape(phrase.lower())}\b", low):
                return False, f"contains banned phrase '{phrase}'"
        for tell in self.AI_TELLS:
            if tell in low:
                return False, f"sounds like an AI ('{tell}')"
        if re.search(r"$$[^$$]{1,40}$$", text):
            return False, "contains a placeholder in brackets"
        min_c = self.followup_min_chars if is_follow_up else self.min_chars
        if len(text) < min_c:
            return False, f"too short ({len(text)} chars, minimum {min_c})"
        if len(text) > self.max_chars:
            return False, f"too long ({len(text)} chars, maximum {self.max_chars})"
        if "?" not in text:
            return False, "does not end with a question"
        return True, None

    def filter(self, text: str) -> str:
        """Backwards-compatible soft filter (case-insensitive). Prefer check() + regenerate."""
        t = self.sanitize(text)
        for phrase in self.banned_phrases:
            t = re.sub(rf"\b{re.escape(phrase)}\b", "", t, flags=re.I)
        return re.sub(r" {2,}", " ", t).strip()