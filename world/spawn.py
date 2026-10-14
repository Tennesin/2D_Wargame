"""world/spawn.py — поиск свободного места для появления техники.
Не знает про танки и стены: техника даёт footprint_at(x, y, angle) и ground_probes_at(x, y, angle),
а всё, что может занять место, передаётся в конструктор как функции-блокировщики obb -> bool."""
import math
import random
from dataclasses import dataclass

from engine import PX_PER_M, TAU

SEARCH_STEP_M = 4.0        # шаг колец и точек на кольце при поиске «рядом», м
CLEARANCE_M = 1.5          # запас свободного места вокруг техники, м
TRY_HEADINGS = 8           # сколько направлений корпуса пробуем, если направление не задано

@dataclass(frozen=True)
class SpawnPoint:
    x: float        # мировые px
    y: float
    angle: float    # угол корпуса, градусы (0 = вверх, по часовой)

class SpawnFinder:
    """terrain — TerrainMap (blocks_obb, speed_factor). blockers — функции obb -> bool
    (например walls.blocks_obb, fleet.blocks_obb)."""

    def __init__(self, terrain, blockers=()):
        self.terrain = terrain
        self.blockers = list(blockers)

    # ---------- проверка ----------
    def is_free(self, footprint, probes, clearance_px=CLEARANCE_M * PX_PER_M):
        """Свободно ли место под footprint (список obb) с запасом clearance_px
        и нет ли вязкой местности в точках probes [(x, y), ...]."""
        padded = [(x, y, hw + clearance_px, hl + clearance_px, ang) for x, y, hw, hl, ang in footprint]
        for obb in padded:
            if self.terrain.blocks_obb(obb):         # камни, глубокая вода, край мира
                return False
            for blocked in self.blockers:
                if blocked(obb):
                    return False
        return all(self.terrain.speed_factor(px, py) >= 1.0 for px, py in probes)

    def _try_place(self, vehicle, x, y, heading, rng):
        """Подходит ли точка (x, y) хоть с одним направлением корпуса. Возвращает SpawnPoint или None."""
        if heading is not None:
            angles = (heading % 360.0,)
        else:
            start = rng.uniform(0.0, 360.0)
            angles = tuple((start + k * 360.0 / TRY_HEADINGS) % 360.0 for k in range(TRY_HEADINGS))
        for angle in angles:
            if self.is_free(vehicle.footprint_at(x, y, angle), vehicle.ground_probes_at(x, y, angle)):
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