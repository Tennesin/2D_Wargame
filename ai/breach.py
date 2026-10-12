"""ai/breach.py — прорыв стены, которая мешает: выбор точки, проверка выгоды, подъезд."""
import math

from engine import PX_PER_M, heading_vector, bearing_deg
from .gunnery import seconds_to_break, BREACH_MAX_S, MIN_USEFUL_DAMAGE

BREACH_RANGE_M = 14.0        # с какого расстояния стреляем по стене
BREACH_RESERVE_S = 6.0       # запас времени на доводку и рикошеты

class BreachPlanner:
    def __init__(self):
        self.wall = None                    # ломаемая стена (None: прорыва нет)
        self.point = (0.0, 0.0)             # куда целимся (мировые px)
        self._left = 0.0

    def tick(self, dt):
        if self.wall is not None:
            self._left -= dt

    def finished(self):
        """Стена рухнула, пропала или время вышло."""
        return self.wall is None or not self.wall.alive or self._left <= 0.0

    def stop(self):
        self.wall = None

    def move(self, me):
        """Курс на стену; подъезжаем до BREACH_RANGE_M, дальше стоим и стреляем: (курс, газ)."""
        px, py = self.point
        heading = bearing_deg(me.x, me.y, px, py)
        far = math.hypot(px - me.x, py - me.y) > BREACH_RANGE_M * PX_PER_M
        return heading, (1.0 if far else 0.0)

    def begin_ahead(self, me, ctx, bearing, look_px):
        """Есть ли по курсу bearing стена, которую выгодно ломать (проверка лучом).
        Стена должна быть ПЕРВОЙ целью на линии: камень или танк впереди означают «ломать нечего»."""
        fx, fy = heading_vector(bearing)
        tx, ty = me.x + fx * look_px, me.y + fy * look_px
        first = ctx.targets.raycast(me.x, me.y, tx, ty, ignore=me)
        if first is None:
            return False
        hit = ctx.walls.raycast(me.x, me.y, tx, ty)
        if hit is None or hit[0] is not first[0]:
            return False
        wall, t, normal = hit
        point = (me.x + (tx - me.x) * t, me.y + (ty - me.y) * t)
        return self._begin(me, wall, point, normal, bearing)

    def begin_from_path(self, me, ctx, wall):
        """Стена из пути A*: целимся в ближайшую к боту точку её поверхности по линии на центр стены.
        Если на этой линии первой стоит что-то другое (камень, танк), ломать отсюда нельзя."""
        first = ctx.targets.raycast(me.x, me.y, wall.x, wall.y, ignore=me)
        if first is None or first[0] is not wall:
            return False
        res = wall.segment_hit(me.x, me.y, wall.x, wall.y)
        if res is None:
            return False
        t, normal = res
        point = (me.x + (wall.x - me.x) * t, me.y + (wall.y - me.y) * t)
        return self._begin(me, wall, point, normal, bearing_deg(me.x, me.y, wall.x, wall.y))

    def _begin(self, me, wall, point, normal, bearing):
        """Проверка по реальному углу попадания; при успехе запоминаем стену и точку."""
        fx, fy = heading_vector(bearing)
        cos_i = 1.0 if normal is None else abs(fx * normal[0] + fy * normal[1])
        secs = seconds_to_break(me, wall, cos_i, normal, MIN_USEFUL_DAMAGE)
        if secs is None or secs > BREACH_MAX_S:
            return False                                          # не пробить или слишком долго
        self.wall = wall
        self.point = point
        self._left = secs + BREACH_RESERVE_S
        return True