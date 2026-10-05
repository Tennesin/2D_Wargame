"""tank/entity.py — состояние и логика танка (без отрисовки)."""
import math

from common import normalize_angle, shortest_angle_diff, VehicleCommand, Shot

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
        self.hull_angle = 0.0           # 0 = вверх, по часовой стрелке
        self.turret_rel_angle = 0.0     # угол башни ОТНОСИТЕЛЬНО корпуса
        self.left_track_offset = 0.0
        self.right_track_offset = 0.0
        self.reload_left = 0.0          # сколько секунд осталось до следующего выстрела
        self.since_shot = 999.0         # сколько секунд прошло с последнего выстрела (для отката)

    @property
    def turret_angle(self):
        """Абсолютный угол башни = корпус + относительный угол."""
        return (self.hull_angle + self.turret_rel_angle) % 360.0

    def update(self, command: VehicleCommand, dt):
        delta_hull = self._rotate_hull(command.steer, dt)
        distance = self._drive(command.throttle, command.steer, dt)
        self._animate_tracks(distance, delta_hull)
        self._aim_turret(command.aim_point, dt)
        return self._update_gun(command.fire, dt)      # Shot или None

    # --- части update ---
    def _rotate_hull(self, steer, dt):
        delta = steer * self.spec.HULL_ROTATION_SPEED * dt
        self.hull_angle = normalize_angle(self.hull_angle + delta)
        return delta

    def _drive(self, throttle, steer, dt):
        if throttle == 0:
            return 0.0
        speed = self.spec.FORWARD_SPEED_PX if throttle > 0 else self.spec.BACKWARD_SPEED_PX
        if steer != 0:
            speed *= self.spec.TURN_SPEED_PENALTY
        distance = speed * dt * throttle
        rad = math.radians(self.hull_angle)
        self.x += math.sin(rad) * distance
        self.y -= math.cos(rad) * distance
        return distance

    def _animate_tracks(self, distance, delta_hull):
        scale = getattr(self.spec, "HULL_SCALE", 1.0)
        rot_dist = math.radians(delta_hull) * self.TRACK_RADIUS
        # Поворот вправо (delta_hull > 0): левая гусеница едет вперёд, правая назад.
        # "Вперёд" для узора = отрицательное смещение. distance переводим в пиксели спрайта.
        self.left_track_offset = (self.left_track_offset - distance / scale - rot_dist) % self.TRACK_STEP
        self.right_track_offset = (self.right_track_offset - distance / scale + rot_dist) % self.TRACK_STEP

    def _aim_turret(self, aim_point, dt):
        if aim_point is None:
            return
        dx = aim_point[0] - self.x
        dy = aim_point[1] - self.y
        if math.hypot(dx, dy) < self.AIM_DEAD_ZONE:
            return
        target_abs = math.degrees(math.atan2(dy, dx)) + 90.0
        diff = shortest_angle_diff(target_abs, self.turret_angle)
        max_step = self.spec.TURRET_ROTATION_SPEED * dt
        if abs(diff) <= max_step:
            self.turret_rel_angle += diff
        else:
            self.turret_rel_angle += math.copysign(max_step, diff)
        self.turret_rel_angle %= 360.0

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