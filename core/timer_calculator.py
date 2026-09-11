"""Timer utilities for response timing."""

import random


class TimerCalculator:
    """Calculate appropriate response delays."""
    
    def __init__(self):
        self.base_typing_speed = 0.05  # seconds per character
    
    def calculate_typing_delay(self, text_length: int) -> float:
        """Calculate realistic typing time."""
        return text_length * self.base_typing_speed + random.uniform(0.5, 1.5)
    
    def get_response_delay(self) -> float:
        """Get random delay before responding."""
        return random.uniform(1.0, 3.0)