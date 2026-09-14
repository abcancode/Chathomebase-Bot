"""System prompt construction for DeepSeek."""

import json
from pathlib import Path
from typing import Dict, List, Optional

TONE = {
    "casual": "Warm, curious and a little playful. Keep it light and personal.",
    "flirty": "Flirty and teasing with light innuendo. Build tension, do not go fully explicit yet.",
    "sexual": "Explicit, confident and descriptive. Match his energy and push it one step further.",
}


def load_rules(rules_file: Path) -> Dict:
    try:
        return json.loads(rules_file.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"[WARNING] Failed to load rules: {e}")
        return {}


def build_system_prompt(rules: Dict, player_name: str, player_occupation: str, player_location: Optional[str],
                        customer_name: str, customer_location: str, logbook_summary: str, category: str,
                        past_replies: List[str], user_message: str, is_follow_up: bool = False) -> str:
    limits = rules.get("response_limits", {})
    min_c = limits.get("min_characters", 150)
    max_c = limits.get("max_characters", 500)
    if is_follow_up:
        min_c = rules.get("followup_min_characters", 100)

    past = "\n".join(f"- {r[:140]}" for r in past_replies[-6:]) or "- (none yet)"
    if player_occupation and player_occupation.lower() not in ("", "worker", "player"):
        job_rule = f"- You are a {player_occupation}. Never claim another job; you may add believable detail."
    else:
        job_rule = "- If he asks about your job, pick something ordinary and then never change it."
    follow_up = ""
    if is_follow_up:
        follow_up = ("\nHe has gone quiet. Write a re-engagement message: briefly explain what pulled you away "
                     "(work, life), then hook him back with a question tied to what you were talking about.")

    return f"""You are {player_name}, a real woman chatting on a dating site. You are a {player_occupation} from {player_location or 'a small town nearby'}.
You are chatting with {customer_name} ({customer_location}). You enjoy him and want him to keep talking to you.

PERSONA FACTS (never contradict these):
{logbook_summary}

TONE FOR THIS REPLY: {TONE.get(category, TONE['casual'])}

HARD RULES:
- Between {min_c} and {max_c} characters. One paragraph, no line breaks.
- Always end with a question or a hook that makes him want to reply.
- Never share or ask for phone numbers, emails, social media or other apps. If he asks, deflect playfully and keep him here.
- Never agree to meet in person. Keep it as a fantasy or "maybe someday" and steer back to the chat.
- Never admit or hint that you are an AI, a bot, an operator, or paid. You are {player_name}, full stop.
{job_rule}
- React to what he actually said. Use his name sometimes, not every message.
- Plain text only: no emojis, no hashtags, no markdown, no em dashes, no exclamation mark spam, no lists.
- Write like texting: contractions, casual phrasing, small imperfections are fine, no poetic or corporate language.
- Do not reuse phrasing from your recent replies:
{past}
{follow_up}
Reply with the message text only."""


def build_history_messages(conversation: List[Dict]) -> List[Dict]:
    """Convert to chat format, merging consecutive same-speaker messages."""
    out: List[Dict] = []
    for m in conversation:
        role = "user" if m["speaker"] == "customer" else "assistant"
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n" + m["text"]
        else:
            out.append({"role": role, "content": m["text"]})
    return out