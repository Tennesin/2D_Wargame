"""ai — боты: архетипы, подбор сборки, мозг. Не знает про окно и про пакет game."""
from .archetypes import Archetype, Skill, DEFAULT_SKILL, UNIVERSAL, ARCHETYPES
from .loadout import fit_loadout
from .brain import BotBrain
from .bot import Bot
from .counter import threat_profile, counter_multipliers
from .pathfinding import PlanBudget, TerrainNavCache
from .context import BotContext

__all__ = ["Archetype", "Skill", "DEFAULT_SKILL", "UNIVERSAL", "ARCHETYPES",
           "fit_loadout", "BotBrain", "Bot", "threat_profile", "counter_multipliers",
           "PlanBudget", "TerrainNavCache", "BotContext"]