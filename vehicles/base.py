"""vehicles/base.py — Vehicle: шасси любой наземной техники.
Здесь движение, столкновения, броня по граням, таран и здоровье. Оружия и башни тут нет:
подкласс переопределяет _update_weapons() и возвращает Shot или None.."""
import math

from engine import (
    normalize_angle, obb_hits_obb, obb_segment_hit, VehicleCommand, PX_PER_M,
    heading_vector, find_free_fraction, Team, TargetType, fmt_num, clamp,
    convex_segment_hit, to_local_frame, vec_to_local, vec_from_local
)
from combat import resolve_hit, Damageable
from .chassis_params import (
    KMH_TO_PX, HULL_BRAKE_K, HULL_TURN_SPEED_LOSS, ARMOR_K, TERRAIN_MIN_K, TERRAIN_BRAKE,
    TERRAIN_ROLL_DECEL, TURN_SPEED_PENALTY, TRACK_LINK_M, TRACK_OFFSET_M, ONE_TRACK_SPEED_K,
    CONTACT_TURN_STEPS, CONTACT_PUSH_STEPS, SLIDE_ANGLES_DEG, SLIDE_MIN_PX, CONTACT_SCRUB,
    CONTACT_STOP_PROGRESS, PUSH_FRICTION_MS2, PUSH_STOP_PX, TERRAIN_SAMPLE_REACH,
    SCREEN_HALF_W_M, SCREEN_FACE_EPS_PX, TRACK_EDGE_ZONE_M, TRACK_HIT_TOL_M
)
from .running_gear import TrackState, LEFT, RIGHT, TRACK_SIDES

PLAYER_TITLE = "Ваша техника"            # заголовок сводки, когда это техника игрока

# Направления отодвигания корпуса: (вдоль корпуса, поперёк). Назад, вперёд, в стороны и диагонали.
_NUDGE_DIRS = ((-1.0, 0.0), (1.0, 0.0), (0.0, -1.0), (0.0, 1.0),
               (-0.7, -0.7), (-0.7, 0.7), (0.7, -0.7), (0.7, 0.7))

