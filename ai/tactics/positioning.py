"""ai/tactics/positioning.py — огневая позиция: точка на нужной дистанции от цели с чистой линией огня."""
import math

from engine import PX_PER_M, WORLD, bearing_deg, heading_vector, shortest_angle_diff

RING_POINTS = 16            # направлений вокруг цели
BAND_K = (0.9, 1.0, 1.1)    # доли желаемой дистанции, на которых пробуем точки
RANGE_K = 0.92              # дальше этой доли дальности снаряда позицию не берём
WORLD_MARGIN_M = 10.0
ALLY_GAP_M = 14.0           # ближе к союзнику (или к его позиции) точку не берём
TRAVEL_W = 1.0              # цена метра пути
BAND_W = 20.0               # штраф за отход от точной дистанции (за единицу доли)
SLOT_W = 0.15               # м за градус отклонения от своего сектора (Squad)
ASPECT_W = 0.12             # м за градус отклонения от желаемого ракурса (фланг)
KEEP_ENEMY_SHIFT_M = 10.0   # цель ушла дальше этого: позицию пересчитать
MAX_AGE_S = 3.0
RETRY_S = 1.0               # пауза после неудачного поиска

def has_line(ctx, me, enemy, x=None, y=None):
    """Первым на отрезке от (x, y) до центра врага стоит сам враг (стены и камни закрывают, свои нет)."""
    x = me.x if x is None else x
    y = me.y if y is None else y
    hit = ctx.targets.raycast(x, y, enemy.x, enemy.y, ignore=me)
    return hit is not None and hit[0] is enemy

class FirePositionPlanner:
    def __init__(self):
        self.point = None
        self._age = 0.0
        self._enemy_xy = None
        self._cooldown = 0.0

    def tick(self, dt):
        self._age += dt
        if self._cooldown > 0.0:
            self._cooldown -= dt

    def invalidate(self):
        self.point = None

    def get(self, me, enemy, ctx, desired_px, need_line=True, slot_deg=None, aspect_deg=None):
        """Позиция (x, y) или None. aspect_deg: желаемый знаковый ракурс относительно лба цели (+ справа)."""
        if self.point is not None and self._still_good(me, enemy, ctx, need_line):
            return self.point
        if self._cooldown > 0.0:
            return None
        self.point = self._search(me, enemy, ctx, desired_px, need_line, slot_deg, aspect_deg)
        self._age = 0.0
        self._enemy_xy = (enemy.x, enemy.y)
        if self.point is None:
            self._cooldown = RETRY_S
        return self.point

    def _still_good(self, me, enemy, ctx, need_line):
        ex, ey = self._enemy_xy
        if (self._age > MAX_AGE_S
                or math.hypot(enemy.x - ex, enemy.y - ey) > KEEP_ENEMY_SHIFT_M * PX_PER_M):
            return False
        return not need_line or has_line(ctx, me, enemy, *self.point)

    @staticmethod
    def _others(me, ctx):
        """Позиции союзников и их уже выбранные огневые точки."""
        pts = []
        for b in ctx.fleet.bots:
            t = b.tank
            if t is me or not t.alive:
                continue
            pts.append((t.x, t.y))
            p = getattr(getattr(b.brain, "firepos", None), "point", None)
            if p is not None:
                pts.append(p)
        return pts

    def _search(self, me, enemy, ctx, desired_px, need_line, slot_deg, aspect_deg):
        ex, ey = enemy.x, enemy.y
        reach = me.spec.SHELL_RANGE_PX * RANGE_K
        radius = min(desired_px, reach)
        hw = WORLD.half_w_px - WORLD_MARGIN_M * PX_PER_M
        hh = WORLD.half_h_px - WORLD_MARGIN_M * PX_PER_M
        gap2 = (ALLY_GAP_M * PX_PER_M) ** 2
        others = self._others(me, ctx)
        start = bearing_deg(ex, ey, me.x, me.y)          # от цели в мою сторону

        best, best_score = None, None
        for k in range(RING_POINTS):
            ang = (start + 360.0 * k / RING_POINTS) % 360.0
            dx, dy = heading_vector(ang)
            for band in BAND_K:
                r = radius * band
                if r > reach:
                    continue
                px, py = ex + dx * r, ey + dy * r
                if abs(px) > hw or abs(py) > hh:
                    continue
                if any((px - ox) ** 2 + (py - oy) ** 2 < gap2 for ox, oy in others):
                    continue
                hull = me.footprint_at(px, py, bearing_deg(px, py, ex, ey))[0]
                if ctx.terrain.blocks_obb(hull) or ctx.walls.blocks_obb(hull):
                    continue
                if ctx.terrain.speed_factor(px, py) < 0.99:
                    continue                              # не стоим в воде и грязи
                if need_line and not has_line(ctx, me, enemy, px, py):
                    continue
                score = math.hypot(px - me.x, py - me.y) / PX_PER_M * TRAVEL_W + abs(band - 1.0) * BAND_W
                if slot_deg is not None:
                    score += abs(shortest_angle_diff(ang, slot_deg)) * SLOT_W
                if aspect_deg is not None:
                    seen = shortest_angle_diff(ang, enemy.hull_angle)    # + справа от лба цели
                    score += abs(shortest_angle_diff(seen, aspect_deg)) * ASPECT_W
                if best_score is None or score < best_score:
                    best, best_score = (px, py), score
        return best