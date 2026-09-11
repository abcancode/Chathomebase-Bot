"""Dynamic excuse generator using DeepSeek AI — aligned with player persona."""

import random
from typing import List, Optional


class DynamicExcuseGenerator:
    """Generates unique, persona-aligned excuses on-demand."""
    
    PERSONA_SCENARIOS = {
        "store attendant": [
            "restocking shelves", "helping a difficult customer", "counting inventory",
            "cleaning up a spill", "unlocking the storage room", "organizing the back room",
            "price-checking an item", "assisting with returns", "restocking the cooler",
            "dealing with a broken scanner", "helping find a product", "cleaning the aisles",
            "restocking register tape", "organizing the display", "checking expiration dates"
        ],
        "teacher": [
            "grading papers", "preparing lesson plans", "talking to a parent",
            "helping a student after class", "organizing classroom supplies", "filling out reports",
            "setting up a projector", "finding lost homework", "calming down a student"
        ],
        "nurse": [
            "checking on a patient", "filling out charts", "restocking medical supplies",
            "talking to a doctor", "calming a family member", "organizing the supply closet"
        ],
        "waitress": [
            "taking a large order", "cleaning up a table", "helping in the kitchen",
            "restocking napkins", "dealing with a difficult customer", "balancing the register"
        ],
        "receptionist": [
            "answering phones", "scheduling appointments", "organizing files",
            "greeting a client", "fixing the printer", "restocking office supplies"
        ],
        "barista": [
            "making a complicated order", "restocking coffee beans", "cleaning the espresso machine",
            "wiping down the counter", "organizing the pastry display", "grinding fresh beans"
        ],
        "bartender": [
            "mixing a complicated drink", "restocking the liquor shelf", "cleaning glasses",
            "wiping down the bar", "checking IDs", "organizing the cooler"
        ],
        "hair stylist": [
            "mixing hair color", "cleaning up cut hair", "organizing styling products",
            "washing towels", "setting up a station", "finding the right tool"
        ],
        "fitness instructor": [
            "setting up equipment", "wiping down machines", "organizing the weight room",
            "finding the right music", "cleaning yoga mats", "restocking water bottles"
        ],
        "default": [
            "organizing my workspace", "dealing with a technical issue", "restocking supplies",
            "cleaning up a mess", "finding something I misplaced", "helping a colleague"
        ]
    }
    
    def __init__(self, deepseek_client, player_occupation: str = ""):
        self.deepseek = deepseek_client
        self.player_occupation = player_occupation.lower()
        self.used_excuses: List[str] = []
        self.used_phrases: set = set()
        self.scenarios = self._get_scenarios()
        
    def _get_scenarios(self) -> List[str]:
        for occupation, scenarios in self.PERSONA_SCENARIOS.items():
            if occupation in self.player_occupation:
                return scenarios
        return self.PERSONA_SCENARIOS["default"]
    
    def generate_excuse(self, category: str, used: List[str] = None) -> Optional[str]:
        if used:
            self.used_excuses.extend(used)
        
        scenario = random.choice(self.scenarios)
        
        tone_instructions = {
            "casual": f"warm and friendly. Mention: {scenario}",
            "flirty": f"playful and teasing with light innuendo. Mention being distracted by: {scenario}",
            "sexual": f"explicit and erotic. Connect {scenario} to sexual thoughts"
        }
        
        tone = tone_instructions.get(category, tone_instructions["casual"])
        
        used_summary = ""
        if self.used_excuses:
            recent = self.used_excuses[-5:]
            used_summary = "AVOID these scenarios:\n" + "\n".join(f"- {e[:60]}..." for e in recent)
        
        prompt = f"""You are a {self.player_occupation}. Write a short excuse (160-260 characters) explaining why you were delayed.

SCENARIO: {scenario}
TONE: {tone}

REQUIREMENTS:
- Sound natural for a {self.player_occupation}
- Reference the scenario authentically
- End with open-ended question
- NO em dashes, NO exclamation marks, NO filler sounds
- COMPLETELY different from previous excuses

{used_summary}

Write ONE excuse:"""
        
        result = self.deepseek.generate(
            system_prompt=prompt,
            history=[{"role": "user", "content": "Generate excuse"}],
            user_message="",
            temperature=0.7
        )
        
        if result["ok"]:
            excuse = result["text"].strip()
            if 150 <= len(excuse) <= 300 and self._is_unique_enough(excuse):
                self.used_excuses.append(excuse)
                self._extract_phrases(excuse)
                return excuse
        
        return self._fallback_excuse(category, scenario)
    
    def _is_unique_enough(self, excuse: str) -> bool:
        excuse_lower = excuse.lower()
        if excuse_lower in [e.lower() for e in self.used_excuses]:
            return False
        
        words = excuse_lower.split()
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            if phrase in self.used_phrases:
                return False
        return True
    
    def _extract_phrases(self, text: str):
        words = text.lower().split()
        for i in range(len(words) - 2):
            phrase = " ".join(words[i:i+3])
            self.used_phrases.add(phrase)
    
    def _fallback_excuse(self, category: str, scenario: str) -> str:
        templates = {
            "store attendant": {
                "casual": [
                    f"Got caught up {scenario} and lost track of time. What have you been up to?",
                    f"Had to stop and deal with {scenario}. What's something that interrupted your day recently?",
                    f"Got distracted by {scenario}. When's the last time you got completely sidetracked?"
                ],
                "flirty": [
                    f"Was {scenario} and kept imagining you watching me. What do you picture me doing right now?",
                    f"Got distracted {scenario} and started thinking about your hands on me. Where would you touch me first?"
                ],
                "sexual": [
                    f"Was {scenario} and started touching myself thinking about you. How hard are you right now?",
                    f"Got distracted {scenario} and my panties got soaked imagining you. What would you do if you saw?"
                ]
            }
        }
        
        occupation_key = None
        for occ in self.PERSONA_SCENARIOS.keys():
            if occ in self.player_occupation:
                occupation_key = occ
                break
        
        if occupation_key and occupation_key in templates:
            options = templates[occupation_key].get(category, templates[occupation_key]["casual"])
        else:
            options = {
                "casual": [f"Got caught up with {scenario}. What have you been up to?"],
                "flirty": [f"Was {scenario} and started thinking about you. What do you picture me doing?"],
                "sexual": [f"Was {scenario} and started touching myself thinking about you. How hard are you?"]
            }.get(category, [f"Got caught up with {scenario}. What have you been up to?"])
        
        for option in options:
            if option.lower() not in [e.lower() for e in self.used_excuses]:
                self.used_excuses.append(option)
                return option
        
        base = random.choice(options)
        modifiers = [" just now", " a few minutes ago", " earlier"]
        return base + random.choice(modifiers)
    
    def clear_history(self):
        self.used_excuses = []
        self.used_phrases = set()