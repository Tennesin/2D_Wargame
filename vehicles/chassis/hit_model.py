"""vehicles/chassis/hit_model.py — модель попаданий по технике: луч снаряда, грань и плита брони,
приведённая броня. Миксин для Vehicle: состояния не хранит, читает spec и положение корпуса
из итогового класса (hull_obb, _to_hull_local, hull_angle)."""
from engine import (
    heading_vector, convex_segment_hit, to_local_frame, vec_to_local, vec_from_local, PX_PER_M,
)
from combat import resolve_hit
from vehicles.chassis.params import ARMOR_K

class HitModelMixin:

    def _local_parts(self):
        """Выпуклые участки для попаданий в метрах корпуса (центр корпуса = (0, 0), перед = -v)."""
        return self.spec.layout.hit_parts

    def raycast(self, x0, y0, x1, y1):
        """Пересечение отрезка с корпусом: (self, t, normal) или None.
        Отрезок переводится в систему корпуса, там ищется ближайшая из выпуклых частей раскладки."""
        cx, cy, _, _, ang = self.hull_obb()
        k = self.spec.HULL_SCALE * PX_PER_M
        u0, v0 = to_local_frame(x0, y0, cx, cy, ang, k)
        u1, v1 = to_local_frame(x1, y1, cx, cy, ang, k)
        best = None
        for part in self._local_parts():
            res = convex_segment_hit(part, u0, v0, u1, v1)
            if res is not None and (best is None or res[0] < best[0]):
                best = res
        if best is None:
            return None
        t, n = best
        if n is not None:
            n = vec_from_local(n[0], n[1], ang)      # масштаб однородный, нормаль только поворачиваем
        return self, t, n

    def zone_at(self, normal, hull_angle=None):
        """Какая грань корпуса принимает удар: "front" / "side" / "rear".
        normal — наружная нормаль грани. hull_angle — гипотетический угол корпуса (по умолчанию текущий)."""
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
        """Плита брони, принявшая удар: та, чья наружная нормаль ближе всего к normal (мировая).
        Нормаль None (выстрел начался внутри) = боковая плита."""
        layout = self.spec.layout
        if normal is None:
            return next((p for p in layout.plates if p.zone == "side"), layout.plates[0])
        ang = self.hull_angle if hull_angle is None else hull_angle
        nu, nv = vec_to_local(normal[0], normal[1], ang)
        return layout.plate_by_normal(nu, nv)

    def armor_at(self, normal, hull_angle=None):
        """Броня грани, в которую попали (мм, с коэффициентом ARMOR_K).
        Зона берётся из zone_at (одна на весь проект), коэффициент толщины из плиты.
        Борт прикрыт гусеницей, лоб экранами: эти добавки идут поверх плиты и на k не умножаются."""
        s = self.spec
        zone = self.zone_at(normal, hull_angle)
        base = {"front": s.front, "side": s.side, "rear": s.rear}[zone]
        plate = self.plate_at(normal, hull_angle)
        base *= plate.k
        if zone == "front":
            base += s.screen_mm
        elif zone == "side":
            base += s.track_mm
        return base * ARMOR_K

    def armor_along(self, from_deg, hull_deg=None, lateral=0.0):
        """Броня и косинус угла для луча, пришедшего с азимута from_deg (от этой техники к стрелку)."""
        if hull_deg is None:
            hull_deg = self.hull_angle
        wx, wy = heading_vector(from_deg)
        ex, ey = vec_to_local(wx, wy, hull_deg)       # единичный вектор на стрелка в системе корпуса
        tx, ty = -ey * lateral, ex * lateral          # точка прицеливания
        reach = 50.0                                  # м: заведомо больше корпуса
        best = None
        for part in self._local_parts():
            res = convex_segment_hit(part, tx + ex * reach, ty + ey * reach,
                                     tx - ex * reach, ty - ey * reach)
            if res is not None and (best is None or res[0] < best[0]):
                best = res
        if best is None or best[1] is None:
            return None
        nu, nv = best[1]
        cos_i = abs(ex * nu + ey * nv)
        normal = vec_from_local(nu, nv, hull_deg)
        return self.armor_at(normal, hull_deg), cos_i

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

    def armor_facing(self, x, y):
        """Броня грани, ближайшей к точке (x, y) (мм). Нужна взрывам по площади: у них нет «луча»."""
        return self.armor_at(self.facing_normal(x, y))

    def frag_nominal_armor(self, normal=None):
        """Номинальная броня грани для осколков: без угла, экраны считаются втрое."""
        return self.armor_at(normal) + self.frag_armor_bonus(normal)

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        return resolve_hit(penetration, self.armor_at(normal), cos_impact)

    def frag_armor_bonus(self, normal=None):
        """Экраны для осколков считаются втрое: 1x уже есть в armor_at, добавляем ещё 2x (только на лбу)."""
        if self.spec.screen_mm > 0.0 and self.zone_at(normal) == "front":
            return 2.0 * self.spec.screen_mm * ARMOR_K
        return 0.0