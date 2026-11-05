"""vehicles/chassis/vehicle.py — Vehicle: шасси любой наземной техники (ядро).
Здесь поля, здоровье, оглушение, геометрия хитбокса и порядок кадра. Остальное вынесено в миксины:
  motion.py     — движение, поворот, скольжение, местность, таран;
  tracks.py     — гусеницы и внешние модули (сбитие, ремонт, анимация);
  hit_model.py  — луч снаряда, грани, плиты и приведённая броня.
Оружия и башни тут нет: подкласс переопределяет _update_weapons() и возвращает Shot или None."""
import math

from engine import (
    obb_hits_obb, VehicleCommand, heading_vector, Team, AmmoKind,
    TargetType, fmt_num, to_local_frame, PX_PER_M, clamp
)
from vehicles.mods import NO_MODS
from combat import Damageable
from vehicles.chassis.hulls import NOSE_PIKE, NOSE_WEDGE, NOSE_RU
from vehicles.chassis.hit_model import HitModelMixin
from vehicles.chassis.motion import MotionMixin
from vehicles.chassis.running_gear import TrackState
from vehicles.chassis.tracks import TracksMixin
from vehicles.chassis.params import RAM_MASS_RANGE_T, KMH_TO_PX
from vehicles.chassis.shock import ShockMixin

