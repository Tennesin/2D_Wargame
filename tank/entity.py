"""tank/entity.py — состояние и логика танка (без отрисовки)."""
import math

from common import (normalize_angle, shortest_angle_diff, obb_hits_obb, obb_segment_hit,
                    VehicleCommand, Shot, PX_PER_M, heading_vector, find_free_fraction)
from armor import resolve_hit, Damageable
from .params import (KMH_TO_PX, HULL_BRAKE_K, HULL_TURN_SPEED_LOSS, TANK_ARMOR_K,
                     TERRAIN_MIN_K, TERRAIN_BRAKE, TERRAIN_ROLL_DECEL, TURN_SPEED_PENALTY,
                     TRACK_LINK_M, TRACK_OFFSET_M)

class Tank(Damageable):
    TRACK_STEP = TRACK_LINK_M * PX_PER_M     # шаг между траками, px эталонного мира
    TRACK_RADIUS = TRACK_OFFSET_M * PX_PER_M # расстояние от центра до гусеницы, px
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
        self.hull_rate = 0.0            # текущая угловая скорость корпуса, °/с (+ = по часовой)
        self.turret_rate = 0.0          # текущая угловая скорость башни относительно корпуса, °/с
        self.left_track_offset = 0.0
        self.right_track_offset = 0.0
        self.reload_left = 0.0          # сколько секунд осталось до следующего выстрела
        self.speed_kmh = 0.0            # текущая скорость вдоль корпуса, км/ч (минус = назад)
        self.since_shot = 999.0         # сколько секунд прошло с последнего выстрела (для отката)
        self.terrain_k = 1.0            # множитель скорости от местности под корпусом (1.0 = обычная)
        self._terrain = None            # карта препятствий; её передаёт Game в update()

    @property
    def turret_angle(self):
        """Абсолютный угол башни = корпус + относительный угол."""
        return (self.hull_angle + self.turret_rel_angle) % 360.0

    @property
    def max_hp(self):
        return self.spec.hp

    @property
    def mass_t(self):
        """Масса танка, т (для тарана: такой же интерфейс, как у Wall.mass_t и Patch.mass_t)."""
        return self.spec.mass

    def set_spec(self, spec):
        """Новая спецификация (ползунки конструктора). Доля здоровья сохраняется."""
        frac = self.hp / self.spec.hp if self.spec.hp > 0 else 1.0
        self.spec = spec
        self.hp = spec.hp * max(0.0, min(1.0, frac))

    # --- столкновения ---
    def _hull_obb(self, x, y, angle):
        """Прямоугольник корпуса: центр лежит позади оси башни."""
        s = self.spec
        fx, fy = heading_vector(angle)
        return (x - fx * s.COLLISION_SHIFT_PX, y - fy * s.COLLISION_SHIFT_PX,
                s.COLLISION_HALF_W_PX, s.COLLISION_HALF_L_PX, angle)

    def _barrel_obb(self, x, y, angle):
        """Прямоугольник ствола. angle — АБСОЛЮТНЫЙ угол башни. Центр лежит на оси башни."""
        s = self.spec
        fx, fy = heading_vector(angle)
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
        if self._terrain is not None and self._terrain.blocks_obb(hull):
            return True
        return self._barrel_hits(x, y, angle + self.turret_rel_angle, obstacles)

    def _has_solids(self, obstacles):
        """Есть ли вообще что проверять на столкновение (стены или карта местности)."""
        return bool(obstacles) or self._terrain is not None

    def hits_obb(self, other):
        """Задевает ли танк (корпус или ствол) повёрнутый прямоугольник (x, y, half_w, half_l, angle)."""
        hull = self._hull_obb(self.x, self.y, self.hull_angle)
        barrel = self._barrel_obb(self.x, self.y, self.turret_angle)
        return obb_hits_obb(*hull, *other) or obb_hits_obb(*barrel, *other)

    # --- попадания снарядов (универсальный интерфейс цели) ---
    @property
    def alive(self):
        return self.hp > 0.0

    def raycast(self, x0, y0, x1, y1):
        """Пересечение отрезка с корпусом: (self, t, normal) или None."""
        hull = self._hull_obb(self.x, self.y, self.hull_angle)
        res = obb_segment_hit(hull, x0, y0, x1, y1)
        return None if res is None else (self, res[0], res[1])

    def armor_at(self, normal):
        """Броня грани, в которую попали (мм, с коэффициентом TANK_ARMOR_K).
        normal — наружная нормаль грани: совпадает с направлением «вперёд» у лба, противоположна у кормы."""
        s = self.spec
        if normal is None:                      # выстрел начался внутри корпуса
            return s.side * TANK_ARMOR_K
        rad = math.radians(self.hull_angle)
        along = normal[0] * math.sin(rad) - normal[1] * math.cos(rad)   # >0 лоб, <0 корма
        if along > 0.5:
            base = s.front
        elif along < -0.5:
            base = s.rear
        else:
            base = s.side
        return base * TANK_ARMOR_K

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        return resolve_hit(penetration, self.armor_at(normal), cos_impact)

    def update(self, command: VehicleCommand, dt, obstacles=(), terrain=None):
        """obstacles — повёрнутые прямоугольники стен (x, y, half_w, half_l, angle).
        terrain — карта естественных препятствий (TerrainMap) или None."""
        self._terrain = terrain
        self._sample_terrain()
        delta_hull = self._rotate_hull(command.steer, dt, obstacles)
        distance = self._drive(command.throttle, command.steer, dt, obstacles)
        self._animate_tracks(distance, delta_hull)
        self._aim_turret(command.aim_point, dt, obstacles)
        return self._update_gun(command.fire, dt)      # Shot или None

    def _sample_terrain(self):
        """Множитель скорости: среднее по трём точкам под корпусом (зад, центр, перед),
        поэтому при въезде в воду танк тормозится постепенно."""
        terrain = self._terrain
        if terrain is None:
            self.terrain_k = 1.0
            return
        hx, hy, _, half_l, angle = self._hull_obb(self.x, self.y, self.hull_angle)
        fx, fy = heading_vector(angle)
        reach = half_l * 0.8
        total = 0.0
        for d in (-reach, 0.0, reach):
            total += terrain.speed_factor(hx + fx * d, hy + fy * d)
        self.terrain_k = max(TERRAIN_MIN_K, total / 3.0)

    @staticmethod
    def _approach(current, target, accel, brake, dt):
        """Приближает скорость current к target. Нарастание модуля идёт с accel, спад или смена знака — с brake."""
        if current == target:
            return current
        speeding_up = abs(target) > abs(current) and current * target >= 0.0
        step = (accel if speeding_up else brake) * dt
        if abs(target - current) <= step:
            return target
        return current + math.copysign(step, target - current)

    # --- части update ---
    def _rotate_hull(self, steer, dt, obstacles=()):
        s = self.spec
        # на ходу развернуться тяжелее, чем с места
        speed_k = 1.0 - HULL_TURN_SPEED_LOSS * min(1.0, abs(self.speed_kmh) / s.v_max)
        target = steer * s.hull_turn * speed_k * (0.5 + 0.5 * self.terrain_k)
        self.hull_rate = self._approach(self.hull_rate, target,
                                        s.hull_alpha, s.hull_alpha * HULL_BRAKE_K, dt)
        delta = self.hull_rate * dt

        old = self.hull_angle
        new = normalize_angle(old + delta)
        # если поворот упирается в препятствие, поворачиваем только до касания и гасим вращение
        if (self._has_solids(obstacles) and delta != 0
                and not self._overlaps(self.x, self.y, old, obstacles)
                and self._overlaps(self.x, self.y, new, obstacles)):
            frac = find_free_fraction(
                lambda f: self._overlaps(self.x, self.y, normalize_angle(old + delta * f), obstacles))
            delta *= frac
            new = normalize_angle(old + delta)
            self.hull_rate = 0.0
        self.hull_angle = new
        return delta

    def _drive(self, throttle, steer, dt, obstacles=()):
        self._update_speed(throttle, steer, dt)
        distance = self.speed_kmh * KMH_TO_PX * dt  # со знаком: минус = назад
        if distance == 0.0:
            return 0.0

        fx, fy = heading_vector(self.hull_angle)
        dx = fx * distance
        dy = fy * distance

        new_x, new_y = self.x + dx, self.y + dy
        # если путь упирается в препятствие, подъезжаем вплотную
        if (self._has_solids(obstacles)
                and not self._overlaps(self.x, self.y, self.hull_angle, obstacles)
                and self._overlaps(new_x, new_y, self.hull_angle, obstacles)):
            frac = find_free_fraction(
                lambda f: self._overlaps(self.x + dx * f, self.y + dy * f, self.hull_angle, obstacles))
            new_x, new_y = self.x + dx * frac, self.y + dy * frac

        moved = math.hypot(new_x - self.x, new_y - self.y)
        if moved < abs(distance) * 0.999:  # путь урезан препятствием: танк встал
            self.speed_kmh = 0.0
        self.x, self.y = new_x, new_y
        return math.copysign(moved, distance)  # гусеницы крутятся только на реально пройденный путь

    def _update_speed(self, throttle, steer, dt):
        """Приближает текущую скорость к целевой с учётом разгона, наката и торможения."""
        s = self.spec
        cap_fwd, cap_back = s.v_max, s.v_back
        if steer != 0:
            cap_fwd *= TURN_SPEED_PENALTY
            cap_back *= TURN_SPEED_PENALTY
        cap_fwd *= self.terrain_k                            # вязкая местность: потолок ниже
        cap_back *= self.terrain_k

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

        if self.terrain_k < 1.0:
            v = self._terrain_drag(v, throttle, cap_fwd, cap_back, dt)
        self.speed_kmh = v

    def _terrain_drag(self, v, throttle, cap_fwd, cap_back, dt):
        """Вязкая местность: скорость сверх потолка гасится быстро; без газа танк останавливается быстрее обычного."""
        if v > cap_fwd:
            v = max(cap_fwd, v - TERRAIN_BRAKE * dt)
        elif v < -cap_back:
            v = min(-cap_back, v + TERRAIN_BRAKE * dt)
        if throttle == 0.0:
            roll = (1.0 - self.terrain_k) * TERRAIN_ROLL_DECEL * dt
            v = math.copysign(max(0.0, abs(v) - roll), v)
        return v

    def _animate_tracks(self, distance, delta_hull):
        scale = self.spec.HULL_SCALE
        rot_dist = math.radians(delta_hull) * self.TRACK_RADIUS
        # Поворот вправо (delta_hull > 0): левая гусеница едет вперёд, правая назад.
        # "Вперёд" для узора = отрицательное смещение. distance переводим в пиксели спрайта.
        self.left_track_offset = (self.left_track_offset - distance / scale - rot_dist) % self.TRACK_STEP
        self.right_track_offset = (self.right_track_offset - distance / scale + rot_dist) % self.TRACK_STEP

    def _aim_turret(self, aim_point, dt, obstacles=()):
        s = self.spec
        target_rate = 0.0
        diff = 0.0
        if aim_point is not None:
            dx = aim_point[0] - self.x
            dy = aim_point[1] - self.y
            if math.hypot(dx, dy) >= self.AIM_DEAD_ZONE:
                target_abs = math.degrees(math.atan2(dy, dx)) + 90.0
                diff = shortest_angle_diff(target_abs, self.turret_angle)
                # скорость, с которой ещё успеем затормозить к цели: v = sqrt(2·α·путь)
                allowed = math.sqrt(2.0 * s.turret_alpha * abs(diff))
                target_rate = math.copysign(min(s.turret_turn, allowed), diff)

        # цели нет (Q, курсор над интерфейсом) — башня плавно останавливается по инерции
        self.turret_rate = self._approach(self.turret_rate, target_rate,
                                          s.turret_alpha, s.turret_alpha, dt)
        delta = self.turret_rate * dt
        if diff != 0.0 and delta * diff > 0.0 and abs(delta) > abs(diff):
            delta = diff                                  # не перелетаем цель
            self.turret_rate = 0.0

        old = self.turret_rel_angle
        if (obstacles and delta != 0
                and not self._barrel_hits(self.x, self.y, self.hull_angle + old, obstacles)
                and self._barrel_hits(self.x, self.y, self.hull_angle + old + delta, obstacles)):
            frac = find_free_fraction(
                lambda f: self._barrel_hits(self.x, self.y, self.hull_angle + old + delta * f, obstacles))
            delta *= frac
            self.turret_rate = 0.0
        self.turret_rel_angle = (old + delta) % 360.0

    def _update_gun(self, fire, dt):
        """Перезарядка и выстрел. Возвращает Shot, если выстрел произошёл в этом кадре."""
        self.reload_left = max(0.0, self.reload_left - dt)
        self.since_shot += dt
        if not fire or self.reload_left > 0.0:
            return None

        self.reload_left = self.spec.reload
        self.since_shot = 0.0
        mx, my = self.muzzle_point()
        return Shot(mx, my, self.turret_angle)

    def muzzle_point(self):
        """Текущая позиция дульного среза (мировые px)."""
        fx, fy = heading_vector(self.turret_angle)
        dist = self.spec.MUZZLE_DIST_PX
        return self.x + fx * dist, self.y + fy * dist

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