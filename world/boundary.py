"""world/boundary.py — граница мира как цель для снарядов: непробиваемые стены по периметру карты.
Рисует их WorldBoundsRenderer, а здесь только логика попаданий."""
from combat import resolve_hit
from engine import WORLD, PX_PER_M, TargetType, obb_segment_hit

BOUNDARY_THICK_M = 6.0           # толщина стены, как в bounds_render.WALL_THICK_M
BOUNDARY_ARMOR_MM = 3000.0       # практически непробиваема, как камень

class WorldBoundary:
    target_type = TargetType.TERRAIN

    @staticmethod
    def _bands():
        """Четыре прямоугольника стен снаружи мира: (x, y, half_w, half_l, angle).
        Верхняя и нижняя шире на толщину стены, поэтому углы закрыты без щелей."""
        hw, hh = WORLD.half_w_px, WORLD.half_h_px
        t = BOUNDARY_THICK_M * PX_PER_M
        h = t / 2.0
        return (
            (0.0, -(hh + h), hw + t, h, 0.0),     # верх
            (0.0, hh + h, hw + t, h, 0.0),        # низ
            (-(hw + h), 0.0, h, hh, 0.0),         # лево
            (hw + h, 0.0, h, hh, 0.0),            # право
        )

    def raycast(self, x0, y0, x1, y1, ignore=None):
        """Первая стена границы на отрезке: (self, t, normal) или None."""
        hw, hh = WORLD.half_w_px, WORLD.half_h_px
        if (abs(x0) <= hw and abs(y0) <= hh and abs(x1) <= hw and abs(y1) <= hh):
            return None                            # оба конца внутри мира: быстрый выход
        best = None
        for obb in self._bands():
            res = obb_segment_hit(obb, x0, y0, x1, y1)
            if res is not None and (best is None or res[0] < best[1]):
                best = (self, res[0], res[1])
        return best

    # ---------- интерфейс цели для снарядов ----------
    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        return resolve_hit(penetration, BOUNDARY_ARMOR_MM, cos_impact)

    def take_hit(self, penetration, damage, cos_impact=1.0, normal=None, min_frac=0.0, caliber_mm=0.0):
        """Граница неразрушаема."""
        return 0.0