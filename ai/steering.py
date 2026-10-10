"""ai/steering.py — курс, «щупальца» вперёд, анти-застревание."""
import math

from engine import heading_vector, shortest_angle_diff, clamp

def bearing_deg(x0, y0, x1, y1):
    """Угол от точки 0 к точке 1 в системе танка (0 = вверх, по часовой)."""
    return math.degrees(math.atan2(y1 - y0, x1 - x0)) + 90.0

def steer_to(tank, heading_deg, go, turn_in_place_deg=60.0):
    """Курс корпуса -> (throttle, steer). go: +1 вперёд, -1 назад, 0 стоять.
    Если до нужного курса далеко, газ в ноль: танк разворачивается на месте."""
    err = shortest_angle_diff(heading_deg, tank.hull_angle)
    steer = 0.0 if abs(err) < 2.0 else clamp(err / 25.0, -1.0, 1.0)
    throttle = go if abs(err) <= turn_in_place_deg else 0.0
    return throttle, steer

def free_ahead(tank, terrain, walls, angle_deg, dist_px):
    """Свободен ли корпус, если проехать dist_px по курсу angle_deg."""
    fx, fy = heading_vector(angle_deg)
    hull = tank.footprint_at(tank.x + fx * dist_px, tank.y + fy * dist_px, angle_deg)[0]
    return not (terrain.blocks_obb(hull) or walls.blocks_obb(hull))

_OFFSETS = (0, 25, -25, 50, -50, 80, -80)

def pick_heading(tank, terrain, walls, desired_deg, look_px, side):
    """Ближайший к desired_deg свободный курс. side (+1/-1) выбирает, в какую сторону обходить первой.
    Если всё занято, возвращает None."""
    for off in _OFFSETS:
        if free_ahead(tank, terrain, walls, desired_deg + off * side, look_px):
            return desired_deg + off * side
    return None

class StuckGuard:
    """Если бот давит на газ, а почти не двигается, на время включается задний ход с поворотом."""
    CHECK_S = 2.0
    MIN_MOVE_PX = 60.0          # 0.6 м
    REVERSE_S = 1.2

    def __init__(self):
        self.turn = 1.0
        self._reverse_left = 0.0
        self._timer = 0.0
        self._ref = None

    def update(self, dt, tank, pushing, rng):
        """pushing: подан ли реально ненулевой газ. Возвращает True, пока надо ехать назад."""
        if self._reverse_left > 0.0:
            self._reverse_left -= dt
            return True
        if not pushing:
            self._timer, self._ref = 0.0, None
            return False
        if self._ref is None:
            self._ref = (tank.x, tank.y)
        self._timer += dt
        if self._timer >= self.CHECK_S:
            moved = math.hypot(tank.x - self._ref[0], tank.y - self._ref[1])
            self._timer, self._ref = 0.0, (tank.x, tank.y)
            if moved < self.MIN_MOVE_PX:
                self._reverse_left = self.REVERSE_S
                self.turn = rng.choice((-1.0, 1.0))
        return False