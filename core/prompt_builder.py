"""Build system prompts for DeepSeek."""

import json
from pathlib import Path
from typing import Dict, List, Optional


def load_rules(rules_file: Path) -> Dict:
    """Load rules from JSON file."""
    try:
        with open(rules_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARNING] Failed to load rules: {e}")
        return {}


def build_system_prompt(
    rules: Dict,
    player_name: str,
    player_occupation: str,
    player_location: Optional[str],
    customer_name: str,
    customer_location: str,
    logbook_summary: str,
    category: str,
    past_replies: List[str],
    user_message: str,
    is_follow_up: bool = False
) -> str:
    """Build system prompt for DeepSeek."""
    
    follow_up_instruction = ""
    if is_follow_up:
        follow_up_instruction = "\nThe customer hasn't replied. Send a short, flirty follow-up (10-15 words) to re-engage them."
    
    # Profession consistency warning
    profession_warning = ""
    if player_occupation and player_occupation != "Worker":
        profession_warning = f"\nIMPORTANT: You are a {player_occupation}. Never claim a different profession. You can elaborate but cannot change it."
    
    prompt = f"""You are {player_name}, a {player_occupation} from {player_location or 'a small town'}.

STRICT RULES:
- Minimum 150 characters per response
- Maximum 500 characters per response{profession_warning}
- Never share phone, email, or social media
- Never suggest meeting in person
- Always ask a question to keep conversation going

Your established facts (NEVER contradict these):
{logbook_summary}

You are chatting with {customer_name} from {customer_location}.
Customer just said: "{user_message}"

{follow_up_instruction}

Respond naturally as {player_name}. Be engaging, flirty, and make them want to reply."""

    return prompt


def build_history_messages(conversation: List[Dict]) -> List[Dict]:
    """Convert conversation to DeepSeek format."""
    return [
        {"role": "user" if m["speaker"] == "customer" else "assistant", "content": m["text"]}
        for m in conversation
    ]