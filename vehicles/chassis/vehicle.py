"""vehicles/chassis/vehicle.py — Vehicle: шасси любой наземной техники (ядро).
Здесь поля, здоровье, оглушение, геометрия хитбокса и порядок кадра. Остальное вынесено в миксины:
  motion.py     — движение, поворот, скольжение, местность, таран;
  tracks.py     — гусеницы и внешние модули (сбитие, ремонт, анимация);
  hit_model.py  — луч снаряда, грани, плиты и приведённая броня.
Оружия и башни тут нет: подкласс переопределяет _update_weapons() и возвращает Shot или None."""
from engine import (
    obb_hits_obb, VehicleCommand, heading_vector, Team,
    TargetType, fmt_num, to_local_frame, PX_PER_M,
)
from combat import Damageable
from vehicles.chassis.hulls import NOSE_PIKE, NOSE_WEDGE, NOSE_RU
from vehicles.chassis.hit_model import HitModelMixin
from vehicles.chassis.motion import MotionMixin
from vehicles.chassis.running_gear import TrackState
from vehicles.chassis.tracks import TracksMixin

class Vehicle(MotionMixin, TracksMixin, HitModelMixin, Damageable):
    # Порядок баз важен: HitModelMixin раньше Damageable, иначе hit_result станет заглушкой.
    target_type = TargetType.VEHICLE
    renderer_key = None                         # ключ в реестре рендереров (Renderer.vehicle_renderers)
    PLAYER_TITLE = "Ваша техника"               # заголовок сводки у техники игрока; потомки переопределяют

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
        self.stun_left = 0.0            # сколько секунд осталось оглушения
        self.stun_total = 0.0           # длительность текущего оглушения (для индикатора)
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

    @property
    def stunned(self):
        return self.stun_left > 0.0

    def apply_stun(self, seconds):
        """Оглушение не складывается: новое просто заменяет старое, если оно длиннее остатка."""
        if seconds > self.stun_left:
            self.stun_left = self.stun_total = seconds

    def place_at(self, spot):
        """Поставить технику в найденную точку спавна (любой объект с x, y, angle) и обнулить движение."""
        self.x, self.y = float(spot.x), float(spot.y)
        self.hull_angle = spot.angle % 360.0
        self.speed_kmh = 0.0
        self.hull_rate = 0.0

    # ---------- геометрия хитбокса (нужна всем миксинам) ----------
    def _hull_obb(self, x, y, angle):
        """Прямоугольник корпуса: центр лежит позади оси башни."""
        s = self.spec
        fx, fy = heading_vector(angle)
        return (x - fx * s.COLLISION_SHIFT_PX, y - fy * s.COLLISION_SHIFT_PX,
                s.COLLISION_HALF_W_PX, s.COLLISION_HALF_L_PX, angle)

    def hull_obb(self):
        """Прямоугольник корпуса в формате столкновений: (x, y, half_w, half_l, angle)."""
        return self._hull_obb(self.x, self.y, self.hull_angle)

    def _to_hull_local(self, x, y):
        """Мировая точка -> метры корпуса (u вправо, v назад)."""
        cx, cy, _, _, ang = self.hull_obb()
        return to_local_frame(x, y, cx, cy, ang, self.spec.HULL_SCALE * PX_PER_M)

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

    # ---------- сводка и наведение ----------
    def describe(self):
        """(заголовок, [(название, значение), ...]) для краткой сводки. Подклассы дополняют."""
        s = self.spec
        title = self.PLAYER_TITLE if self.team is Team.PLAYER else f"Враг: {self.label}"
        nose = getattr(s, "nose", None)
        pike = nose == NOSE_PIKE
        rows = [
            ("Броня: лоб (по оси)" if pike else "Броня: лоб",
             f"{s.front:.0f}" + (f" + {s.screen_mm:.0f}" if s.screen_mm else "") + " мм"),
            ("Броня: борт", f"{s.side:.0f} + {s.gear.armor_mm:.0f} мм"),
            ("Броня: корма", f"{s.rear:.0f} мм"),
            ("Масса", f"{fmt_num(s.mass, 1)} т"),
            ("Гусеницы", self._track_status()),
        ]
        if nose in (NOSE_PIKE, NOSE_WEDGE):
            rows.insert(1, ("Нос корпуса", NOSE_RU[nose]))
        return title, rows

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
        self.repaired_track = self.tracks.update(dt)        # ремонт идёт, пока машина жива и обновляется
        throttle, steer = self._track_inputs(command.throttle, command.steer)
        braking = False
        if self.stun_left > 0.0:
            throttle = steer = 0.0
            braking = True
        delta_hull = self._rotate_hull(steer, dt, obstacles)
        distance = self._drive(throttle, steer, dt, obstacles, braking)
        self._animate_tracks(distance, delta_hull)
        shot = self._update_weapons(command, dt)
        self.stun_left = max(0.0, self.stun_left - dt)  # таймер в конце кадра: весь кадр оглушение действует
        return shot

    def _update_weapons(self, command, dt):
        """Хук для подклассов: башня, орудие, перезарядка. Возвращает Shot или None."""
        return None