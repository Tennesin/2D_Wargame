"""world/spawn.py — поиск свободного места для появления техники.
Не знает про танки и стены: техника даёт footprint_at(x, y, angle), а всё, что может занять место,
подключается как функции-блокировщики obb -> bool."""
import math
import random
from dataclasses import dataclass

from engine import PX_PER_M, heading_vector

TAU = 2.0 * math.pi

SEARCH_STEP_M = 4.0        # шаг колец и точек на кольце при поиске «рядом», м
CLEARANCE_M = 1.5          # запас свободного места вокруг техники, м
TRY_HEADINGS = 8           # сколько направлений корпуса пробуем, если направление не задано
RANDOM_ATTEMPTS = 60       # попыток при поиске случайной точки в круге
BODY_REACH = 0.8           # какую долю полудлины корпуса берём для проверки грунта (как в Tank._sample_terrain)

@dataclass(frozen=True)
class SpawnPoint:
    x: float        # мировые px
    y: float
    angle: float    # угол корпуса, градусы (0 = вверх, по часовой)

class SpawnFinder:
    """terrain — TerrainMap (blocks_obb, speed_factor). blockers — функции obb -> bool
    (например walls.blocks_obb, other_tank.hits_obb). Список живой: блокировщики можно добавлять позже."""

    def __init__(self, terrain, blockers=()):
        self.terrain = terrain
        self.blockers = list(blockers)

    def add_blocker(self, blocker):
        self.blockers.append(blocker)

    # ---------- проверка ----------
    def is_free(self, footprint, clearance_px=CLEARANCE_M * PX_PER_M):
        """Свободно ли место под footprint (список obb, корпус первым) с запасом clearance_px."""
        padded = [(x, y, hw + clearance_px, hl + clearance_px, ang) for x, y, hw, hl, ang in footprint]

        for obb in padded:
            if self.terrain.blocks_obb(obb):         # камни, глубокая вода, край мира
                return False
            for blocked in self.blockers:
                if blocked(obb):
                    return False

        # вязкая местность под корпусом: три точки вдоль оси, как при расчёте скорости танка
        hx, hy, _, hl, ang = padded[0]
        fx, fy = heading_vector(ang)
        for d in (-hl * BODY_REACH, 0.0, hl * BODY_REACH):
            if self.terrain.speed_factor(hx + fx * d, hy + fy * d) < 1.0:
                return False
        return True

    def _try_place(self, vehicle, x, y, heading, rng):
        """Подходит ли точка (x, y) хоть с одним направлением корпуса. Возвращает SpawnPoint или None."""
        if heading is not None:
            angles = (heading % 360.0,)
        else:
            start = rng.uniform(0.0, 360.0)
            angles = tuple((start + k * 360.0 / TRY_HEADINGS) % 360.0 for k in range(TRY_HEADINGS))
        for angle in angles:
            if self.is_free(vehicle.footprint_at(x, y, angle)):
                return SpawnPoint(x, y, angle)
        return None

    # ---------- поиск ----------
    def find_near(self, vehicle, cx, cy, max_radius_m, heading=None, rng=None):
        """Ближайшее к (cx, cy) свободное место в радиусе max_radius_m (центр, затем кольца наружу).
        Возвращает SpawnPoint или None, если места нет."""
        rng = rng or random
        step = SEARCH_STEP_M * PX_PER_M
        max_r = max_radius_m * PX_PER_M

        spot = self._try_place(vehicle, cx, cy, heading, rng)
        if spot is not None:
            return spot

        r = step
        while r <= max_r:
            count = max(6, int(TAU * r / step))
            start = rng.uniform(0.0, TAU)                  # без этого результат всегда «в одну сторону»
            for i in range(count):
                a = start + TAU * i / count
                spot = self._try_place(vehicle, cx + math.cos(a) * r, cy + math.sin(a) * r, heading, rng)
                if spot is not None:
                    return spot
            r += step
        return None

    def find_in_area(self, vehicle, cx, cy, radius_m, heading=None, rng=None, attempts=RANDOM_ATTEMPTS):
        """Случайное свободное место в круге (для зон появления команд). Точки распределены равномерно
        по площади. Если за attempts попыток ничего не нашлось, возвращает None."""
        rng = rng or random
        radius = radius_m * PX_PER_M
        for _ in range(attempts):
            r = radius * math.sqrt(rng.random())
            a = rng.uniform(0.0, TAU)
            spot = self._try_place(vehicle, cx + math.cos(a) * r, cy + math.sin(a) * r, heading, rng)
            if spot is not None:
                return spot
        return None