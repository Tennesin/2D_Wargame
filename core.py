"""core.py — ядро: математика, команда, камера, генератор мира, танк.
Здесь нет ни pygame-отрисовки, ни чтения клавиатуры."""
import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import tank_config

# ==========================================
# 1. НАСТРОЙКИ МИРА
# ==========================================
CHUNK_SIZE = 512          # размер чанка (px)
CELL_SIZE = 16            # размер клетки земли (px); CHUNK_SIZE должен делиться на него
DECOR_ATTEMPTS = 90       # сколько попыток поставить декор на чанк
DECOR_MARGIN = 20         # отступ от края чанка, чтобы рисунки не обрезались

DRY_GRASS = (158, 184, 96)    # светлая сухая трава
LUSH_GRASS = (46, 112, 52)    # тёмная густая трава
FLOWER_COLORS = [
    (238, 238, 246),  # белый
    (242, 202, 60),   # жёлтый
    (222, 72, 92),    # красный
    (172, 112, 204),  # сиреневый
    (242, 142, 60),   # оранжевый
]
PX_PER_M = 100.0          # МАСШТАБ МИРА: 100 px = 1 метр (все скорости и расстояния в метрах переводим через него)
ZOOM_LEVELS = [round(0.10 * 6 ** (i / 20), 4) for i in range(21)]   # 0.10 … 0.60, шаг ≈ 9 %
DEFAULT_ZOOM_LEVEL = 5                                               # ≈ 0.157: танк 7 м ≈ 110 px

# ==========================================
# 2. МАТЕМАТИЧЕСКИЕ ПОМОЩНИКИ
# ==========================================
def normalize_angle(angle):
    return angle % 360.0


def shortest_angle_diff(target, current):
    """Кратчайшая разница углов в диапазоне [-180, 180)."""
    return (target - current + 180.0) % 360.0 - 180.0


def clamp(value, low, high):
    return max(low, min(high, value))


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def hash_int(ix, iy, seed):
    """Детерминированный целочисленный хеш трёх чисел (32 бита)."""
    h = (ix * 374761393 + iy * 668265263 + seed * 144269504) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


def hash_float(ix, iy, seed):
    """То же, но результат в диапазоне 0..1."""
    return hash_int(ix, iy, seed) / 4294967295.0


def value_noise(x, y, seed):
    """Плавный шум 0..1: хеши в углах клетки, сглаженная интерполяция."""
    x0 = math.floor(x)
    y0 = math.floor(y)
    fx = x - x0
    fy = y - y0
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    x0 = int(x0)
    y0 = int(y0)
    v00 = hash_float(x0, y0, seed)
    v10 = hash_float(x0 + 1, y0, seed)
    v01 = hash_float(x0, y0 + 1, seed)
    v11 = hash_float(x0 + 1, y0 + 1, seed)
    return lerp(lerp(v00, v10, fx), lerp(v01, v11, fx), fy)


# ==========================================
# 3. КОМАНДА МАШИНЕ
# ==========================================
@dataclass
class VehicleCommand:
    """Что машине «приказали» в этом кадре. Кто приказал (игрок или бот) — не важно."""
    throttle: float = 0.0                              # -1..1 (назад / вперёд)
    steer: float = 0.0                                 # -1..1 (влево / вправо)
    aim_point: Optional[Tuple[float, float]] = None    # куда целиться (МИРОВЫЕ координаты)
    fire: bool = False                                 # задел под стрельбу

@dataclass
class Shot:
    """Событие «выстрел»: откуда вылетел снаряд и куда смотрел ствол."""
    x: float          # мировые координаты дульного среза
    y: float
    angle: float      # абсолютный угол башни в градусах (0 = вверх, по часовой)

# ==========================================
# 4. КАМЕРА
# ==========================================
class Camera:
    """Камера: центр в мировых координатах + зум. Мир: 100 px = 1 м; на экране 1 м = 100 * zoom px."""

    def __init__(self, view_w=800, view_h=600):
        self.x = 0.0
        self.y = 0.0
        self.view_w = view_w
        self.view_h = view_h
        self.zoom_level = DEFAULT_ZOOM_LEVEL

    @property
    def zoom(self):
        return ZOOM_LEVELS[self.zoom_level]

    def zoom_by(self, steps):
        """Сдвинуть уровень зума: steps > 0 — приблизить, < 0 — отдалить."""
        self.zoom_level = int(clamp(self.zoom_level + steps, 0, len(ZOOM_LEVELS) - 1))

    def resize(self, view_w, view_h):
        self.view_w = view_w
        self.view_h = view_h

    def center_on(self, x, y):
        self.x = x
        self.y = y

    def origin_px(self):
        """Сдвиг мира в ЭКРАННЫХ пикселях (целые числа, чтобы земля не дрожала)."""
        z = self.zoom
        return round(self.x * z) - self.view_w // 2, round(self.y * z) - self.view_h // 2

    def world_to_screen(self, wx, wy):
        z = self.zoom
        left, top = self.origin_px()
        return wx * z - left, wy * z - top

    def screen_to_world(self, sx, sy):
        z = self.zoom
        left, top = self.origin_px()
        return (sx + left) / z, (sy + top) / z

