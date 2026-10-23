"""vehicles/chassis/motion.py — движение шасси: разгон и торможение, поворот корпуса, скольжение
вдоль препятствий, вязкая местность, толчок от тарана. Миксин для Vehicle: состояния не хранит,
читает поля и методы итогового класса (spec, _overlaps, _has_solids, _hull_obb, hull_angle...)."""
import math

from engine import normalize_angle, heading_vector, find_free_fraction, PX_PER_M
from vehicles.chassis.params import (
    KMH_TO_PX, HULL_BRAKE_K, HULL_TURN_SPEED_LOSS, TERRAIN_MIN_K, TERRAIN_BRAKE,
    TERRAIN_ROLL_DECEL, TURN_SPEED_PENALTY, CONTACT_TURN_STEPS, CONTACT_PUSH_STEPS,
    SLIDE_ANGLES_DEG, SLIDE_MIN_PX, CONTACT_SCRUB, CONTACT_STOP_PROGRESS,
    PUSH_FRICTION_MS2, PUSH_STOP_PX, TERRAIN_SAMPLE_REACH,
)

# Направления отодвигания корпуса: (вдоль корпуса, поперёк). Назад, вперёд, в стороны и диагонали.
_NUDGE_DIRS = ((-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0),
               (-0.7, -0.7), (-0.7, 0.7), (0.7, -0.7), (0.7, 0.7))

