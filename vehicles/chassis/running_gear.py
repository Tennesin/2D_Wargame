"""vehicles/chassis/running_gear.py — ходовая часть: тип (данные) и состояние гусениц (здоровье, сбитие, ремонт).
Про спрайты и физику не знает: Vehicle спрашивает отсюда, какая гусеница цела."""
from dataclasses import dataclass

from vehicles.chassis.params import TRACK_REPAIR_S, TRACK_REGEN_DELAY_S, TRACK_REGEN_PER_S

LEFT = "left"
RIGHT = "right"
TRACK_SIDES = (LEFT, RIGHT)      # порядок = порядок ремонта «по умолчанию»

@dataclass(frozen=True)
class RunningGear:
    """Тип ходовой части. Колёса потом добавятся сюда же отдельным экземпляром."""
    key: str
    repair_s: float = TRACK_REPAIR_S    # сколько секунд чинится одна гусеница

TRACKS = RunningGear("tracks")

class TrackState:
    """Здоровье гусениц в ДОЛЯХ шкалы (0..1), сбитие и ремонт. Чинить можно только одну гусеницу за раз.
    Доли, а не абсолютные HP: при смене спецификации (ползунки) ничего пересчитывать не нужно."""

    def __init__(self):
        self.health = {LEFT: 1.0, RIGHT: 1.0}
        self.repair_side = None         # какая гусеница чинится сейчас (None: ремонта нет)
        self.repair_left = 0.0          # сколько секунд осталось
        self.repair_total = 0.0
        self._idle = {LEFT: TRACK_REGEN_DELAY_S, RIGHT: TRACK_REGEN_DELAY_S}   # секунд с последнего урона

    @property
    def broken(self):
        """Множество сбитых сторон (0% здоровья). Интерфейс прежний: if tracks.broken, перебор."""
        return {s for s in TRACK_SIDES if self.health[s] <= 0.0}

    def is_broken(self, side):
        return self.health[side] <= 0.0

    def damage(self, side, frac):
        """Урон гусенице в долях её шкалы. Возвращает True, если она ТОЛЬКО ЧТО упала в ноль.
        Сбитая гусеница урона не принимает."""
        if frac <= 0.0 or self.is_broken(side):
            return False
        self._idle[side] = 0.0
        self.health[side] = max(0.0, self.health[side] - frac)
        return self.is_broken(side)

    def break_track(self, side):
        """Сбить гусеницу сразу (фон меню, отладка). True, если она была цела."""
        if self.is_broken(side):
            return False
        self.health[side] = 0.0
        return True

    def start_repair(self, duration, side=None):
        """Начать ремонт. side=None: первая сбитая по порядку TRACK_SIDES.
        Возвращает сторону, которую начали чинить, или None (ремонт уже идёт / чинить нечего)."""
        if self.repair_side is not None:
            return None                 # по очереди: вторая гусеница ждёт, пока кончится первая
        if side is None:
            side = next((s for s in TRACK_SIDES if self.is_broken(s)), None)
        if side is None or not self.is_broken(side):
            return None
        self.repair_side = side
        self.repair_total = self.repair_left = duration
        return side

    def update(self, dt):
        """Ремонт и регенерация. Возвращает сторону, которую только что досталось починить, иначе None."""
        repaired = self._update_repair(dt)
        self._regen(dt)
        return repaired

    def _update_repair(self, dt):
        if self.repair_side is None:
            return None
        self.repair_left -= dt
        if self.repair_left > 0.0:
            return None
        side = self.repair_side
        self.health[side] = 1.0         # после ремонта гусеница снова на 100%
        self._idle[side] = TRACK_REGEN_DELAY_S
        self.repair_side = None
        self.repair_left = self.repair_total = 0.0
        return side

    def _regen(self, dt):
        """Не сбитая и не полная гусеница восстанавливается, когда с последнего урона прошла пауза."""
        for side in TRACK_SIDES:
            h = self.health[side]
            self._idle[side] += dt
            if 0.0 < h < 1.0 and self._idle[side] >= TRACK_REGEN_DELAY_S:
                self.health[side] = min(1.0, h + TRACK_REGEN_PER_S * dt)