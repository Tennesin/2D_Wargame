"""vehicles/chassis/shock.py — подброс техники от сильного тарана: таймер, высота для рисунка и запрет стрельбы.
Миксин для Vehicle: поля lift_left / lift_total / lift_amp создаёт Vehicle.__init__, таймер убывает в Vehicle.update."""
import math

from engine import clamp, lerp
from vehicles.chassis.params import LIFT_MIN_DV_MS, LIFT_FULL_DV_MS, LIFT_TIME_S, LIFT_MAX_S

LIFT_RISE = 0.12         # доля времени на быстрый подъём
LIFT_BOUNCES = 1.5       # сколько "качков" при оседании

class ShockMixin:

    @property
    def lifted(self):
        return self.lift_left > 0.0

    @property
    def fire_locked(self):
        """Стрелять нельзя, пока машина подброшена. Перезарядка при этом идёт."""
        return self.lift_left > 0.0

    def apply_lift(self, dv_ms):
        """dv_ms: на сколько м/с удар изменил скорость ЭТОЙ машины. Возвращает True, если её подбросило.
        Уже подброшенную машину повторно не поднимаем и время не продлеваем (ни с какой стороны)."""
        if self.lift_left > 0.0 or dv_ms < LIFT_MIN_DV_MS:
            return False
        amp = clamp((dv_ms - LIFT_MIN_DV_MS) / (LIFT_FULL_DV_MS - LIFT_MIN_DV_MS), 0.0, 1.0)
        mass_k = self.mass_k
        duration = lerp(LIFT_TIME_S[0], LIFT_TIME_S[1], amp) * (0.85 + 0.30 * mass_k)   # тяжёлая качается дольше...
        self.lift_total = self.lift_left = min(LIFT_MAX_S, duration)
        self.lift_amp = (0.3 + 0.7 * amp) * (1.0 - 0.4 * mass_k)                         # ...но поднимается ниже
        return True

    def lift_height(self):
        """Высота подъёма 0..1 для рисунка: быстрый подъём, затем затухающее оседание с лёгким подпрыгиванием."""
        if self.lift_left <= 0.0 or self.lift_total <= 0.0:
            return 0.0
        u = 1.0 - self.lift_left / self.lift_total
        if u < LIFT_RISE:
            t = u / LIFT_RISE
            return self.lift_amp * t * t * (3.0 - 2.0 * t)
        k = (u - LIFT_RISE) / (1.0 - LIFT_RISE)
        return self.lift_amp * (1.0 - k) ** 2 * (0.65 + 0.35 * math.cos(2.0 * math.pi * LIFT_BOUNCES * k))