class MotionMixin:

    # ---------- грунт ----------
    def ground_probes_at(self, x, y, hull_angle):
        """Три точки замера грунта вдоль оси корпуса (зад, центр, перед) для машины в (x, y)."""
        hx, hy, _, half_l, angle = self._hull_obb(x, y, hull_angle)
        fx, fy = heading_vector(angle)
        reach = half_l * TERRAIN_SAMPLE_REACH
        return [(hx + fx * d, hy + fy * d) for d in (-reach, 0.0, reach)]

    def _sample_terrain(self):
        """Множитель скорости: среднее по трём точкам под корпусом,
        поэтому при въезде в воду техника тормозится постепенно."""
        terrain = self._terrain
        if terrain is None:
            self.terrain_k = 1.0
            return
        total = 0.0
        for px, py in self.ground_probes_at(self.x, self.y, self.hull_angle):
            total += terrain.speed_in(self._patches, px, py)
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

    # ---------- поворот корпуса ----------
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
        if (self._has_solids(obstacles) and delta != 0
                and not self._overlaps(self.x, self.y, old, obstacles)
                and self._overlaps(self.x, self.y, new, obstacles)):
            turned = self._turn_with_resistance(old, delta, obstacles)
            if turned is not None:
                # поворачиваемся медленнее и «отползаем» от препятствия; hull_rate не гасим,
                # поэтому сопротивление действует, пока игрок держит поворот
                new, ox, oy, delta = turned
                self.x += ox
                self.y += oy
            else:
                # подобрать не удалось: поворачиваем до касания и гасим вращение
                frac = find_free_fraction(
                    lambda f: self._overlaps(self.x, self.y, normalize_angle(old + delta * f), obstacles))
                delta *= frac
                new = normalize_angle(old + delta)
                self.hull_rate = 0.0
        self.hull_angle = new
        return delta

    def _turn_with_resistance(self, old, delta, obstacles):
        """Поворот на delta упёрся в препятствие. Пробуем повернуть на часть угла и чуть сдвинуть корпус
        от препятствия. Возвращает (новый угол, смещение x, смещение y, применённый угол) или None."""
        s = self.spec
        radius = math.hypot(s.COLLISION_HALF_W_PX, s.COLLISION_HALF_L_PX)
        fx, fy = heading_vector(old)
        rx, ry = -fy, fx  # вправо от корпуса
        for k in CONTACT_TURN_STEPS:
            part = delta * k
            new = normalize_angle(old + part)
            push_max = radius * math.radians(abs(part)) * 1.5 + 0.5  # на столько угол мог «въехать» в препятствие
            for f in CONTACT_PUSH_STEPS:
                for a, b in _NUDGE_DIRS:
                    ox = (fx * a + rx * b) * push_max * f
                    oy = (fy * a + ry * b) * push_max * f
                    if not self._overlaps(self.x + ox, self.y + oy, new, obstacles):
                        return new, ox, oy, part
        return None

    # ---------- движение ----------
    def _drive(self, throttle, steer, dt, obstacles=(), brake=False):
        self._update_speed(throttle, steer, dt, brake)
        distance = self.speed_kmh * KMH_TO_PX * dt  # со знаком: минус = назад
        if distance == 0.0:
            return 0.0

        fx, fy = heading_vector(self.hull_angle)
        dx = fx * distance
        dy = fy * distance
        new_x, new_y = self.x + dx, self.y + dy
        along = distance  # сколько пути реально пройдено вдоль курса

        if (self._has_solids(obstacles)
                and not self._overlaps(self.x, self.y, self.hull_angle, obstacles)
                and self._overlaps(new_x, new_y, self.hull_angle, obstacles)):
            self.impact_kmh = self.speed_kmh        # скорость ДО гашения: по ней считается таран
            new_x, new_y = self._move_along_obstacle(dx, dy, obstacles)
            along = (new_x - self.x) * fx + (new_y - self.y) * fy
            progress = max(0.0, min(1.0, along / distance))
            self._scrub_speed(progress, dt)

        self.x, self.y = new_x, new_y
        return along

    def _move_along_obstacle(self, dx, dy, obstacles):
        """Прямой путь (dx, dy) упёрся в препятствие. Подъезжаем вплотную, а остаток пути
        отклоняем на небольшой угол в обе стороны: первый свободный вариант и есть скольжение вдоль стены.
        Возвращает новую позицию (x, y); угол корпуса не меняется."""
        x0, y0, ang = self.x, self.y, self.hull_angle
        frac = find_free_fraction(
            lambda f: self._overlaps(x0 + dx * f, y0 + dy * f, ang, obstacles))
        x1, y1 = x0 + dx * frac, y0 + dy * frac

        rest = (1.0 - frac) * math.hypot(dx, dy)  # путь, который не удалось проехать прямо
        if rest < SLIDE_MIN_PX:
            return x1, y1

        base = math.atan2(dy, dx)
        for deg in SLIDE_ANGLES_DEG:
            rad = math.radians(deg)
            length = rest * math.cos(rad)  # чем круче отклонение, тем короче скольжение
            for sign in (1, -1):
                a = base + rad * sign
                sx, sy = x1 + math.cos(a) * length, y1 + math.sin(a) * length
                if not self._overlaps(sx, sy, ang, obstacles):
                    return sx, sy
        return x1, y1  # удар почти в лоб: скользить некуда

    def _scrub_speed(self, progress, dt):
        """Трение о препятствие. progress = какая доля пути вперёд всё-таки пройдена (0..1).
        Касание вскользь почти не тормозит, а удар в лоб останавливает технику."""
        if progress < CONTACT_STOP_PROGRESS:
            self.speed_kmh = 0.0
            return
        loss = 1.0 - progress
        self.speed_kmh *= math.exp(-CONTACT_SCRUB * loss * loss * dt)

    def _update_speed(self, throttle, steer, dt, brake=False):
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
            if v > 0:
                rate = s.decel_brake if (target < 0 or brake) else s.decel_coast
                v = max(v - rate * dt, max(target, 0.0))
            else:
                v = max(v - s.accel_back * dt, target)
        elif v < target:
            if v < 0:
                rate = s.decel_brake if (target > 0 or brake) else s.decel_coast
                v = min(v + rate * dt, min(target, 0.0))
            else:
                v = min(v + s.accel_at(v) * dt, target)

        if self.terrain_k < 1.0:
            v = self._terrain_drag(v, throttle, cap_fwd, cap_back, dt)
        self.speed_kmh = v

    def _terrain_drag(self, v, throttle, cap_fwd, cap_back, dt):
        """Вязкая местность: скорость сверх потолка гасится быстро; без газа техника останавливается быстрее обычного."""
        if v > cap_fwd:
            v = max(cap_fwd, v - TERRAIN_BRAKE * dt)
        elif v < -cap_back:
            v = min(-cap_back, v + TERRAIN_BRAKE * dt)
        if throttle == 0.0:
            roll = (1.0 - self.terrain_k) * TERRAIN_ROLL_DECEL * dt
            v = math.copysign(max(0.0, abs(v) - roll), v)
        return v

    # ---------- скорость и таран ----------
    def velocity_px(self, speed_kmh=None):
        """Скорость корпуса в мировых px/с (нужна ботам для упреждения и тарану).
        speed_kmh: подставить другую скорость вдоль корпуса (по умолчанию текущую). Толчок от тарана включён."""
        fx, fy = heading_vector(self.hull_angle)
        v = (self.speed_kmh if speed_kmh is None else speed_kmh) * KMH_TO_PX
        return fx * v + self.push_vx, fy * v + self.push_vy

    def apply_impulse(self, nx, ny, dv_ms):
        """Таран: изменить скорость вдоль нормали (nx, ny) на dv_ms м/с (со знаком).
        Если машина сама врезалась (impact_kmh задан), составляющая вдоль корпуса меняет её ход
        (потеря скорости), а остальное уходит в толчок. Если её ударили, всё уходит в толчок."""
        k = dv_ms * PX_PER_M
        dvx, dvy = nx * k, ny * k
        if self.impact_kmh is not None:
            fx, fy = heading_vector(self.hull_angle)
            along = dvx * fx + dvy * fy
            self.impact_kmh += along / KMH_TO_PX     # база для следующего удара в этом же кадре
            self.speed_kmh = self.impact_kmh         # «отменяем» гашение скорости от стены/камня
            dvx -= along * fx
            dvy -= along * fy
        self.push_vx += dvx
        self.push_vy += dvy

    def update_push(self, dt, obstacles, terrain):
        """Сдвиг по инерции от толчка. Гасится сцеплением гусениц, упирается в препятствия."""
        if self.push_vx == 0.0 and self.push_vy == 0.0:
            return
        speed = math.hypot(self.push_vx, self.push_vy)
        drop = PUSH_FRICTION_MS2 * PX_PER_M * dt
        if speed <= drop + PUSH_STOP_PX:
            self.push_vx = self.push_vy = 0.0
            return
        k = (speed - drop) / speed
        self.push_vx *= k
        self.push_vy *= k

        self._terrain = terrain
        self._patches = terrain.patches_near(self.x, self.y, self.reach_px()) if terrain is not None else ()
        dx, dy = self.push_vx * dt, self.push_vy * dt
        if self._has_solids(obstacles) and self._overlaps(self.x + dx, self.y + dy, self.hull_angle, obstacles):
            frac = 0.0
            if not self._overlaps(self.x, self.y, self.hull_angle, obstacles):
                frac = find_free_fraction(
                    lambda f: self._overlaps(self.x + dx * f, self.y + dy * f, self.hull_angle, obstacles))
            dx *= frac
            dy *= frac
            self.push_vx = self.push_vy = 0.0        # упёрся: толчок закончился
        self.x += dx
        self.y += dy