"""Make model output typeable like a human would type it.

Key point for copy-paste detection: Playwright can only emit real key events
for characters on the US keyboard layout. Curly quotes, em dashes, ellipsis
and emoji are injected via CDP insertText (an input event with no keydown),
which is what 'typed vs pasted' detectors look for. So we normalise to ASCII
before typing, and never use Ctrl+A / fill / paste.
"""

import asyncio
import random
import re

REPLACEMENTS = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": ", ", "\u2014": ", ", "\u2012": "-", "\u2212": "-",
    "\u2026": "...", "\u00a0": " ", "\u200b": "",
}

NEIGHBOURS = {
    "a": "qs", "b": "vn", "c": "xv", "d": "sf", "e": "wr", "f": "dg", "g": "fh", "h": "gj",
    "i": "uo", "j": "hk", "k": "jl", "l": "k", "m": "n", "n": "bm", "o": "ip", "p": "o",
    "q": "wa", "r": "et", "s": "ad", "t": "ry", "u": "yi", "v": "cb", "w": "qe", "x": "zc",
    "y": "tu", "z": "x",
}


def normalize_for_typing(text: str, allow_emoji: bool = False) -> str:
    for bad, good in REPLACEMENTS.items():
        text = text.replace(bad, good)
    text = re.sub(r"[*_`#>]+", "", text)                 # markdown
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s*,\s*,+", ",", text)               # ", ," left over from dash replacement
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    if allow_emoji:
        # keep ASCII + emoji only; note emoji are typed via insertText and may trip detection
        text = "".join(ch for ch in text if ord(ch) < 128 or 0x1F000 <= ord(ch) <= 0x1FAFF or 0x2600 <= ord(ch) <= 0x27BF)
    else:
        text = "".join(ch for ch in text if ord(ch) < 128)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return text


class HumanTyper:
    """Types one character at a time with variable cadence, pauses and occasional corrected typos."""

    def __init__(self, page, cpm_range=(190, 260), typo_rate: float = 0.02, pause_rate: float = 0.06):
        self.page = page
        self.cpm_range = cpm_range
        self.typo_rate = typo_rate
        self.pause_rate = pause_rate

    async def type(self, text: str, typos: bool = True):
        cpm = random.uniform(*self.cpm_range)
        base = 60.0 / cpm
        for ch in text:
            if typos and ch.isalpha() and random.random() < self.typo_rate:
                wrong = random.choice(NEIGHBOURS.get(ch.lower(), "e"))
                await self.page.keyboard.type(wrong)
                await asyncio.sleep(random.uniform(0.15, 0.45))
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.1, 0.3))
            await self.page.keyboard.type(ch)
            delay = max(0.04, min(base * 3, random.gauss(base, base * 0.35)))
            if ch in ".!?":
                delay += random.uniform(0.3, 0.9)
            elif ch == ",":
                delay += random.uniform(0.1, 0.4)
            elif ch == " " and random.random() < self.pause_rate:
                delay += random.uniform(0.3, 1.2)
            await asyncio.sleep(delay)

    def estimate_seconds(self, text: str) -> float:
        return len(text) * 60.0 / sum(self.cpm_range) * 2