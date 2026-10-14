"""ai/steering.py — курс, «щупальца» вперёд, анти-застревание."""
import math

from engine import shortest_angle_diff, clamp

STEER_DEADZONE_DEG = 2.0      # ошибка курса меньше этого: руль в ноль
STEER_FULL_DEG = 25.0         # при ошибке курса от этого руль «до упора»
TURN_IN_PLACE_DEG = 60.0      # ошибка больше этого: газ в ноль, разворот на месте

def steer_to(tank, heading_deg, go, turn_in_place_deg=TURN_IN_PLACE_DEG):
    err = shortest_angle_diff(heading_deg, tank.hull_angle)
    steer = 0.0 if abs(err) < STEER_DEADZONE_DEG else clamp(err / STEER_FULL_DEG, -1.0, 1.0)
    throttle = go if abs(err) <= turn_in_place_deg else 0.0
    return throttle, steer

class StuckGuard:
    """Бот пытается ехать или поворачиваться, а корпус не двигается и не поворачивается:
    на время включается задний ход с поворотом."""
    CHECK_S = 2.0
    MIN_MOVE_PX = 60.0          # 0.6 м
    MIN_TURN_DEG = 10.0
    REVERSE_S = 1.2

    def __init__(self):
        self.turn = 1.0
        self._reverse_left = 0.0
        self._timer = 0.0
        self._ref = None        # (x, y, угол корпуса) в начале окна проверки

    def update(self, dt, tank, pushing, rng):
        """pushing: подан ли ненулевой газ ИЛИ руль. Возвращает True, пока надо ехать назад."""
        if self._reverse_left > 0.0:
            self._reverse_left -= dt
            return True
        if not pushing:
            self._timer, self._ref = 0.0, None
            return False
        if self._ref is None:
            self._ref = (tank.x, tank.y, tank.hull_angle)
        self._timer += dt
        if self._timer >= self.CHECK_S:
            rx, ry, ra = self._ref
            moved = math.hypot(tank.x - rx, tank.y - ry)
            turned = abs(shortest_angle_diff(tank.hull_angle, ra))
            self._timer, self._ref = 0.0, (tank.x, tank.y, tank.hull_angle)
            if moved < self.MIN_MOVE_PX and turned < self.MIN_TURN_DEG:
                self._reverse_left = self.REVERSE_S
                self.turn = rng.choice((-1.0, 1.0))
        return False