class Vehicle(MotionMixin, TracksMixin, HitModelMixin, ShockMixin, Damageable):
    # Порядок баз важен: HitModelMixin раньше Damageable, иначе hit_result станет заглушкой.
    target_type = TargetType.VEHICLE
    kind = None
    PLAYER_TITLE = "Ваша техника"               # заголовок сводки у техники игрока; потомки переопределяют

    def __init__(self, x=0.0, y=0.0, *, spec, team_color=(200, 40, 40),
                 team=Team.PLAYER, label="техника", emblem="", arch_key=None):
        self.spec = spec
        self.team_color = team_color
        self.team = team
        self.label = label              # название архетипа для сводки
        self.arch_key = arch_key        # ключ архетипа
        self.emblem = emblem
        self.x = float(x)
        self.y = float(y)
        self.hp = float(spec.hp)        # текущее здоровье (максимум задаёт spec.hp)
        self.hull_angle = 0.0           # 0 = вверх, по часовой стрелке
        self.hull_rate = 0.0            # текущая угловая скорость корпуса, °/с (+ = по часовой)
        self.left_track_offset = 0.0
        self.right_track_offset = 0.0
        self.speed_kmh = 0.0            # текущая скорость вдоль корпуса, км/ч (минус = назад)
        self.lift_dir = None            # направление на точку удара в системе корпуса (для наклона при подбросе)
        self.contact_push = None        # боковой толчок, с которым упёрлись в этом кадре (видит солвер тарана)
        self.contact_spin = None        # вращение корпуса (°/с), с которым упёрлись в этом кадре
        self.press_s = 0.0              # пока > 0, солвер «ведёт» скорость (давление)
        self.last_throttle = 0.0        # газ после учёта оглушения (нужен давлению)
        self.terrain_k = 1.0            # множитель скорости от местности под корпусом
        self.terrain_kind = None        # вид вязкой местности под корпусом (TerrainKind) или None: трава
        self._terrain = None            # карта препятствий; её передаёт GameContext в update()
        self._patches = ()              # пятна карты рядом с техникой; обновляется в начале update()
        self.impact_kmh = None          # скорость в момент удара в ЭТОМ кадре (None: удара не было)
        self.push_vx = 0.0              # скорость, полученная от тарана, px/с мира
        self.push_vy = 0.0
        self._pending = []              # невыданные изменения скорости: [[dvx, dvy, секунд осталось], ...] px/с
        self._soft_contact_s = 0.0      # пока > 0, удар о препятствие не гасит скорость (партнёр ещё разгоняется)
        self.tracks = TrackState()      # сбитые гусеницы и ремонт
        self.stun_left = 0.0            # сколько секунд осталось оглушения
        self.lift_left = 0.0            # сколько секунд осталось подброса
        self.lift_total = 0.0           # длительность текущего подброса (для индикатора и кривой)
        self.lift_amp = 0.0             # высота подъёма 0..1
        self.stun_total = 0.0           # длительность текущего оглушения (для индикатора)
        self.repaired_track = None      # сторона гусеницы, которую починили в ЭТОМ кадре (для сообщений)
        self.mods = NO_MODS             # улучшения (у ботов всегда пустые)

    # ---------- параметры ----------
    @property
    def max_hp(self):
        return self.spec.hp

    @property
    def mass_t(self):
        """Масса, т (для тарана: тот же интерфейс, что у Wall.mass_t и Patch.mass_t)."""
        return self.spec.mass

    @property
    def mass_k(self):
        """Где масса машины между "лёгкой" и "тяжёлой": 0..1 (для реакции на удар)."""
        lo, hi = RAM_MASS_RANGE_T
        return clamp((self.mass_t - lo) / (hi - lo), 0.0, 1.0)

    @property
    def inertia_t_m2(self):
        """Момент инерции корпуса, т·м² (для тарана: тот же интерфейс, что у mass_t)."""
        return self.spec.inertia

    @property
    def has_impact(self):
        """Тело в этом кадре упёрлось во что-то: ездой, толчком или поворотом."""
        return (self.impact_kmh is not None or self.contact_push is not None
                or self.contact_spin is not None)

    @property
    def alive(self):
        return self.hp > 0.0

    def set_spec(self, spec):
        """Новая спецификация (ползунки конструктора). Доля здоровья сохраняется."""
        frac = self.hp / self.spec.hp if self.spec.hp > 0 else 1.0
        self.spec = spec
        self.hp = spec.hp * max(0.0, min(1.0, frac))
        self.spec.set_power_boost(self.mods.power_k)

    def set_mods(self, mods):
        """Применить набор улучшений (StatMods). Двигатель пересчитывает сама спецификация."""
        self.mods = mods
        self.spec.set_power_boost(mods.power_k)

    def heal(self, amount):
        """Восстановить здоровье, не выше максимума. Возвращает, сколько реально восстановлено."""
        if amount <= 0.0 or not self.alive:
            return 0.0
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def incoming_k(self, kind):
        """Множитель входящего урона от снаряда типа kind. Сопротивление действует только на ФГ и HESH."""
        if kind is AmmoKind.HE or kind is AmmoKind.HESH:
            return self.mods.blast_taken_k
        return 1.0

    @property
    def stunned(self):
        return self.stun_left > 0.0

    def apply_stun(self, seconds):
        """Оглушение не складывается: новое просто заменяет старое, если оно длиннее остатка."""
        seconds *= self.mods.blast_taken_k
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
            ("Броня: борт", f"{s.side:.0f} + {s.track_mm:.0f} мм"),
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
        """obstacles — повёрнутые прямоугольники стен и чужой техники."""
        self.impact_kmh = None          # флаги удара живут ровно один кадр
        self.contact_push = None
        self.contact_spin = None
        self._terrain = terrain
        self._patches = terrain.patches_near(self.x, self.y, self.reach_px()) if terrain is not None else ()
        self._sample_terrain()
        self.repaired_track = self.tracks.update(dt)        # ремонт идёт, пока машина жива и обновляется
        throttle, steer = self._track_inputs(command.throttle, command.steer)
        braking = False
        if self.stun_left > 0.0:
            throttle = steer = 0.0
            braking = True
        self.last_throttle = throttle
        delta_hull = self._rotate_hull(steer, dt, obstacles)
        distance = self._drive(throttle, steer, dt, obstacles, braking)
        if self.press_s > 0.0 and abs(throttle) > 0.0:      # упёрлись и давим: гусеницы пробуксовывают
            slip = abs(throttle) * 0.5 * self.spec.v_avg * KMH_TO_PX * dt
            if abs(distance) < slip:
                distance = math.copysign(slip, throttle)
        self._animate_tracks(distance, delta_hull)
        shot = self._update_weapons(command, dt)
        self.stun_left = max(0.0, self.stun_left - dt)
        self._soft_contact_s = max(0.0, self._soft_contact_s - dt)
        self.press_s = max(0.0, self.press_s - dt)
        self.lift_left = max(0.0, self.lift_left - dt)
        return shot

    def _update_weapons(self, command, dt):
        """Хук для подклассов: башня, орудие, перезарядка. Возвращает Shot или None."""
        return None