"""vehicles/gun_vehicle.py — техника с орудием: башня (ОБТ) или лафет с ограниченным сектором (ПТ-САУ).
Имена turret_angle / turret_rel_angle сохранены: их читают ai, combat и overlays.
У техники без башни это угол орудия."""
import math

from engine import shortest_angle_diff, Shot, heading_vector, bearing_deg, clamp, AmmoKind
from .base import Vehicle
from .ammo import ammo_stats

class GunVehicle(Vehicle):
    AIM_DEAD_ZONE = 100.0   # если курсор ближе к оси орудия (1 м), орудие не дёргается
    ARC_MARGIN_DEG = 3.0    # корпус доворачивают так, чтобы цель была не на самом краю сектора

    def __init__(self, x=0.0, y=0.0, **kwargs):
        super().__init__(x, y, **kwargs)
        self.turret_rel_angle = 0.0     # угол орудия ОТНОСИТЕЛЬНО корпуса
        self.turret_rate = 0.0          # угловая скорость относительно корпуса, °/с
        self.reload_left = 0.0          # сколько секунд осталось до следующего выстрела
        self.since_shot = 999.0         # сколько секунд прошло с последнего выстрела (для отката)
        self.ammo = AmmoKind.AP         # выбранный тип снаряда (по умолчанию бронебойный)
        self.reload_total = 0.0         # длительность текущей перезарядки, с (нужна HUD)
        self._round_cache = None        # (spec, ammo, stats): пересчитывается при смене орудия или снаряда

    @property
    def turret_angle(self):
        """Абсолютный угол башни (орудия) = корпус + относительный угол."""
        return (self.hull_angle + self.turret_rel_angle) % 360.0

    def place_at(self, spot):
        super().place_at(spot)
        self.turret_rate = 0.0

    def _extra_rows(self):
        """Строки сводки между калибром и бронёй (подклассы добавляют своё)."""
        return []

    def describe(self):
        title, rows = super().describe()
        head = [("Калибр", f"{self.spec.cal:.0f} мм"), *self._extra_rows()]
        return title, head + rows

    # ---------- оружие ----------
    def _update_weapons(self, command, dt):
        self._aim_turret(command.aim_point, dt)
        return self._update_gun(command.fire, dt)      # Shot или None

    def _aim_turret(self, aim_point, dt):
        s = self.spec
        half = s.TURRET_ARC_DEG / 2.0
        limited = half < 180.0                             # круговая башня или ограниченный сектор
        rel = shortest_angle_diff(self.turret_rel_angle, 0.0)   # угол к корпусу: -180..180

        target_rate = 0.0
        diff = 0.0
        if aim_point is not None:
            dx = aim_point[0] - self.x
            dy = aim_point[1] - self.y
            if math.hypot(dx, dy) >= self.AIM_DEAD_ZONE:
                want = shortest_angle_diff(bearing_deg(self.x, self.y, *aim_point), self.hull_angle)
                if limited:
                    diff = clamp(want, -half, half) - rel      # без «короткого пути» через запретный сектор
                else:
                    diff = shortest_angle_diff(want, rel)
                allowed = math.sqrt(2.0 * s.turret_alpha * abs(diff))
                target_rate = math.copysign(min(s.turret_turn, allowed), diff)

        self.turret_rate = self._approach(self.turret_rate, target_rate,
                                          s.turret_alpha, s.turret_alpha, dt)
        delta = self.turret_rate * dt
        if diff != 0.0 and delta * diff > 0.0 and abs(delta) > abs(diff):
            delta = diff
            self.turret_rate = 0.0

        new_rel = rel + delta
        if limited:
            clamped = clamp(new_rel, -half, half)
            if clamped != new_rel:
                self.turret_rate = 0.0
            new_rel = clamped
        self.turret_rel_angle = new_rel % 360.0

    def _update_gun(self, fire, dt):
        """Перезарядка и выстрел. Возвращает Shot, если выстрел произошёл в этом кадре."""
        self.reload_left = max(0.0, self.reload_left - dt)
        self.since_shot += dt
        if not fire or self.reload_left > 0.0:
            return None

        stats = self.round_stats()
        self.reload_total = self.reload_left = stats.reload
        self.since_shot = 0.0
        mx, my = self.muzzle_point()
        return Shot(mx, my, self.turret_angle, stats)

    def muzzle_point(self):
        """Текущая позиция дульного среза (мировые px)."""
        fx, fy = heading_vector(self.turret_angle)
        dist = self.spec.MUZZLE_DIST_PX
        return self.x + fx * dist, self.y + fy * dist

    def round_stats(self):
        """Характеристики выстрела текущим снарядом. Зовётся каждый кадр (HUD, прицел), поэтому кэшируется.
        Сравнение по идентичности: set_spec() подменяет объект spec, и кэш обновится сам."""
        c = self._round_cache
        if c is None or c[0] is not self.spec or c[1] is not self.ammo:
            c = self._round_cache = (self.spec, self.ammo, ammo_stats(self.spec, self.ammo))
        return c[2]

    def select_ammo(self, kind):
        """Сменить тип снаряда. Если идёт перезарядка, прогресс сохраняется пропорционально:
        иначе можно выстрелить ББ, переключиться на КС и получить его раньше положенного."""
        if kind is self.ammo:
            return
        old_total = self.reload_total
        self.ammo = kind
        if self.reload_left > 0.0 and old_total > 0.0:
            new_total = self.round_stats().reload
            self.reload_left = self.reload_left / old_total * new_total
            self.reload_total = new_total

    def hull_offset_to(self, x, y):
        """Сколько градусов довернуть КОРПУС (+ по часовой), чтобы точка (x, y) попала в сектор орудия.
        0, если башня круговая или точка уже в секторе (с запасом ARC_MARGIN_DEG)."""
        half = self.spec.TURRET_ARC_DEG / 2.0
        if half >= 180.0:
            return 0.0
        want = shortest_angle_diff(bearing_deg(self.x, self.y, x, y), self.hull_angle)
        margin = max(0.0, half - self.ARC_MARGIN_DEG)
        if abs(want) <= margin:
            return 0.0
        return want - math.copysign(margin, want)

    @property
    def recoil_m(self):
        """Насколько ствол сейчас утоплен (метры эталонного спрайта)."""
        T = self.spec.RECOIL_TIME
        if self.since_shot >= T:
            return 0.0
        k = self.since_shot / T
        depth = self.spec.RECOIL_DEPTH_M
        if k < 0.2:
            return depth * (k / 0.2)
        return depth * (1.0 - (k - 0.2) / 0.8) ** 2