"""vehicles/chassis/hit_model.py — модель попаданий по технике:
луч снаряда, грань и плита брони, приведённая броня."""
import math

from engine import (
    heading_vector, convex_segment_hit, to_local_frame, vec_to_local, vec_from_local, PX_PER_M,
)
from combat import resolve_hit, effective_armor
from vehicles.chassis.params import ARMOR_K, SCREEN_RAY_BACK_M, SCREEN_RAY_FWD_M
from vehicles.chassis.screens import ray_crossings

class HitModelMixin:

    def _local_parts(self):
        """Выпуклые участки для попаданий в метрах корпуса (центр корпуса = (0, 0), перед = -v)."""
        return self.spec.layout.hit_parts

    def _enters_track_from_inside(self, part, normal):
        """True, если снаряд вошёл бы в гусеницу через её внутреннюю грань."""
        if normal is None:
            return False
        xs = [p[0] for p in part]
        mid = (min(xs) + max(xs)) / 2.0
        if abs(abs(mid) - self.spec.layout.track_x) > 0.05:
            return False  # это не гусеница
        side = 1.0 if mid > 0.0 else -1.0
        return normal[0] * side < -0.5  # нормаль смотрит к оси танка

    def raycast(self, x0, y0, x1, y1):
        """Пересечение отрезка с корпусом: (self, t, normal) или None."""
        cx, cy, _, _, ang = self.hull_obb()
        k = self.spec.HULL_SCALE * PX_PER_M
        u0, v0 = to_local_frame(x0, y0, cx, cy, ang, k)
        u1, v1 = to_local_frame(x1, y1, cx, cy, ang, k)
        best = None
        for part in self._local_parts():
            res = convex_segment_hit(part, u0, v0, u1, v1)
            if res is None or self._enters_track_from_inside(part, res[1]):
                continue
            if best is None or res[0] < best[0]:
                best = res
        if best is None:
            return None
        t, n = best
        if n is not None:
            n = vec_from_local(n[0], n[1], ang)      # масштаб однородный, нормаль только поворачиваем
        return self, t, n

    def zone_at(self, normal, hull_angle=None):
        """Какая грань корпуса принимает удар: "front" / "side" / "rear"."""
        if normal is None:                      # выстрел начался внутри корпуса
            return "side"
        fx, fy = heading_vector(self.hull_angle if hull_angle is None else hull_angle)
        along = normal[0] * fx + normal[1] * fy
        if along > 0.5:
            return "front"
        if along < -0.5:
            return "rear"
        return "side"

    def plate_at(self, normal, hull_angle=None):
        """Плита брони, принявшая удар: та, чья наружная нормаль ближе всего к normal (мировая)."""
        layout = self.spec.layout
        if normal is None:
            return next((p for p in layout.plates if p.zone == "side"), layout.plates[0])
        ang = self.hull_angle if hull_angle is None else hull_angle
        nu, nv = vec_to_local(normal[0], normal[1], ang)
        return layout.plate_by_normal(nu, nv)

    def plate_at_point(self, x, y):
        """Плита брони, ближайшая к мировой точке (x, y)."""
        u, v = self._to_hull_local(x, y)
        best, best_d = None, None
        for p in self.spec.layout.plates:
            ax, ay = p.a
            bx, by = p.b
            ex, ey = bx - ax, by - ay
            ln2 = ex * ex + ey * ey
            t = 0.0 if ln2 < 1e-9 else max(0.0, min(1.0, ((u - ax) * ex + (v - ay) * ey) / ln2))
            d = math.hypot(ax + ex * t - u, ay + ey * t - v)
            if best_d is None or d < best_d:
                best, best_d = p, d
        return best

    def zone_at_point(self, x, y):
        """Грань ("front" / "side" / "rear"), принявшая удар в мировой точке (x, y)."""
        return self.plate_at_point(x, y).zone

    def armor_at(self, normal, hull_angle=None):
        """Броня грани, в которую попали."""
        s = self.spec
        zone = self.zone_at(normal, hull_angle)
        base = {"front": s.front, "side": s.side, "rear": s.rear}[zone]
        plate = self.plate_at(normal, hull_angle)
        base *= plate.k
        if zone == "front":
            base += s.screen_mm
        if zone == "side":
            base += s.track_mm
        return base * ARMOR_K * self.mods.armor_k

    def armor_along(self, from_deg, hull_deg=None, lateral=0.0):
        """Броня и косинус угла для луча, пришедшего с азимута from_deg (от этой техники к стрелку)."""
        if hull_deg is None:
            hull_deg = self.hull_angle
        wx, wy = heading_vector(from_deg)
        ex, ey = vec_to_local(wx, wy, hull_deg)       # единичный вектор на стрелка в системе корпуса
        tx, ty = -ey * lateral, ex * lateral          # точка прицеливаниdddddddddddddddddddddddddя
        reach = 50.0                                  # м: заведомо больше корпуса
        best = None
        for part in self._local_parts():
            res = convex_segment_hit(part, tx + ex * reach, ty + ey * reach,
                                     tx - ex * reach, ty - ey * reach)
            if res is None or self._enters_track_from_inside(part, res[1]):
                continue
            if best is None or res[0] < best[0]:
                best = res
        nu, nv = best[1]
        cos_i = abs(ex * nu + ey * nv)
        normal = vec_from_local(nu, nv, hull_deg)
        # экраны на пути до входа в корпус: луч идёт от стрелка к цели, вход на best[0] * span
        span = 2.0 * reach
        lost = 0.0
        for t, s, c in ray_crossings(self.spec.screens, tx + ex * reach, ty + ey * reach, -ex, -ey, 0.0, span):
            if t <= best[0] * span + SCREEN_RAY_FWD_M:
                lost += effective_armor(s.mm * self.mods.armor_k, c)
        return self.armor_at(normal, hull_deg), cos_i, lost

    def facing_normal(self, x, y):
        """Наружная нормаль грани, ближайшей к точке (x, y)."""
        cx, cy, hw, hl, ang = self.hull_obb()
        fx, fy = heading_vector(ang)
        rx, ry = -fy, fx                                  # вправо от корпуса
        dx, dy = x - cx, y - cy
        along = dx * fx + dy * fy                         # вперёд (+) / назад (-)
        across = dx * rx + dy * ry                        # вправо (+) / влево (-)
        if abs(along) - hl > abs(across) - hw:
            sign = 1.0 if along >= 0.0 else -1.0
            return fx * sign, fy * sign                   # лоб или корма
        sign = 1.0 if across >= 0.0 else -1.0
        return rx * sign, ry * sign                       # правый или левый борт

    def screens_along_world(self, x, y, dx, dy):
        """Листы на пути снаряда через точку попадания (x, y) в направлении (dx, dy)."""
        screens = self.spec.screens
        if not screens:
            return ()
        u, v = self._to_hull_local(x, y)
        du, dv = vec_to_local(dx, dy, self.hull_angle)
        k = self.mods.armor_k
        return [(s.mm * k, cos) for _, s, cos in
                ray_crossings(screens, u, v, du, dv, SCREEN_RAY_BACK_M, SCREEN_RAY_FWD_M)]

    def armor_facing(self, x, y):
        """Броня грани, ближайшей к точке (x, y) (мм). Нужна взрывам по площади: у них нет «луча»."""
        return self.armor_at(self.facing_normal(x, y))

    def armor_at_point(self, x, y):
        """Броня плиты, ближайшей к мировой точке (x, y): учитывает ползунки, накладки, гусеницы и улучшения."""
        plate = self.plate_at_point(x, y)
        nx, ny = vec_from_local(plate.normal[0], plate.normal[1], self.hull_angle)
        return self.armor_at((nx, ny))

    def frag_nominal_armor(self, normal=None):
        """Номинальная броня грани для осколков: без угла, экраны считаются втрое."""
        return self.armor_at(normal) + self.frag_armor_bonus(normal)

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        return resolve_hit(penetration, self.armor_at(normal), cos_impact)