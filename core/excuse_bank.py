"""Persona-aligned re-engagement messages (why she went quiet + a hook)."""

import asyncio
import random
from typing import List


class DynamicExcuseGenerator:
    PERSONA_SCENARIOS = {
        "store attendant": ["restocking shelves", "helping a difficult customer", "counting inventory",
                            "cleaning up a spill", "organizing the back room", "dealing with a broken scanner"],
        "teacher": ["grading papers", "preparing lesson plans", "talking to a parent",
                    "helping a student after class", "filling out reports", "calming down a student"],
        "nurse": ["checking on a patient", "filling out charts", "restocking medical supplies",
                  "talking to a doctor", "calming a family member"],
        "waitress": ["taking a large order", "cleaning up a table", "helping in the kitchen",
                     "dealing with a difficult customer", "balancing the register"],
        "receptionist": ["answering phones", "scheduling appointments", "organizing files",
                         "greeting a client", "fixing the printer"],
        "barista": ["making a complicated order", "restocking coffee beans", "cleaning the espresso machine",
                    "wiping down the counter"],
        "bartender": ["mixing a complicated drink", "restocking the liquor shelf", "cleaning glasses", "checking IDs"],
        "hair stylist": ["mixing hair color", "cleaning up cut hair", "washing towels", "setting up a station"],
        "fitness instructor": ["setting up equipment", "wiping down machines", "cleaning yoga mats"],
        "student": ["finishing an assignment", "sitting through a lecture", "a group project call"],
        "default": ["dealing with a work thing", "cleaning up a mess", "finding something I misplaced",
                    "helping a colleague", "a phone call that would not end"],
    }

    TEMPLATES = {
        "casual": [
            "Sorry, got pulled away {s} and completely lost track of time. Back now and all yours for a bit. What have you been getting up to while I was gone?",
            "Ugh, {s} took forever and I kept thinking I should get back to you. Anyway I am here now. Tell me something good that happened to you today?",
        ],
        "flirty": [
            "Got stuck {s} and my mind kept drifting back to you the whole time, which is not very professional of me. What do you think I was picturing?",
            "Was {s} and caught myself smiling at my phone like an idiot waiting for you. So what would you have done to distract me if you were here?",
        ],
        "sexual": [
            "Was {s} and could not stop thinking about you, got myself so worked up in the middle of it that I had to sneak off for a minute. Tell me exactly what you would do to me if you walked in right now?",
            "Got caught up {s} but honestly all I could think about was your hands on me. I am still wet just typing this. How hard are you right now?",
        ],
    }

    def __init__(self, deepseek_client, player_occupation: str = "", min_chars: int = 100, max_chars: int = 320):
        self.deepseek = deepseek_client
        self.player_occupation = (player_occupation or "").lower()
        self.min_chars, self.max_chars = min_chars, max_chars
        self.used_excuses: List[str] = []
        self.used_phrases: set = set()
        self.scenarios = self._get_scenarios()

    def _get_scenarios(self) -> List[str]:
        for occ, scenarios in self.PERSONA_SCENARIOS.items():
            if occ != "default" and occ in self.player_occupation:
                return scenarios
        return self.PERSONA_SCENARIOS["default"]

    async def generate_excuse(self, category: str) -> str:
        scenario = random.choice(self.scenarios)
        tone = {
            "casual": f"warm and friendly. Mention: {scenario}",
            "flirty": f"playful and teasing with light innuendo. You got distracted thinking about him while: {scenario}",
            "sexual": f"explicit and erotic. Connect {scenario} to thinking about him sexually",
        }.get(category, f"warm and friendly. Mention: {scenario}")
        avoid = ""
        if self.used_excuses:
            avoid = "AVOID anything resembling these earlier messages:\n" + "\n".join(f"- {e[:80]}" for e in self.used_excuses[-5:])
        job = self.player_occupation or "working woman"
        prompt = f"""You are a {job} texting a man on a dating site. He has gone quiet. Write ONE message ({self.min_chars}-{self.max_chars} characters) explaining briefly why you were away, then hook him with an open question.
SCENARIO: {scenario}
TONE: {tone}
RULES: sound natural for a {job}; plain text; no emojis; no em dashes; no exclamation marks; end with a question; completely different from earlier messages.
{avoid}
Reply with the message only."""
        result = await asyncio.to_thread(self.deepseek.generate, prompt,
                                         [{"role": "user", "content": "Write the message now."}], None, 0.8, 200)
        if result["ok"]:
            excuse = result["text"].strip()
            if self.min_chars <= len(excuse) <= self.max_chars and self._is_unique_enough(excuse):
                self._remember(excuse)
                return excuse
        return self._fallback(category, scenario)

    def _is_unique_enough(self, excuse: str) -> bool:
        low = excuse.lower()
        if low in (e.lower() for e in self.used_excuses):
            return False
        words = low.split()
        return not any(" ".join(words[i:i + 3]) in self.used_phrases for i in range(len(words) - 2))

    def _remember(self, text: str):
        self.used_excuses.append(text)
        words = text.lower().split()
        for i in range(len(words) - 2):
            self.used_phrases.add(" ".join(words[i:i + 3]))

    def _fallback(self, category: str, scenario: str) -> str:
        options = [t.format(s=scenario) for t in self.TEMPLATES.get(category, self.TEMPLATES["casual"])]
        random.shuffle(options)
        for opt in options:
            if opt.lower() not in (e.lower() for e in self.used_excuses):
                self._remember(opt)
                return opt
        return options[0]

    def clear_history(self):
        self.used_excuses, self.used_phrases = [], set()