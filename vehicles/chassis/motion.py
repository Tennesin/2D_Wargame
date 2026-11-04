"""vehicles/chassis/motion.py — движение шасси: разгон и торможение, поворот корпуса, скольжение
вдоль препятствий, вязкая местность, толчок от тарана. Миксин для Vehicle: состояния не хранит,
читает поля и методы итогового класса (spec, _overlaps, _has_solids, _hull_obb, hull_angle...)."""
import math

from engine import normalize_angle, heading_vector, find_free_fraction, clamp, PX_PER_M
from vehicles.chassis.params import (
    KMH_TO_PX, HULL_BRAKE_K, HULL_TURN_SPEED_LOSS, TERRAIN_MIN_K, TERRAIN_BRAKE,
    TERRAIN_ROLL_DECEL, TURN_SPEED_PENALTY, CONTACT_TURN_STEPS, CONTACT_PUSH_STEPS,
    SLIDE_ANGLES_DEG, SLIDE_MIN_PX, CONTACT_SCRUB, CONTACT_STOP_PROGRESS,
    PUSH_STOP_PX, TERRAIN_SAMPLE_REACH, RAM_MAX_SPIN_DEG_S,
    PUSH_LATERAL_FRICTION_MS2, PUSH_MAX_MS, PUSH_OVERSPEED_K, TERRAIN_PUSH_DRAG,
    PUSH_RAMP_S, SPIN_FRICTION_DEG_S2,
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
        """Множитель скорости."""
        terrain = self._terrain
        if terrain is None:
            self.terrain_k = 1.0
            self.terrain_kind = None
            return
        total = 0.0
        loss = None                                          # вид -> суммарная потеря скорости (создаётся лениво)
        for px, py in self.ground_probes_at(self.x, self.y, self.hull_angle):
            kind = terrain.kind_in(self._patches, px, py)
            k = 1.0 if kind is None else kind.speed_k
            total += k
            if kind is not None and not kind.solid:          # камень и глубокая вода сюда не заезжают
                if loss is None:
                    loss = {}
                loss[kind] = loss.get(kind, 0.0) + (1.0 - k)
        self.terrain_k = max(TERRAIN_MIN_K, total / 3.0)
        self.terrain_kind = max(loss, key=loss.get) if loss else None

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
        k = self.mods.turn_k
        # на ходу развернуться тяжелее, чем с места
        speed_k = 1.0 - HULL_TURN_SPEED_LOSS * min(1.0, abs(self.speed_kmh) / s.v_max)
        target = steer * s.hull_turn * k * speed_k * (0.5 + 0.5 * self.terrain_k)
        self.hull_rate = self._approach(self.hull_rate, target,
                                        s.hull_alpha * k, s.hull_alpha * k * HULL_BRAKE_K, dt)
        # свободное вращение после удара (сверх рабочей скорости поворота) гасится сцеплением гусениц;
        # обычная езда не затрагивается: рабочая скорость поворота остаётся прежней
        excess = abs(self.hull_rate) - s.hull_turn * k
        if excess > 0.0:
            grip = 1.0 + (1.0 - self.terrain_k) * TERRAIN_PUSH_DRAG
            cut = min(excess, SPIN_FRICTION_DEG_S2 * grip * dt)
            self.hull_rate -= math.copysign(cut, self.hull_rate)
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
        """Поворот на delta упёрся в препятствие."""
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
        """Прямой путь (dx, dy) упёрся в препятствие."""
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
        """Трение о препятствие."""
        if self._soft_contact_s > 0.0:
            return
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
    def velocity_px(self, speed_kmh=None, include_pending=False):
        """Скорость корпуса в мировых px/с."""
        fx, fy = heading_vector(self.hull_angle)
        v = (self.speed_kmh if speed_kmh is None else speed_kmh) * KMH_TO_PX
        vx, vy = fx * v + self.push_vx, fy * v + self.push_vy
        if include_pending:
            for item in self._pending:
                vx += item[0]
                vy += item[1]
        return vx, vy

    def apply_impulse(self, nx, ny, dv_ms, dw_rad_s=0.0):
        """Таран камня: изменить скорость вдоль нормали (nx, ny) на dv_ms м/с (со знаком)."""
        self.apply_velocity_change(nx * dv_ms, ny * dv_ms, dw_rad_s)

    @property
    def has_push(self):
        """Есть ли что обрабатывать в update_push (скольжение или невыданный толчок)."""
        return bool(self.push_vx or self.push_vy or self._pending)

    def push_ramp_s(self):
        """За сколько секунд эта машина "выдаёт" полученное изменение скорости: лёгкая быстрее, тяжёлая плавнее."""
        lo, hi = PUSH_RAMP_S
        return lo + (hi - lo) * self.mass_k

    def start_soft_contact(self, seconds):
        """Пока идёт мягкий контакт, упор в препятствие не обнуляет скорость (партнёр по удару разгоняется)."""
        self._soft_contact_s = max(self._soft_contact_s, seconds)

    def _queue_dv(self, dvx, dvy, ramp_s):
        """Изменение скорости (px/с): сразу или растянутое на ramp_s секунд."""
        if ramp_s <= 0.0:
            self.push_vx += dvx
            self.push_vy += dvy
        else:
            self._pending.append([dvx, dvy, ramp_s])

    def _release_pending(self, dt):
        """Равномерно выдаёт очередь в push: за каждый кадр доля dt / оставшееся время."""
        if not self._pending:
            return
        keep = []
        for item in self._pending:
            dvx, dvy, left = item
            k = 1.0 if left <= dt else dt / left
            self.push_vx += dvx * k
            self.push_vy += dvy * k
            item[0] = dvx - dvx * k
            item[1] = dvy - dvy * k
            item[2] = left - dt
            if item[2] > 0.0:
                keep.append(item)
        self._pending = keep

    def apply_velocity_change(self, dvx_ms, dvy_ms, dw_rad_s=0.0, ramp_s=0.0):
        """Изменение скорости центра на (dvx, dvy) м/с и угловой скорости на dw рад/с."""
        dvx, dvy = dvx_ms * PX_PER_M, dvy_ms * PX_PER_M
        if self.impact_kmh is not None:
            fx, fy = heading_vector(self.hull_angle)
            along = dvx * fx + dvy * fy
            self.impact_kmh += along / KMH_TO_PX  # база для следующего удара в этом же кадре
            self.speed_kmh = self.impact_kmh  # «отменяем» гашение скорости от стены/камня
            dvx -= along * fx
            dvy -= along * fy
        self._queue_dv(dvx, dvy, ramp_s)
        if dw_rad_s:
            spin = self.hull_rate + math.degrees(dw_rad_s)
            self.hull_rate = clamp(spin, -RAM_MAX_SPIN_DEG_S, RAM_MAX_SPIN_DEG_S)

    def update_push(self, dt, obstacles, terrain):
        """Толчок после удара."""
        self._release_pending(dt)
        if self.push_vx == 0.0 and self.push_vy == 0.0:
            return
        s = self.spec
        fx, fy = heading_vector(self.hull_angle)
        rx, ry = -fy, fx
        along = self.push_vx * fx + self.push_vy * fy
        lat = self.push_vx * rx + self.push_vy * ry

        if along:  # дальше едем (или пятимся) обычным ходом
            v = self.speed_kmh + along / KMH_TO_PX
            self.speed_kmh = clamp(v, -s.v_back * PUSH_OVERSPEED_K, s.v_max * PUSH_OVERSPEED_K)

        grip = 1.0 + (1.0 - self.terrain_k) * TERRAIN_PUSH_DRAG
        drop = PUSH_LATERAL_FRICTION_MS2 * grip * PX_PER_M * dt
        mag = abs(lat)
        if mag <= drop + PUSH_STOP_PX:
            lat = 0.0
        else:
            lat = math.copysign(min(mag - drop, PUSH_MAX_MS * PX_PER_M), lat)
        self.push_vx, self.push_vy = rx * lat, ry * lat
        if lat == 0.0:
            return

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
            self.push_vx = self.push_vy = 0.0  # упёрся: толчок закончился
        self.x += dx
        self.y += dy