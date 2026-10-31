"""vehicles/chassis/tracks.py — гусеницы и внешние модули корпуса: какую гусеницу или лобовой экран
задела точка попадания, сбитие, ремонт, влияние на управление и анимация траков.
Миксин для Vehicle: состояние (self.tracks) создаёт Vehicle.__init__.
Экран живёт здесь же, потому что module_at сначала спрашивает про гусеницу, а потом про экран."""
import math

from engine import PX_PER_M, clamp
from vehicles.chassis.hull_noses import screen_hit
from vehicles.chassis.params import (
    TRACK_LINK_M, ONE_TRACK_SPEED_K, SCREEN_FACE_EPS_PX, TRACK_EDGE_ZONE_M, TRACK_HIT_TOL_M,
)
from vehicles.chassis.running_gear import LEFT, RIGHT, TRACK_SIDES

class TracksMixin:
    TRACK_STEP = TRACK_LINK_M * PX_PER_M        # шаг между траками, px эталонного мира

    @property
    def TRACK_RADIUS(self):
        """Расстояние от центра до гусеницы, px эталонного спрайта: колея берётся из раскладки."""
        return self.spec.layout.track_x * PX_PER_M

    # ---------- попадания ----------
    def track_at(self, x, y):
        """Какую гусеницу задевает точка попадания (x, y): "left" / "right" или None.
        Сбить можно только передний или задний конец гусеницы (TRACK_EDGE_ZONE_M)."""
        layout = self.spec.layout
        u, v = self._to_hull_local(x, y)
        tol = TRACK_HIT_TOL_M
        for side, (x0, y0, x1, y1) in zip((LEFT, RIGHT), layout.track_rects):
            if not (x0 - tol <= u <= x1 + tol and y0 - tol <= v <= y1 + tol):
                continue
            if v <= y0 + TRACK_EDGE_ZONE_M or v >= y1 - TRACK_EDGE_ZONE_M:
                return side
        return None

    def track_under(self, x, y):
        """Какая гусеница лежит под точкой (x, y) целиком, по всей длине: "left" / "right" / None.
        Нужен взрывам САУ: в отличие от track_at, зона краёв и допуск не учитываются."""
        u, v = self._to_hull_local(x, y)
        for side, (x0, y0, x1, y1) in zip((LEFT, RIGHT), self.spec.layout.track_rects):
            if x0 <= u <= x1 and y0 <= v <= y1:
                return side
        return None

    def screen_at(self, x, y):
        """Попала ли точка (x, y) прямо в лист лобового экрана (а не просто в лоб).
        Если экранов нет (screen_mm = 0), всегда False."""
        s = self.spec
        if s.screen_mm <= 0.0:
            return False
        u, v = self._to_hull_local(x, y)
        k = s.HULL_SCALE * PX_PER_M
        return screen_hit(s.layout, u, v, SCREEN_FACE_EPS_PX / k)

    def module_at(self, x, y):
        """Внешний модуль, который первым задевает точка попадания (x, y).
        Возвращает "left" / "right" (целая гусеница), "screen" (лобовой экран) или None.
        Гусеница проверяется первой: на углу лба она закрывает экран."""
        side = self.track_at(x, y)
        if side is not None and not self.tracks.is_broken(side):
            return side
        if self.screen_at(x, y):
            return "screen"
        return None

    @property
    def track_thickness_mm(self):
        """Толщина гусеницы (производная от габарита, см. ChassisSpec._calc_tracks)."""
        return self.spec.track_mm

    def nearest_track(self, x, y):
        """Ближайшая к точке (x, y) гусеница: (сторона, расстояние в мировых px до её прямоугольника).
        Состояние не учитывается. При равном расстоянии (взрыв ровно по оси) берётся левая."""
        u, v = self._to_hull_local(x, y)
        best_side, best_d = None, None
        for side, (x0, y0, x1, y1) in zip((LEFT, RIGHT), self.spec.layout.track_rects):
            du = max(x0 - u, 0.0, u - x1)
            dv = max(y0 - v, 0.0, v - y1)
            d = math.hypot(du, dv)
            if best_d is None or d < best_d:
                best_side, best_d = side, d
        return best_side, best_d * self.spec.HULL_SCALE * PX_PER_M

    def damage_track(self, side, damage_hp):
        """Урон гусенице стороны side в HP гусеницы. True, если она только что сбита."""
        return self.tracks.damage(side, damage_hp / self.spec.track_max_hp)

    # ---------- ремонт и состояние ----------
    def start_repair(self, side=None):
        """Начать ремонт сбитой гусеницы. Одновременно идёт только один ремонт.
        Возвращает сторону, которую начали чинить, или None."""
        return self.tracks.start_repair(self.spec.gear.repair_s, side)

    def _track_status(self):
        names = {LEFT: "левая", RIGHT: "правая"}
        if not self.tracks.broken:
            return "целы"
        return "сбита: " + ", ".join(names[s] for s in TRACK_SIDES if self.tracks.is_broken(s))

    def _track_inputs(self, throttle, steer):
        """Газ и руль с учётом сбитых гусениц.
        Обе целы: без изменений. Обе сбиты: стоим. Цела одна: работает только она,
        машина ползёт по дуге вокруг стоящей гусеницы (поворот в сторону сбитой)."""
        left_bad = self.tracks.is_broken(LEFT)
        right_bad = self.tracks.is_broken(RIGHT)
        if not left_bad and not right_bad:
            return throttle, steer
        if left_bad and right_bad:
            return 0.0, 0.0
        if left_bad:                                   # цела правая: центр поворота у левой, крутимся влево
            u = clamp(throttle - steer, -1.0, 1.0)
            return u * ONE_TRACK_SPEED_K, -u
        u = clamp(throttle + steer, -1.0, 1.0)         # цела левая: крутимся вправо
        return u * ONE_TRACK_SPEED_K, u

    # ---------- анимация ----------
    def _animate_tracks(self, distance, delta_hull):
        scale = self.spec.HULL_SCALE
        rot_dist = math.radians(delta_hull) * self.TRACK_RADIUS
        # Поворот вправо (delta_hull > 0): левая гусеница едет вперёд, правая назад.
        # "Вперёд" для узора = отрицательное смещение. distance переводим в пиксели спрайта.
        if not self.tracks.is_broken(LEFT):
            self.left_track_offset = (self.left_track_offset - distance / scale - rot_dist) % self.TRACK_STEP
        if not self.tracks.is_broken(RIGHT):
            self.right_track_offset = (self.right_track_offset - distance / scale + rot_dist) % self.TRACK_STEP