"""vehicles/base.py — Vehicle: шасси любой наземной техники.
Здесь движение, столкновения, броня по граням, таран и здоровье. Оружия и башни тут нет:
подкласс переопределяет _update_weapons() и возвращает Shot или None.

Что должен уметь spec: hp, mass, front, side, rear, v_max, v_back, hull_turn, hull_alpha,
accel, accel_back, accel_at(v), decel_coast, decel_brake, HULL_SCALE,
COLLISION_HALF_W_PX, COLLISION_HALF_L_PX, COLLISION_SHIFT_PX, REACH_PX."""
import math

from engine import (
    normalize_angle, obb_hits_obb, obb_segment_hit, VehicleCommand, PX_PER_M,
    heading_vector, find_free_fraction, Team, TargetType, fmt_num
)
from combat import resolve_hit, Damageable
from .chassis_params import (
    KMH_TO_PX, HULL_BRAKE_K, HULL_TURN_SPEED_LOSS, ARMOR_K, TERRAIN_MIN_K, TERRAIN_BRAKE,
    TERRAIN_ROLL_DECEL, TURN_SPEED_PENALTY, TRACK_LINK_M, TRACK_OFFSET_M,
    CONTACT_TURN_STEPS, CONTACT_PUSH_STEPS, SLIDE_ANGLES_DEG, SLIDE_MIN_PX, CONTACT_SCRUB,
    CONTACT_STOP_PROGRESS, PUSH_FRICTION_MS2, PUSH_STOP_PX, TERRAIN_SAMPLE_REACH
)

PLAYER_TITLE = "Ваша техника"            # заголовок сводки, когда это техника игрока

# Направления отодвигания корпуса: (вдоль корпуса, поперёк). Назад, вперёд, в стороны и диагонали.
_NUDGE_DIRS = ((-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0),
               (-0.7, -0.7), (-0.7, 0.7), (0.7, -0.7), (0.7, 0.7))

