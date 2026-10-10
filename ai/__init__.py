"""ai — боты: архетипы, подбор сборки, мозг. Не знает про окно и про пакет game."""
from .archetypes import Archetype, Skill, DEFAULT_SKILL, UNIVERSAL, ARCHETYPES
from .loadout import fit_loadout, BASE_BUDGET
from .brain import BotBrain
from .bot import Bot
from .counter import threat_profile, counter_multipliers

__all__ = ["Archetype", "Skill", "DEFAULT_SKILL", "UNIVERSAL", "ARCHETYPES",
           "fit_loadout", "BASE_BUDGET", "BotBrain", "Bot",
           "threat_profile", "counter_multipliers"]