# ==========================================
# 5. ПРОЦЕДУРНЫЙ МИР
# ==========================================
@dataclass
class Decoration:
    kind: str        # "flower", "stone", "bush", "tuft"
    x: float         # координаты ВНУТРИ чанка
    y: float
    size: float
    color: tuple
    variant: int     # число для мелких различий внешнего вида


class WorldGenerator:
    """Данные о мире: какая тут трава и какой декор. Рисует не он, а Renderer."""

    def __init__(self, seed):
        self.seed = seed

    def grass_at(self, wx, wy):
        """Густота травы в точке мира: 0 (сухо) .. 1 (густо)."""
        n = (0.60 * value_noise(wx / 700.0, wy / 700.0, self.seed)
             + 0.28 * value_noise(wx / 220.0, wy / 220.0, self.seed + 101)
             + 0.12 * value_noise(wx / 70.0, wy / 70.0, self.seed + 202))
        # шум кучкуется около 0.5, растягиваем, чтобы были и светлые, и тёмные области
        return clamp((n - 0.5) * 2.0 + 0.5, 0.0, 1.0)

    @staticmethod
    def grass_color(g):
        return lerp_color(DRY_GRASS, LUSH_GRASS, g)

    def ground_color(self, cell_x, cell_y, cell_size=CELL_SIZE):
        """Цвет клетки земли (индексы клеток, не пиксели). cell_size больше обычного — для дальнего зума."""
        g = self.grass_at((cell_x + 0.5) * cell_size, (cell_y + 0.5) * cell_size)
        base = self.grass_color(g)
        jitter = int((hash_float(cell_x, cell_y, self.seed + 7) - 0.5) * 12)
        return tuple(clamp(c + jitter, 0, 255) for c in base)

    def chunk_decorations(self, cx, cy) -> List[Decoration]:
        """Декор одного чанка. Одинаков при каждом вызове для одних и тех же cx, cy."""
        rng = random.Random(hash_int(cx, cy, self.seed + 999))
        origin_x = cx * CHUNK_SIZE
        origin_y = cy * CHUNK_SIZE
        low, high = DECOR_MARGIN, CHUNK_SIZE - DECOR_MARGIN
        result: List[Decoration] = []

        for _ in range(DECOR_ATTEMPTS):
            x = rng.uniform(low, high)
            y = rng.uniform(low, high)
            g = self.grass_at(origin_x + x, origin_y + y)
            roll = rng.random()

            stone_p = 0.04 + 0.10 * (1.0 - g)   # на сухой земле камней больше
            flower_p = 0.30 * g * g             # цветы любят густую траву
            bush_p = 0.06 * g * g
            tuft_p = 0.30

            if roll < stone_p:
                v = rng.randint(95, 150)
                result.append(Decoration("stone", x, y, rng.uniform(5, 12),
                                         (v, v, v + 6), rng.randint(0, 99)))
            elif roll < stone_p + flower_p:
                color = rng.choice(FLOWER_COLORS)
                for _k in range(rng.randint(2, 5)):      # цветы растут группкой
                    fx = clamp(x + rng.uniform(-16, 16), low, high)
                    fy = clamp(y + rng.uniform(-16, 16), low, high)
                    result.append(Decoration("flower", fx, fy, rng.choice((3, 4)),
                                             color, rng.randint(0, 99)))
            elif roll < stone_p + flower_p + bush_p:
                s = rng.randint(0, 25)
                result.append(Decoration("bush", x, y, rng.uniform(8, 13),
                                         (28 + s, 80 + s, 38 + s), rng.randint(0, 99)))
            elif roll < stone_p + flower_p + bush_p + tuft_p:
                dark = lerp_color(self.grass_color(g), (10, 40, 15), 0.45)
                result.append(Decoration("tuft", x, y, rng.uniform(4, 7),
                                         dark, rng.randint(0, 99)))

        result.sort(key=lambda d: d.y)   # нижние рисуются поверх верхних
        return result


# ==========================================
# 6. ТАНК (состояние + логика, без отрисовки)
# ==========================================
class Tank:
    TRACK_STEP = 20.0      # шаг между траками (px эталонного мира; 20 px = 0,2 м)
    TRACK_RADIUS = 160.0   # расстояние от центра до гусеницы
    AIM_DEAD_ZONE = 100.0  # если курсор ближе к центру танка (1 м), башня не дёргается

    def __init__(self, x=0.0, y=0.0, spec=tank_config, team_color=(200, 40, 40)):
        # spec — любой объект с теми же именами (модуль tank_config или будущий класс)
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