class Vehicle(Damageable):
    target_type = TargetType.VEHICLE
    renderer_key = None                         # ключ в реестре рендереров (Renderer.vehicle_renderers)
    TRACK_STEP = TRACK_LINK_M * PX_PER_M        # шаг между траками, px эталонного мира
    TRACK_RADIUS = TRACK_OFFSET_M * PX_PER_M    # расстояние от центра до гусеницы, px

    def __init__(self, x=0.0, y=0.0, *, spec, team_color=(200, 40, 40),
                 team=Team.PLAYER, label="техника", emblem=""):
        self.spec = spec
        self.team_color = team_color
        self.team = team
        self.label = label              # название архетипа для сводки (у игрока не используется)
        self.emblem = emblem
        self.x = float(x)
        self.y = float(y)
        self.hp = float(spec.hp)        # текущее здоровье (максимум задаёт spec.hp)
        self.hull_angle = 0.0           # 0 = вверх, по часовой стрелке
        self.hull_rate = 0.0            # текущая угловая скорость корпуса, °/с (+ = по часовой)
        self.left_track_offset = 0.0
        self.right_track_offset = 0.0
        self.speed_kmh = 0.0            # текущая скорость вдоль корпуса, км/ч (минус = назад)
        self.terrain_k = 1.0            # множитель скорости от местности под корпусом
        self._terrain = None            # карта препятствий; её передаёт GameContext в update()
        self._patches = ()              # пятна карты рядом с техникой; обновляется в начале update()
        self.impact_kmh = None          # скорость в момент удара в ЭТОМ кадре (None: удара не было)
        self.push_vx = 0.0              # скорость, полученная от тарана, px/с мира
        self.push_vy = 0.0

    # ---------- параметры ----------
    @property
    def max_hp(self):
        return self.spec.hp

    @property
    def mass_t(self):
        """Масса, т (для тарана: тот же интерфейс, что у Wall.mass_t и Patch.mass_t)."""
        return self.spec.mass

    @property
    def alive(self):
        return self.hp > 0.0

    def set_spec(self, spec):
        """Новая спецификация (ползунки конструктора). Доля здоровья сохраняется."""
        frac = self.hp / self.spec.hp if self.spec.hp > 0 else 1.0
        self.spec = spec
        self.hp = spec.hp * max(0.0, min(1.0, frac))

    def place_at(self, spot):
        """Поставить технику в найденную точку спавна (любой объект с x, y, angle) и обнулить движение."""
        self.x, self.y = float(spot.x), float(spot.y)
        self.hull_angle = spot.angle % 360.0
        self.speed_kmh = 0.0
        self.hull_rate = 0.0

    # ---------- столкновения ----------
    def _hull_obb(self, x, y, angle):
        """Прямоугольник корпуса: центр лежит позади оси башни."""
        s = self.spec
        fx, fy = heading_vector(angle)
        return (x - fx * s.COLLISION_SHIFT_PX, y - fy * s.COLLISION_SHIFT_PX,
                s.COLLISION_HALF_W_PX, s.COLLISION_HALF_L_PX, angle)

    def hull_obb(self):
        """Прямоугольник корпуса в формате столкновений: (x, y, half_w, half_l, angle)."""
        return self._hull_obb(self.x, self.y, self.hull_angle)

    def _overlaps(self, x, y, angle, obstacles):
        """angle — угол КОРПУСА. Задевает ли препятствие корпус."""
        hull = self._hull_obb(x, y, angle)
        if any(obb_hits_obb(*hull, *other) for other in obstacles):
            return True
        return self._terrain is not None and self._terrain.blocks_obb_in(self._patches, hull)

    def _has_solids(self, obstacles):
        """Есть ли вообще что проверять на столкновение (стены или карта местности)."""
        return bool(obstacles) or self._terrain is not None

    def reach_px(self):
        """Радиус, в который попадает всё, что техника может задеть за один кадр (считается в spec)."""
        return self.spec.REACH_PX

    def hits_obb(self, other):
        """Задевает ли корпус повёрнутый прямоугольник (x, y, half_w, half_l, angle)."""
        return obb_hits_obb(*self._hull_obb(self.x, self.y, self.hull_angle), *other)

    def footprint_at(self, x, y, hull_angle):
        """Прямоугольники, которые техника займёт в точке (x, y). Корпус всегда первый:
        по нему проверяется грунт."""
        return [self._hull_obb(x, y, hull_angle)]

    # ---------- попадания снарядов (универсальный интерфейс цели) ----------
    def raycast(self, x0, y0, x1, y1):
        """Пересечение отрезка с корпусом: (self, t, normal) или None."""
        res = obb_segment_hit(self._hull_obb(self.x, self.y, self.hull_angle), x0, y0, x1, y1)
        return None if res is None else (self, res[0], res[1])

    def zone_at(self, normal, hull_angle=None):
        """Какая грань корпуса принимает удар: "front" / "side" / "rear".
        normal — наружная нормаль грани. hull_angle — гипотетический угол корпуса (по умолчанию текущий)."""
        if normal is None:                      # выстрел начался внутри корпуса
            return "side"
        fx, fy = heading_vector(self.hull_angle if hull_angle is None else hull_angle)
        along = normal[0] * fx + normal[1] * fy
        if along > 0.5:
            return "front"
        if along < -0.5:
            return "rear"
        return "side"

    def armor_at(self, normal, hull_angle=None):
        """Броня грани, в которую попали (мм, с коэффициентом ARMOR_K)."""
        s = self.spec
        base = {"front": s.front, "side": s.side, "rear": s.rear}[self.zone_at(normal, hull_angle)]
        return base * ARMOR_K

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        return resolve_hit(penetration, self.armor_at(normal), cos_impact)

    def describe(self):
        """(заголовок, [(название, значение), ...]) для краткой сводки. Подклассы дополняют."""
        s = self.spec
        title = self.PLAYER_TITLE if self.team is Team.PLAYER else f"Враг: {self.label}"
        return title, [
            ("Броня: лоб", f"{s.front:.0f} мм"),
            ("Броня: борт", f"{s.side:.0f} мм"),
            ("Броня: корма", f"{s.rear:.0f} мм"),
            ("Масса", f"{fmt_num(s.mass, 1)} т"),
        ]

    def hull_offset_to(self, x, y):
        """Сколько градусов надо довернуть корпус (+ по часовой), чтобы точка (x, y) стала досягаема
        орудием. Базовая техника: 0 (вопрос не стоит)."""
        return 0.0

    # ---------- кадр ----------
    def update(self, command: VehicleCommand, dt, obstacles=(), terrain=None):
        """obstacles — повёрнутые прямоугольники стен и чужой техники (x, y, half_w, half_l, angle).
        terrain — карта естественных препятствий (TerrainMap) или None.
        Возвращает Shot или None (даёт подкласс через _update_weapons)."""
        self.impact_kmh = None          # флаг удара живёт ровно один кадр
        self._terrain = terrain
        self._patches = terrain.patches_near(self.x, self.y, self.reach_px()) if terrain is not None else ()
        self._sample_terrain()
        delta_hull = self._rotate_hull(command.steer, dt, obstacles)
        distance = self._drive(command.throttle, command.steer, dt, obstacles)
        self._animate_tracks(distance, delta_hull)
        return self._update_weapons(command, dt)

    def _update_weapons(self, command, dt):
        """Хук для подклассов: башня, орудие, перезарядка. Возвращает Shot или None."""
        return None

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
    def _drive(self, throttle, steer, dt, obstacles=()):
        self._update_speed(throttle, steer, dt)
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
        """Вязкая местность: скорость сверх потолка гасится быстро; без газа техника останавливается быстрее обычного."""
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