class Vehicle(Damageable):
    target_type = TargetType.VEHICLE
    renderer_key = None                         # ключ в реестре рендереров (Renderer.vehicle_renderers)
    TRACK_STEP = TRACK_LINK_M * PX_PER_M        # шаг между траками, px эталонного мира

    @property
    def TRACK_RADIUS(self):
        """Расстояние от центра до гусеницы, px эталонного спрайта: колея берётся из раскладки."""
        layout = self.spec.layout
        return (layout.track_x if layout is not None else TRACK_OFFSET_M) * PX_PER_M

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
        self.tracks = TrackState()      # сбитые гусеницы и ремонт
        self.repaired_track = None      # сторона гусеницы, которую починили в ЭТОМ кадре (для сообщений)

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

    def _local_parts(self):
        """Выпуклые участки для попаданий в метрах корпуса (центр корпуса = (0, 0), перед = -v).
        Без раскладки это прямоугольник хитбокса: те же числа, что у hull_obb."""
        layout = self.spec.layout
        if layout is not None:
            return layout.hit_parts
        b = self.spec.body
        hw, hl = b.coll_half_w_m, b.coll_half_l_m
        return (((-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)),)

    def _to_hull_local(self, x, y):
        """Мировая точка -> метры корпуса (u вправо, v назад)."""
        cx, cy, _, _, ang = self.hull_obb()
        return to_local_frame(x, y, cx, cy, ang, self.spec.HULL_SCALE * PX_PER_M)

    def raycast(self, x0, y0, x1, y1):
        """Пересечение отрезка с корпусом: (self, t, normal) или None.
        Отрезок переводится в систему корпуса, там ищется ближайшая из выпуклых частей раскладки."""
        cx, cy, _, _, ang = self.hull_obb()
        k = self.spec.HULL_SCALE * PX_PER_M
        u0, v0 = to_local_frame(x0, y0, cx, cy, ang, k)
        u1, v1 = to_local_frame(x1, y1, cx, cy, ang, k)
        best = None
        for part in self._local_parts():
            res = convex_segment_hit(part, u0, v0, u1, v1)
            if res is not None and (best is None or res[0] < best[0]):
                best = res
        if best is None:
            return None
        t, n = best
        if n is not None:
            n = vec_from_local(n[0], n[1], ang)      # масштаб однородный, нормаль только поворачиваем
        return self, t, n

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

    def plate_at(self, normal, hull_angle=None):
        """Плита брони, принявшая удар: та, чья наружная нормаль ближе всего к normal (мировая).
        None, если у техники нет раскладки. Нормаль None (выстрел начался внутри) = боковая плита."""
        layout = self.spec.layout
        if layout is None:
            return None
        if normal is None:
            return next((p for p in layout.plates if p.zone == "side"), layout.plates[0])
        ang = self.hull_angle if hull_angle is None else hull_angle
        nu, nv = vec_to_local(normal[0], normal[1], ang)
        return layout.plate_by_normal(nu, nv)

    def armor_at(self, normal, hull_angle=None):
        """Броня грани, в которую попали (мм, с коэффициентом ARMOR_K).
        Зона берётся из zone_at (одна на весь проект), коэффициент толщины из плиты.
        Борт прикрыт гусеницей, лоб экранами: эти добавки идут поверх плиты и на k не умножаются."""
        s = self.spec
        zone = self.zone_at(normal, hull_angle)
        base = {"front": s.front, "side": s.side, "rear": s.rear}[zone]
        plate = self.plate_at(normal, hull_angle)
        if plate is not None:
            base *= plate.k
        if zone == "front":
            base += s.screen_mm
        elif zone == "side":
            base += s.gear.armor_mm
        return base * ARMOR_K

    def armor_along(self, from_deg, hull_deg=None, lateral=0.0):
        """Броня и косинус угла для луча, пришедшего с азимута from_deg (от этой техники к стрелку)."""
        if hull_deg is None:
            hull_deg = self.hull_angle
        wx, wy = heading_vector(from_deg)
        ex, ey = vec_to_local(wx, wy, hull_deg)       # единичный вектор на стрелка в системе корпуса
        tx, ty = -ey * lateral, ex * lateral          # точка прицеливания
        reach = 50.0                                  # м: заведомо больше корпуса
        best = None
        for part in self._local_parts():
            res = convex_segment_hit(part, tx + ex * reach, ty + ey * reach,
                                     tx - ex * reach, ty - ey * reach)
            if res is not None and (best is None or res[0] < best[0]):
                best = res
        if best is None or best[1] is None:
            return None
        nu, nv = best[1]
        cos_i = abs(ex * nu + ey * nv)
        normal = vec_from_local(nu, nv, hull_deg)
        return self.armor_at(normal, hull_deg), cos_i

    def hit_result(self, penetration, cos_impact=1.0, normal=None):
        return resolve_hit(penetration, self.armor_at(normal), cos_impact)

    def describe(self):
        """(заголовок, [(название, значение), ...]) для краткой сводки. Подклассы дополняют."""
        s = self.spec
        title = self.PLAYER_TITLE if self.team is Team.PLAYER else f"Враг: {self.label}"
        return title, [
            ("Броня: лоб", f"{s.front:.0f}" + (f" + {s.screen_mm:.0f}" if s.screen_mm else "") + " мм"),
            ("Броня: борт", f"{s.side:.0f} + {s.gear.armor_mm:.0f} мм"),
            ("Броня: корма", f"{s.rear:.0f} мм"),
            ("Масса", f"{fmt_num(s.mass, 1)} т"),
            ("Гусеницы", self._track_status()),
        ]

    def hull_offset_to(self, x, y):
        """Сколько градусов надо довернуть корпус (+ по часовой), чтобы точка (x, y) стала досягаема
        орудием. Базовая техника: 0 (вопрос не стоит)."""
        return 0.0

    # ---------- гусеницы ----------
    def track_at(self, x, y):
        """Какую гусеницу задевает точка попадания (x, y): "left" / "right" или None.
        Сбить можно только передний или задний конец гусеницы (TRACK_EDGE_ZONE_M)."""
        layout = self.spec.layout
        if layout is None:
            return self._track_at_legacy(x, y)
        u, v = self._to_hull_local(x, y)
        tol = TRACK_HIT_TOL_M
        for side, (x0, y0, x1, y1) in zip((LEFT, RIGHT), layout.track_rects):
            if not (x0 - tol <= u <= x1 + tol and y0 - tol <= v <= y1 + tol):
                continue
            if v <= y0 + TRACK_EDGE_ZONE_M or v >= y1 - TRACK_EDGE_ZONE_M:
                return side
        return None

    def _track_at_legacy(self, x, y):
        """Старая логика по прямоугольнику хитбокса. Нужна технике без раскладки (удалить на этапе 11)."""
        cx, cy, hw, hl, ang = self.hull_obb()
        rad = math.radians(ang)
        c, sn = math.cos(rad), math.sin(rad)
        dx, dy = x - cx, y - cy
        u = dx * c + dy * sn            # поперёк корпуса (+ вправо)
        v = -dx * sn + dy * c           # вдоль корпуса (минус = нос)
        s = self.spec
        if abs(u) < hw - s.TRACK_BAND_PX:       # не в полосе гусеницы
            return None
        if abs(v) < hl - s.TRACK_EDGE_PX:       # не у переднего или заднего края
            return None
        return LEFT if u < 0.0 else RIGHT

    def screen_at(self, x, y):
        """Попала ли точка (x, y) в лобовые экраны: передняя грань корпуса, средняя часть по ширине.
        Если экранов нет (screen_mm = 0), всегда False."""
        s = self.spec
        if s.screen_mm <= 0.0:
            return False
        layout = s.layout
        if layout is None:
            return self._screen_at_legacy(x, y)
        u, v = self._to_hull_local(x, y)
        k = s.HULL_SCALE * PX_PER_M
        x0, x1 = layout.screen_x
        return v <= layout.screen_y + SCREEN_FACE_EPS_PX / k and x0 <= u <= x1

    def _screen_at_legacy(self, x, y):
        """Старая логика (удалить на этапе 11)."""
        s = self.spec
        cx, cy, hw, hl, ang = self.hull_obb()
        rad = math.radians(ang)
        c, sn = math.cos(rad), math.sin(rad)
        dx, dy = x - cx, y - cy
        u = dx * c + dy * sn            # поперёк корпуса
        v = -dx * sn + dy * c           # вдоль корпуса (минус = нос)
        half = SCREEN_HALF_W_M * s.HULL_SCALE * PX_PER_M
        return v <= -hl + SCREEN_FACE_EPS_PX and abs(u) <= half

    def module_at(self, x, y):
        """Внешний модуль, который первым задевает точка попадания (x, y).
        Возвращает "left" / "right" (целая гусеница), "screen" (лобовой экран) или None.
        Гусеница проверяется первой: на углу лба она закрывает экран."""
        side = self.track_at(x, y)
        if side is not None and not self.tracks.is_broken(side):
            return side
        if self.screen_at(x, y):
            return "screen"
        return None

    def knock_track(self, x, y):
        """Попали в точку (x, y): сбить гусеницу, если это её край. Возвращает сторону или None."""
        side = self.track_at(x, y)
        if side is None or not self.tracks.break_track(side):
            return None
        return side

    def start_repair(self, side=None):
        """Начать ремонт сбитой гусеницы. Одновременно идёт только один ремонт.
        Возвращает сторону, которую начали чинить, или None."""
        return self.tracks.start_repair(self.spec.gear.repair_s, side)

    def _track_status(self):
        names = {LEFT: "левая", RIGHT: "правая"}
        if not self.tracks.broken:
            return "целы"
        return "сбита: " + ", ".join(names[s] for s in TRACK_SIDES if self.tracks.is_broken(s))

    def _track_inputs(self, throttle, steer):
        """Газ и руль с учётом сбитых гусениц.
        Обе целы: без изменений. Обе сбиты: стоим. Цела одна: работает только она,
        машина ползёт по дуге вокруг стоящей гусеницы (поворот в сторону сбитой)."""
        left_bad = self.tracks.is_broken(LEFT)
        right_bad = self.tracks.is_broken(RIGHT)
        if not left_bad and not right_bad:
            return throttle, steer
        if left_bad and right_bad:
            return 0.0, 0.0
        if left_bad:                                   # цела правая: центр поворота у левой, крутимся влево
            u = clamp(throttle - steer, -1.0, 1.0)
            return u * ONE_TRACK_SPEED_K, -u
        u = clamp(throttle + steer, -1.0, 1.0)         # цела левая: крутимся вправо
        return u * ONE_TRACK_SPEED_K, u

    # ---------- кадр ----------
    def update(self, command: VehicleCommand, dt, obstacles=(), terrain=None):
        """obstacles — повёрнутые прямоугольники стен и чужой техники (x, y, half_w, half_l, angle).
        terrain — карта естественных препятствий (TerrainMap) или None.
        Возвращает Shot или None (даёт подкласс через _update_weapons)."""
        self.impact_kmh = None          # флаг удара живёт ровно один кадр
        self._terrain = terrain
        self._patches = terrain.patches_near(self.x, self.y, self.reach_px()) if terrain is not None else ()
        self._sample_terrain()
        self.repaired_track = self.tracks.update(dt)        # ремонт идёт, пока машина жива и обновляется
        throttle, steer = self._track_inputs(command.throttle, command.steer)
        delta_hull = self._rotate_hull(steer, dt, obstacles)
        distance = self._drive(throttle, steer, dt, obstacles)
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
        if not self.tracks.is_broken(LEFT):
            self.left_track_offset = (self.left_track_offset - distance / scale - rot_dist) % self.TRACK_STEP
        if not self.tracks.is_broken(RIGHT):
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