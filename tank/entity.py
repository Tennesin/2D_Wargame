"""tank/entity.py — состояние и логика танка (без отрисовки)."""
import math

from common import normalize_angle, shortest_angle_diff, obb_hits_obb, VehicleCommand, Shot
from .params import KMH_TO_PX

class Tank:
    TRACK_STEP = 20.0      # шаг между траками (px эталонного мира; 20 px = 0,2 м)
    TRACK_RADIUS = 160.0   # расстояние от центра до гусеницы
    AIM_DEAD_ZONE = 100.0  # если курсор ближе к центру танка (1 м), башня не дёргается

    def __init__(self, x=0.0, y=0.0, *, spec, team_color=(200, 40, 40)):
        # spec — объект TankSpec (обязательный, только по имени: Tank(0, 0, spec=...))
        self.spec = spec
        self.team_color = team_color  # цвет команды (RGB), красный по умолчанию
        self.x = float(x)
        self.y = float(y)
        self.hp = float(spec.hp)        # текущее здоровье (максимум задаёт spec.hp)
        self.hull_angle = 0.0           # 0 = вверх, по часовой стрелке
        self.turret_rel_angle = 0.0     # угол башни ОТНОСИТЕЛЬНО корпуса
        self.left_track_offset = 0.0
        self.right_track_offset = 0.0
        self.reload_left = 0.0          # сколько секунд осталось до следующего выстрела
        self.speed_kmh = 0.0            # текущая скорость вдоль корпуса, км/ч (минус = назад)
        self.since_shot = 999.0         # сколько секунд прошло с последнего выстрела (для отката)

    @property
    def turret_angle(self):
        """Абсолютный угол башни = корпус + относительный угол."""
        return (self.hull_angle + self.turret_rel_angle) % 360.0

    @property
    def max_hp(self):
        return self.spec.hp

    def set_spec(self, spec):
        """Новая спецификация (ползунки конструктора). Доля здоровья сохраняется."""
        frac = self.hp / self.spec.hp if self.spec.hp > 0 else 1.0
        self.spec = spec
        self.hp = spec.hp * max(0.0, min(1.0, frac))

    # --- столкновения ---
    def _hull_obb(self, x, y, angle):
        """Прямоугольник корпуса: центр лежит позади оси башни."""
        s = self.spec
        rad = math.radians(angle)
        fx, fy = math.sin(rad), -math.cos(rad)
        return (x - fx * s.COLLISION_SHIFT_PX, y - fy * s.COLLISION_SHIFT_PX,
                s.COLLISION_HALF_W_PX, s.COLLISION_HALF_L_PX, angle)

    def _barrel_obb(self, x, y, angle):
        """Прямоугольник ствола. angle — АБСОЛЮТНЫЙ угол башни. Центр лежит на оси башни."""
        s = self.spec
        rad = math.radians(angle)
        fx, fy = math.sin(rad), -math.cos(rad)
        mid = (s.BARREL_COLL_START_PX + s.BARREL_COLL_END_PX) / 2.0
        half = (s.BARREL_COLL_END_PX - s.BARREL_COLL_START_PX) / 2.0
        return (x + fx * mid, y + fy * mid, s.BARREL_COLL_HALF_W_PX, half, angle)

    def _barrel_hits(self, x, y, turret_abs, obstacles):
        obb = self._barrel_obb(x, y, turret_abs)
        return any(obb_hits_obb(*obb, *other) for other in obstacles)

    def _overlaps(self, x, y, angle, obstacles):
        """angle — угол КОРПУСА. Задевает ли препятствие корпус или ствол
        (башня при этом сохраняет свой относительный угол)."""
        hull = self._hull_obb(x, y, angle)
        if any(obb_hits_obb(*hull, *other) for other in obstacles):
            return True
        return self._barrel_hits(x, y, angle + self.turret_rel_angle, obstacles)

    def hits_obb(self, other):
        """Задевает ли танк (корпус или ствол) повёрнутый прямоугольник (x, y, half_w, half_l, angle)."""
        hull = self._hull_obb(self.x, self.y, self.hull_angle)
        barrel = self._barrel_obb(self.x, self.y, self.turret_angle)
        return obb_hits_obb(*hull, *other) or obb_hits_obb(*barrel, *other)

    def update(self, command: VehicleCommand, dt, obstacles=()):
        """obstacles — список прямоугольников (left, top, right, bottom) в мировых px."""
        delta_hull = self._rotate_hull(command.steer, dt, obstacles)
        distance = self._drive(command.throttle, command.steer, dt, obstacles)
        self._animate_tracks(distance, delta_hull)
        self._aim_turret(command.aim_point, dt, obstacles)
        return self._update_gun(command.fire, dt)      # Shot или None

    # --- части update ---
    def _rotate_hull(self, steer, dt, obstacles=()):
        delta = steer * self.spec.HULL_ROTATION_SPEED * dt
        old = self.hull_angle
        new = normalize_angle(old + delta)
        # если поворот упирается в препятствие, поворачиваем только до касания
        if (obstacles and delta != 0
                and not self._overlaps(self.x, self.y, old, obstacles)
                and self._overlaps(self.x, self.y, new, obstacles)):
            lo, hi = 0.0, 1.0
            for _ in range(8):
                mid = (lo + hi) / 2.0
                if self._overlaps(self.x, self.y, normalize_angle(old + delta * mid), obstacles):
                    hi = mid
                else:
                    lo = mid
            delta *= lo
            new = normalize_angle(old + delta)
        self.hull_angle = new
        return delta

    def _drive(self, throttle, steer, dt, obstacles=()):
        self._update_speed(throttle, steer, dt)
        distance = self.speed_kmh * KMH_TO_PX * dt          # со знаком: минус = назад
        if distance == 0.0:
            return 0.0

        rad = math.radians(self.hull_angle)
        dx = math.sin(rad) * distance
        dy = -math.cos(rad) * distance

        new_x, new_y = self.x + dx, self.y + dy
        # если путь упирается в препятствие, подъезжаем вплотную (деление отрезка пополам)
        if (obstacles
                and not self._overlaps(self.x, self.y, self.hull_angle, obstacles)
                and self._overlaps(new_x, new_y, self.hull_angle, obstacles)):
            lo, hi = 0.0, 1.0
            for _ in range(8):
                mid = (lo + hi) / 2.0
                if self._overlaps(self.x + dx * mid, self.y + dy * mid, self.hull_angle, obstacles):
                    hi = mid
                else:
                    lo = mid
            new_x, new_y = self.x + dx * lo, self.y + dy * lo

        moved = math.hypot(new_x - self.x, new_y - self.y)
        if moved < abs(distance) * 0.999:                    # путь урезан препятствием: танк встал
            self.speed_kmh = 0.0
        self.x, self.y = new_x, new_y
        return math.copysign(moved, distance)                # гусеницы крутятся только на реально пройденный путь

    def _update_speed(self, throttle, steer, dt):
        """Приближает текущую скорость к целевой с учётом разгона, наката и торможения."""
        s = self.spec
        cap_fwd, cap_back = s.v_max, s.v_back
        if steer != 0:                                       # на повороте потолок скорости ниже
            cap_fwd *= s.TURN_SPEED_PENALTY
            cap_back *= s.TURN_SPEED_PENALTY

        if throttle > 0:
            target = throttle * cap_fwd
        elif throttle < 0:
            target = throttle * cap_back                     # отрицательное число
        else:
            target = 0.0

        v = self.speed_kmh
        if v > target:
            if v > 0:                                        # едем вперёд, а надо медленнее или назад
                rate = s.decel_brake if target < 0 else s.decel_coast
                v = max(v - rate * dt, max(target, 0.0))     # назад через ноль переходим на следующем кадре
            else:                                            # едем назад и хотим ещё быстрее назад
                v = max(v - s.accel_back * dt, target)
        elif v < target:
            if v < 0:                                        # едем назад, а надо медленнее или вперёд
                rate = s.decel_brake if target > 0 else s.decel_coast
                v = min(v + rate * dt, min(target, 0.0))
            else:                                            # разгон вперёд
                v = min(v + s.accel_at(v) * dt, target)
        self.speed_kmh = v

    def _animate_tracks(self, distance, delta_hull):
        scale = getattr(self.spec, "HULL_SCALE", 1.0)
        rot_dist = math.radians(delta_hull) * self.TRACK_RADIUS
        # Поворот вправо (delta_hull > 0): левая гусеница едет вперёд, правая назад.
        # "Вперёд" для узора = отрицательное смещение. distance переводим в пиксели спрайта.
        self.left_track_offset = (self.left_track_offset - distance / scale - rot_dist) % self.TRACK_STEP
        self.right_track_offset = (self.right_track_offset - distance / scale + rot_dist) % self.TRACK_STEP

    def _aim_turret(self, aim_point, dt, obstacles=()):
        if aim_point is None:
            return
        dx = aim_point[0] - self.x
        dy = aim_point[1] - self.y
        if math.hypot(dx, dy) < self.AIM_DEAD_ZONE:
            return
        target_abs = math.degrees(math.atan2(dy, dx)) + 90.0
        diff = shortest_angle_diff(target_abs, self.turret_angle)
        max_step = self.spec.TURRET_ROTATION_SPEED * dt
        delta = diff if abs(diff) <= max_step else math.copysign(max_step, diff)

        old = self.turret_rel_angle
        # если поворот упирается в препятствие, поворачиваем только до касания
        if (obstacles and delta != 0
                and not self._barrel_hits(self.x, self.y, self.hull_angle + old, obstacles)
                and self._barrel_hits(self.x, self.y, self.hull_angle + old + delta, obstacles)):
            lo, hi = 0.0, 1.0
            for _ in range(8):
                mid = (lo + hi) / 2.0
                if self._barrel_hits(self.x, self.y, self.hull_angle + old + delta * mid, obstacles):
                    hi = mid
                else:
                    lo = mid
            delta *= lo
        self.turret_rel_angle = (old + delta) % 360.0

    def _update_gun(self, fire, dt):
        """Перезарядка и выстрел. Возвращает Shot, если выстрел произошёл в этом кадре."""
        self.reload_left = max(0.0, self.reload_left - dt)
        self.since_shot += dt
        if not fire or self.reload_left > 0.0:
            return None

        self.reload_left = self.spec.reload
        self.since_shot = 0.0
        rad = math.radians(self.turret_angle)
        dist = self.spec.MUZZLE_DIST_PX
        return Shot(self.x + math.sin(rad) * dist,
                    self.y - math.cos(rad) * dist,
                    self.turret_angle)

    def muzzle_point(self):
        """Текущая позиция дульного среза (мировые px)."""
        rad = math.radians(self.turret_angle)
        dist = self.spec.MUZZLE_DIST_PX
        return self.x + math.sin(rad) * dist, self.y - math.cos(rad) * dist

    @property
    def recoil_m(self):
        """Насколько ствол сейчас утоплен в башню (метры эталонного спрайта)."""
        T = self.spec.RECOIL_TIME
        if self.since_shot >= T:
            return 0.0
        k = self.since_shot / T
        depth = self.spec.RECOIL_DEPTH_M
        if k < 0.2:                                   # быстрый откат назад (первые 20% времени)
            return depth * (k / 0.2)
        return depth * (1.0 - (k - 0.2) / 0.8) ** 2   # плавный накат обратно