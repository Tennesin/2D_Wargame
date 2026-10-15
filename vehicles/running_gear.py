"""vehicles/running_gear.py — ходовая часть: тип (данные) и состояние гусениц (сбитие, ремонт).
Про спрайты и физику не знает: Vehicle спрашивает отсюда, какая гусеница цела."""
from dataclasses import dataclass

from .chassis_params import TRACK_REPAIR_S

LEFT = "left"
RIGHT = "right"
TRACK_SIDES = (LEFT, RIGHT)      # порядок = порядок ремонта «по умолчанию»

@dataclass(frozen=True)
class RunningGear:
    """Тип ходовой части. Колёса потом добавятся сюда же отдельным экземпляром."""
    key: str
    armor_mm: float                     # добавка к броне борта (гусеница закрывает борт)
    repair_s: float = TRACK_REPAIR_S    # сколько секунд чинится одна гусеница

TRACKS = RunningGear("tracks", 20.0)

class TrackState:
    """Какие гусеницы сбиты и идёт ли ремонт. Чинить можно только одну гусеницу за раз."""

    def __init__(self):
        self.broken = set()             # {"left", "right"}
        self.repair_side = None         # какая гусеница чинится сейчас (None: ремонта нет)
        self.repair_left = 0.0          # сколько секунд осталось
        self.repair_total = 0.0

    def is_broken(self, side):
        return side in self.broken

    def break_track(self, side):
        """Сбить гусеницу. True, если она была цела (на уже сбитую повторно не действует)."""
        if side in self.broken:
            return False
        self.broken.add(side)
        return True

    def start_repair(self, duration, side=None):
        """Начать ремонт. side=None: первая сбитая по порядку TRACK_SIDES.
        Возвращает сторону, которую начали чинить, или None (ремонт уже идёт / чинить нечего)."""
        if self.repair_side is not None:
            return None                 # по очереди: вторая гусеница ждёт, пока кончится первая
        if side is None:
            side = next((s for s in TRACK_SIDES if s in self.broken), None)
        if side is None or side not in self.broken:
            return None
        self.repair_side = side
        self.repair_total = self.repair_left = duration
        return side

    def update(self, dt):
        """Ход ремонта. Возвращает сторону, которую только что досталась починить, иначе None."""
        if self.repair_side is None:
            return None
        self.repair_left -= dt
        if self.repair_left > 0.0:
            return None
        side = self.repair_side
        self.broken.discard(side)
        self.repair_side = None
        self.repair_left = self.repair_total = 0.0
        return side