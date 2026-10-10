"""ai/bot.py — связка «танк + мозг»."""
from dataclasses import dataclass

@dataclass
class Bot:
    tank: object
    brain: object