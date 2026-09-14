"""Human-ish delays."""

import random


class TimerCalculator:
    def reading_delay(self, incoming_chars: int) -> float:
        """Time a person needs to read the message and decide what to say."""
        return min(25.0, random.uniform(2.5, 6.0) + incoming_chars * random.uniform(0.02, 0.04))

    def between_actions(self) -> float:
        return random.uniform(0.4, 1.2)