"""ai — боты: архетипы, подбор сборки, мозг. Не знает про окно и про пакет game."""
from .archetypes import Archetype, Skill, DEFAULT_SKILL, UNIVERSAL, ARCHETYPES
from .loadout import fit_loadout
from .brain import BotBrain
from .artillery_brain import ArtilleryBrain
from .factory import make_brain
from .bot import Bot
from .counter import threat_profile, counter_multipliers
from .context import BotContext, PlanBudget
from .nav_cache import TerrainNavCache
from .hazards import HazardBoard

__all__ = ["Archetype", "Skill", "DEFAULT_SKILL", "UNIVERSAL", "ARCHETYPES",
           "fit_loadout", "BotBrain", "ArtilleryBrain", "make_brain", "Bot",
           "threat_profile", "counter_multipliers", "HazardBoard",
           "PlanBudget", "TerrainNavCache", "BotContext"]