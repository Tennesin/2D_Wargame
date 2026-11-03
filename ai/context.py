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
    squad: Any = None

STALE_FRAMES = 90

class PlanBudget:
    """Лимит построений пути A* за кадр на всех ботов. Кому отказали, тот встаёт в очередь
    и в следующих кадрах идёт раньше новых."""

    def __init__(self, per_frame=1):
        self.per_frame = per_frame
        self.left = per_frame
        self._frame = 0
        self._waiting = {}              # владелец -> кадр последнего запроса; порядок = очередь

    def new_frame(self):
        self.left = self.per_frame
        self._frame += 1
        if self._waiting:
            limit = self._frame - STALE_FRAMES
            for owner in [o for o, f in self._waiting.items() if f < limit]:
                del self._waiting[owner]

    def try_take(self, owner=None):
        waiting = self._waiting
        if owner is not None and owner in waiting:
            if list(waiting).index(owner) < self.left:     # впереди достаточно мало ждущих
                del waiting[owner]
                self.left -= 1
                return True
            waiting[owner] = self._frame                   # место в очереди сохраняется
            return False
        if self.left > len(waiting):                       # лимит остаётся после обслуживания очереди
            self.left -= 1
            return True
        if owner is not None:
            waiting[owner] = self._frame
        return False