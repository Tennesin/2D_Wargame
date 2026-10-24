"""ai/factory.py — выбор мозга по виду техники архетипа."""
from engine import VehicleKind
from .artillery_brain import ArtilleryBrain
from .brain import BotBrain

def make_brain(arch, skill, rng):
    """Мозг для архетипа: у САУ свой, у остальных общий BotBrain."""
    if arch.kind is VehicleKind.SPG:
        return ArtilleryBrain(arch, skill, rng)
    return BotBrain(arch, skill, rng)