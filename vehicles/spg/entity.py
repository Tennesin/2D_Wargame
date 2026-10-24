"""vehicles/spg/entity.py — САУ: орудие без башни, стрельба навесом по точке на земле.
Команда: aim_point = ЦЕЛЕВАЯ ТОЧКА НА ЗЕМЛЕ, fire = «стрелять, если можно»."""
import math

from engine import (WORLD, Shot, AmmoKind, PX_PER_M, bearing_deg, clamp,
                    shortest_angle_diff)
from vehicles.gun.vehicle import GunVehicle
from .params import SPG_AIM_TOLERANCE_DEG

class ArtilleryVehicle(GunVehicle):
    renderer_key = "spg"
    PLAYER_TITLE = "Ваша САУ"
    AIM_TOLERANCE_DEG = SPG_AIM_TOLERANCE_DEG

    def __init__(self, x=0.0, y=0.0, *, label="САУ", **kwargs):
        super().__init__(x, y, label=label, **kwargs)
        self.ammo = AmmoKind.HE                  # единственный снаряд

    # ---------- сводка ----------
    def _extra_rows(self):
        s = self.spec
        return [("Дальность", f"{s.RANGE_MAX_PX / PX_PER_M:.0f} м"),
                ("Мёртвая зона", f"{s.RANGE_MIN_PX / PX_PER_M:.0f} м"),
                ("Радиус взрыва", f"{s.shell_stats.outer_radius_px / PX_PER_M:.1f} м"),
                ("УГН", f"±{s.TURRET_ARC_DEG / 2.0:.0f} °")]

    # ---------- оружие ----------
    def round_stats(self):
        """Числа выстрела берутся готовыми из спецификации (снаряд всегда один)."""
        return self.spec.shell_stats

    def _update_weapons(self, command, dt):
        self._aim_turret(command.aim_point, dt)
        self._update_gun(False, dt)              # fire=False: только таймеры перезарядки и отката
        return self._try_fire(command)

    def _try_fire(self, command):
        """Выстрел разрешён, если: цель между мёртвой зоной и максимальной дальностью, орудие довёрнуто,
        перезарядка прошла и машина не оглушена. Возвращает Shot (с полем target) или None."""
        target = command.aim_point
        if not command.fire or target is None or self.stunned or self.reload_left > 0.0:
            return None

        s = self.spec
        tx = clamp(target[0], -WORLD.half_w_px, WORLD.half_w_px)     # снаряд не падает за край мира
        ty = clamp(target[1], -WORLD.half_h_px, WORLD.half_h_px)
        dist = math.hypot(tx - self.x, ty - self.y)
        if dist < s.RANGE_MIN_PX or dist > s.RANGE_MAX_PX:
            return None

        err = shortest_angle_diff(bearing_deg(self.x, self.y, tx, ty), self.turret_angle)
        if abs(err) > self.AIM_TOLERANCE_DEG:
            return None

        stats = self.round_stats()
        self.reload_total = self.reload_left = stats.reload
        self.since_shot = 0.0
        mx, my = self.muzzle_point()
        return Shot(mx, my, self.turret_angle, stats, target=(tx, ty))