"""ai/context.py — что мозг бота должен получить от игры, чтобы принимать решения."""
from typing import Any, NamedTuple


class BotContext(NamedTuple):
    targets: Any  # TargetSet: raycast по стенам, камням и технике
    terrain: Any  # TerrainMap
    walls: Any  # WallManager
    fleet: Any  # Fleet: .player и .bots
    budget: Any  # PlanBudget: лимит построений пути за кадр
    nav: Any  # TerrainNavCache: кэш рельефа для A*
