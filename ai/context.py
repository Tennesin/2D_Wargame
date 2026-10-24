"""ai/context.py — что мозг бота должен получить от игры, чтобы принимать решения."""
from typing import Any, NamedTuple

class BotContext(NamedTuple):
    targets: Any            # TargetSet: raycast по стенам, камням и технике
    terrain: Any            # TerrainMap
    walls: Any              # WallManager
    fleet: Any              # Fleet: .player и .bots
    budget: Any             # PlanBudget: лимит построений пути за кадр
    nav: Any                # TerrainNavCache: кэш рельефа для A*
    hazards: Any = None     # HazardBoard: зоны обстрела САУ
    settings: Any = None    # GameSettings: нужен friendly_fire

class PlanBudget:
    """Лимит построений пути A* за кадр на всех ботов."""

    def __init__(self, per_frame=1):
        self.per_frame = per_frame
        self.left = per_frame

    def new_frame(self):
        self.left = self.per_frame

    def try_take(self):
        if self.left > 0:
            self.left -= 1
            return True
        return False