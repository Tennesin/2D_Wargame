"""vehicles/hulls.py — раскладка корпуса: единый источник геометрии."""
import math
from dataclasses import dataclass, replace
from enum import Enum, auto

from engine import edge_normal_away, is_convex, shrink_polygon, clamp, lerp, round_to
from .gun_params import TURRET_FRONT_M

# ==========================================
# 0. ВАРИАНТЫ ЛБА
# ==========================================
NOSE_FLAT = "flat"
NOSE_PIKE = "pike"
NOSE_RU = {NOSE_FLAT: "плоский", NOSE_PIKE: "щучий"}

NOSE_MIN_FRONT_MM = 250.0   # щучий нос доступен при лобовой броне СТРОГО больше этого
NOSE_ANGLE_DEG = 38.0       # угол плит к направлению «в лоб»; строго меньше 60°
NOSE_COMP = 0.5             # 0: плиты полной толщины (лоб сильнее ползунка), 1: ровно «ползунок» в лоб
NOSE_TIP_MARGIN_M = 0.05    # остриё не доходит до переднего края хитбокса на столько

# ==========================================
# 1. КЛАССЫ И ПЛИТЫ
# ==========================================

class HullClass(Enum):
    LIGHT = auto()
    MEDIUM = auto()
    HEAVY = auto()

HULL_CLASS_RU = {HullClass.LIGHT: "лёгкий", HullClass.MEDIUM: "средний", HullClass.HEAVY: "тяжёлый"}
ZONES = ("front", "side", "rear")      # зоны те же, что возвращает Vehicle.zone_at

@dataclass(frozen=True)
class ArmorPlate:
    """Одна плита брони: ребро корпуса в плане."""
    a: tuple
    b: tuple
    zone: str
    k: float
    normal: tuple

    @classmethod
    def make(cls, a, b, zone, k=1.0, inside=(0.0, 0.0)):
        """Создать плиту. inside: любая точка внутри корпуса (по умолчанию его центр):
        от неё считается, куда смотрит наружная нормаль, поэтому порядок точек a, b неважен."""
        if zone not in ZONES:
            raise ValueError(f"неизвестная зона плиты: {zone!r}")
        n = edge_normal_away(a[0], a[1], b[0], b[1], inside[0], inside[1])
        return cls((float(a[0]), float(a[1])), (float(b[0]), float(b[1])), zone, float(k), n)

    @property
    def mid(self):
        return (self.a[0] + self.b[0]) / 2.0, (self.a[1] + self.b[1]) / 2.0

    @property
    def length(self):
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

def _rect(hw, hl, cx=0.0, cy=0.0):
    """Углы прямоугольника: верхний левый, верхний правый, нижний правый, нижний левый."""
    return ((cx - hw, cy - hl), (cx + hw, cy - hl), (cx + hw, cy + hl), (cx - hw, cy + hl))

def _rect_plates(hw, hl):
    """Четыре плиты прямоугольного корпуса: лоб, правый борт, корма, левый борт."""
    tl, tr, br, bl = _rect(hw, hl)
    return (ArmorPlate.make(tl, tr, "front"),
            ArmorPlate.make(tr, br, "side"),
            ArmorPlate.make(br, bl, "rear"),
            ArmorPlate.make(bl, tl, "side"))

def with_box_hitbox(base, half_w_m, half_l_m, **changes):
    """Копия раскладки с прямоугольным хитбоксом half_w_m × half_l_m: части попаданий и плиты
    брони пересчитываются от тех же чисел (единый источник). Остальные поля берутся из changes."""
    return replace(base, coll_half_w_m=half_w_m, coll_half_l_m=half_l_m,
                   hit_parts=(_rect(half_w_m, half_l_m),),
                   plates=_rect_plates(half_w_m, half_l_m), **changes)

# ==========================================
# 2. РАСКЛАДКА
# ==========================================

@dataclass(frozen=True)
class HullLayout:
    key: str
    cls: HullClass

    # --- форма корпуса и ходовая (только рисунок) ---
    outline: tuple               # выпуклый контур корпуса без гусениц
    track_x: float               # расстояние от центра до центра гусеницы
    track_w: float               # ширина гусеницы
    track_top: float             # передний край гусеницы (меньше = дальше вперёд)
    track_len: float             # длина гусеницы
    axis_fwd_m: float            # насколько ось башни впереди центра корпуса

    # --- физика и попадания ---
    coll_half_w_m: float         # полуширина прямоугольного хитбокса
    coll_half_l_m: float         # получастота хитбокса
    hit_parts: tuple             # выпуклые участки, в которые попадают снаряды (в системе корпуса)
    plates: tuple                # плиты брони (ArmorPlate)

    # --- башня и стиль ---
    ring_r_m: float              # радиус погона
    turret_style: str            # ключ стиля башни для рендерера
    hull_style: str              # ключ стиля деталей корпуса (люки, МТО и т.д.)

    # --- якоря обвеса ---
    skirt_outer_x: float         # внешний край бортового экрана
    skirt_levels: tuple          # ((y_начала, y_конца, ширина), ...) для уровней 1 и 2
    skirt_pitch_m: float         # примерная длина одной плиты экрана
    front_kit_poly: tuple        # накладная броня лба, уровень 1: многоугольник
    front_kit_bar: tuple         # уровень 2: планка (x, y, w, h)
    front_kit_wedge: tuple       # уровень 2: правый боковой клин (левый зеркальный)
    screen_x: tuple              # лобовые экраны: (x_слева, x_справа)
    screen_y: float              # лобовые экраны: y передней грани, от которой они выступают
    exhaust_xs: tuple            # выхлопные патрубки: x
    exhaust_y: float             # и y
    fender_rects: tuple          # подкрылки: ((x, y, w, h), ...) — правый и левый
    front_plate: tuple           # многоугольник лобовой плиты (светлее остального корпуса)
    deck_rect: tuple             # палуба: (x, y, w, h)

    # --- холст спрайта и масштаб ---
    canvas_half_m: float         # половина стороны квадратного холста корпуса
    scale_range: tuple = (0.8, 1.2)    # в каких пределах класс масштабируется
    scale_step: float = 0.02           # шаг квантования масштаба (0 = без квантования)

    # --- детали корпуса и башни (значения по умолчанию = средний корпус) ---
    hatch: tuple = (0.65, -1.65, 0.24)             # люк механика: x, y, радиус
    grill_rect: tuple = (-0.95, 1.0, 1.9, 1.2)     # решётка МТО: x, y, w, h
    rear_plate: tuple = (-1.15, 2.40, 2.30, 0.50)  # кормовая плита: x, y, w, h
    base_skirt: int = 0                            # постоянный бортовой экран, прибавляется к look.side
    turret_front_m: float = TURRET_FRONT_M         # где из башни выходит ствол, м вперёд от оси
    nose: str = NOSE_FLAT                          # вариант лба: NOSE_FLAT или NOSE_PIKE
    area_k: tuple = (1.0, 1.0, 1.0)                # множители площадей брони (лоб, борт, корма) к эталонным

    # ---------- проверка при создании ----------
    def __post_init__(self):
        if not is_convex(self.outline):
            raise ValueError(f"{self.key}: контур корпуса должен быть выпуклым")
        if not self.hit_parts or not all(is_convex(p) for p in self.hit_parts):
            raise ValueError(f"{self.key}: hit_parts должен быть непустым набором выпуклых многоугольников")
        if not self.plates:
            raise ValueError(f"{self.key}: нет плит брони")
        for p in self.plates:
            if p.zone not in ZONES:
                raise ValueError(f"{self.key}: неизвестная зона {p.zone!r}")
        lo, hi = self.scale_range
        if not (0.0 < lo < hi) or self.scale_step < 0.0:
            raise ValueError(f"{self.key}: неверный scale_range / scale_step")
        if self.nose not in (NOSE_FLAT, NOSE_PIKE):
            raise ValueError(f"{self.key}: неизвестный вариант носа {self.nose!r}")
        if self.sprite_reach_m() > self.canvas_half_m:
            raise ValueError(f"{self.key}: форма ({self.sprite_reach_m():.2f} м) не влезает в холст "
                             f"({self.canvas_half_m:.2f} м)")

    # ---------- производные ----------
    @property
    def coll_shift_m(self):
        """Центр корпуса лежит позади оси башни на столько же, на сколько ось впереди центра.
        Одно число вместо двух (раньше рисунок брал 0.30, а хитбокс 0.35)."""
        return self.axis_fwd_m

    @property
    def front_face_m(self):
        """Самая передняя точка корпуса по hit_parts в системе корпуса, м (перед = минус)."""
        return min(y for part in self.hit_parts for _, y in part)

    @property
    def track_rects(self):
        """Прямоугольники левой и правой гусениц: ((x0, y0, x1, y1), (x0, y0, x1, y1)), в системе корпуса."""
        hw = self.track_w / 2.0
        y0, y1 = self.track_top, self.track_top + self.track_len
        return ((-self.track_x - hw, y0, -self.track_x + hw, y1),
                (self.track_x - hw, y0, self.track_x + hw, y1))

    @property
    def track_polys(self):
        """Те же гусеницы в виде многоугольников (левая, правая)."""
        return tuple(((x0, y0), (x1, y0), (x1, y1), (x0, y1)) for x0, y0, x1, y1 in self.track_rects)

    def sprite_reach_m(self):
        """Самая дальняя точка формы от центра спрайта (оси башни), м: нужна для проверки холста."""
        pts = list(self.outline)
        for x0, y0, x1, y1 in self.track_rects:
            pts += [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        return max(max(abs(x), abs(y + self.axis_fwd_m)) for x, y in pts)

    def scale_for(self, size_k):
        """Масштаб корпуса для физического размера size_k: в пределах класса и квантованный.
        Сетка привязана к нижней границе, а обе границы возвращаются точно (без ошибок float)."""
        lo, hi = self.scale_range
        if size_k <= lo:
            return lo
        if size_k >= hi:
            return hi
        step = self.scale_step
        if step <= 0.0:
            return size_k
        n = math.floor((size_k - lo) / step + 0.5 + 1e-9)    # 1e-9: защита от 17.4999999
        return round(min(hi, lo + n * step), 4)

    def plate_by_normal(self, nx, ny):
        """Плита, чья наружная нормаль ближе всего к направлению (nx, ny) (в системе корпуса)."""
        return max(self.plates, key=lambda p: p.normal[0] * nx + p.normal[1] * ny)

# ==========================================
# 3. КОРПУС
# ==========================================

_MED_HW, _MED_HL = 1.95, 3.15

LIGHT_LAYOUT = HullLayout(
    key="light", cls=HullClass.LIGHT,
    outline=((-1.00, -2.80), (1.00, -2.80), (1.25, -2.15), (1.25, 1.90),
             (1.00, 3.05), (-1.00, 3.05), (-1.25, 1.90), (-1.25, -2.15)),
    track_x=1.45, track_w=0.64, track_top=-3.15, track_len=6.3,
    axis_fwd_m=0.0,                                   # башня по центру
    coll_half_w_m=1.77, coll_half_l_m=3.15,
    hit_parts=(_rect(1.25, 2.925, 0.0, 0.125),        # корпус: y от -2.80 до 3.05
               _rect(0.32, 3.15, -1.45, 0.0),         # левая гусеница
               _rect(0.32, 3.15, 1.45, 0.0)),         # правая гусеница
    plates=_rect_plates(1.77, 3.15),
    ring_r_m=0.9, turret_style="oval", hull_style="classic",
    skirt_outer_x=1.80,
    skirt_levels=((-2.2, 2.6, 0.36), (-2.9, 3.0, 0.46)),
    skirt_pitch_m=1.1,
    front_kit_poly=((-0.85, -2.72), (0.85, -2.72), (1.15, -2.20), (-1.15, -2.20)),
    front_kit_bar=(-1.20, -2.12, 2.40, 0.18),
    front_kit_wedge=((1.25, -2.10), (1.25, -1.35), (1.00, -2.06)),
    screen_x=(-0.90, 0.90), screen_y=-2.82,
    exhaust_xs=(-0.65, 0.65), exhaust_y=2.90,
    fender_rects=((1.25, -2.1, 0.20, 4.8), (-1.45, -2.1, 0.20, 4.8)),
    front_plate=((-1.00, -2.80), (1.00, -2.80), (1.25, -2.15), (-1.25, -2.15)),
    deck_rect=(-1.10, -2.10, 2.20, 4.40),
    canvas_half_m=3.7,
    scale_range=(0.80, 0.92), scale_step=0.02,
    hatch=(0.55, -1.70, 0.20),
    grill_rect=(-0.80, 1.15, 1.60, 1.20),
    rear_plate=(-1.00, 2.45, 2.00, 0.60),
    turret_front_m=1.35,
    area_k=(0.80, 0.88, 0.80),
)

MEDIUM_LAYOUT = HullLayout(
    key="medium", cls=HullClass.MEDIUM,
    outline=((-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (1.35, 2.65),
             (1.15, 2.9), (-1.15, 2.9), (-1.35, 2.65), (-1.35, -2.1)),
    track_x=1.6, track_w=0.75, track_top=-3.1, track_len=6.3,
    axis_fwd_m=0.3,
    coll_half_w_m=_MED_HW, coll_half_l_m=_MED_HL,
    hit_parts=(_rect(_MED_HW, _MED_HL),),
    plates=_rect_plates(_MED_HW, _MED_HL),
    ring_r_m=1.35, turret_style="hex", hull_style="classic",
    skirt_outer_x=1.95,
    skirt_levels=((-2.2, 2.4, 0.42), (-2.9, 3.0, 0.50)),
    skirt_pitch_m=1.15,
    front_kit_poly=((-0.85, -2.82), (0.85, -2.82), (1.18, -2.15), (-1.18, -2.15)),
    front_kit_bar=(-1.2, -2.08, 2.4, 0.20),
    front_kit_wedge=((1.35, -2.10), (1.35, -1.20), (1.05, -2.05)),
    screen_x=(-1.0, 1.0), screen_y=-2.92,
    exhaust_xs=(-0.7, 0.7), exhaust_y=2.65,
    fender_rects=((1.35, -2.1, 0.22, 4.75), (-1.57, -2.1, 0.22, 4.75)),
    front_plate=((-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (-1.35, -2.1)),
    deck_rect=(-1.25, -2.05, 2.50, 4.40),
    canvas_half_m=3.7,
    scale_range=(0.88, 1.06), scale_step=0.02,
)

# Тяжёлый: широкий (4.4 x 6.0, отношение 1.36), сплошные бортовые экраны, башня сдвинута вперёд
HEAVY_LAYOUT = HullLayout(
    key="heavy", cls=HullClass.HEAVY,
    outline=((-1.55, -2.75), (1.55, -2.75), (1.75, -2.20), (1.75, 2.65),
             (1.60, 2.90), (-1.60, 2.90), (-1.75, 2.65), (-1.75, -2.20)),
    track_x=1.8, track_w=0.80, track_top=-3.15, track_len=6.3,
    axis_fwd_m=0.3,
    coll_half_w_m=2.18, coll_half_l_m=3.15,
    hit_parts=(_rect(1.75, 2.825, 0.0, 0.075),
               _rect(0.40, 3.15, -1.8, 0.0),
               _rect(0.40, 3.15, 1.8, 0.0)),
    plates=_rect_plates(2.18, 3.15),
    ring_r_m=1.40, turret_style="hex", hull_style="classic",
    skirt_outer_x=2.2,
    skirt_levels=((-2.4, 2.6, 0.55), (-2.95, 2.95, 0.65)),
    skirt_pitch_m=1.3,
    front_kit_poly=((-1.35, -2.67), (1.35, -2.67), (1.65, -2.25), (-1.65, -2.25)),
    front_kit_bar=(-1.7, -2.17, 3.4, 0.22),
    front_kit_wedge=((1.75, -2.20), (1.75, -1.30), (1.45, -2.15)),
    screen_x=(-1.3, 1.3), screen_y=-2.77,
    exhaust_xs=(-1.1, 1.1), exhaust_y=2.75,
    fender_rects=((1.75, -2.2, 0.30, 4.85), (-2.05, -2.2, 0.30, 4.85)),
    front_plate=((-1.55, -2.75), (1.55, -2.75), (1.75, -2.20), (-1.75, -2.20)),
    deck_rect=(-1.55, -2.15, 3.1, 4.5),
    canvas_half_m=3.7,
    scale_range=(1.00, 1.12), scale_step=0.02,
    hatch=(1.20, -2.00, 0.24),
    grill_rect=(-1.10, 1.40, 2.20, 1.00),
    rear_plate=(-1.50, 2.40, 3.00, 0.50),
    base_skirt=1,
    turret_front_m=1.85,
    area_k=(1.20, 1.05, 1.20),
)

# ==========================================
# 4. ТАБЛИЦА
# ==========================================

LAYOUTS = {HullClass.LIGHT: LIGHT_LAYOUT,
           HullClass.MEDIUM: MEDIUM_LAYOUT,
           HullClass.HEAVY: HEAVY_LAYOUT}

def layout_for(cls):
    """Раскладка класса. Пока готов только средний корпус: остальные классы временно получают его же."""
    return LAYOUTS.get(cls, MEDIUM_LAYOUT)

def max_canvas_half_m():
    """Наибольший холст среди раскладок: один размер заготовки на весь рендерер (этап 4)."""
    return max(layout.canvas_half_m for layout in LAYOUTS.values())

# ==========================================
# 4а. ЩУЧИЙ НОС
# ==========================================

def _make_pike(base):
    """Производная раскладка со щучьим носом. Нос заменяет переднюю плиту: остриё у переднего
    края хитбокса класса, плечи на полной ширине корпуса. Угол плит один для всех классов."""
    half_w = base.outline[2][0]
    if abs(base.outline[3][0] - half_w) > 1e-9 or abs(base.outline[-1][0] + half_w) > 1e-9:
        raise ValueError(f"{base.key}: для щучьего носа боковые грани контура должны быть вертикальными")

    theta = math.radians(NOSE_ANGLE_DEG)
    tip_y = -(base.coll_half_l_m - NOSE_TIP_MARGIN_M)
    sh_y = tip_y + half_w * math.tan(theta)                  # y плеч
    tip, left, right = (0.0, tip_y), (-half_w, sh_y), (half_w, sh_y)

    outline = (tip, right, *base.outline[3:-1], left)        # передние углы заменены остриём

    k = 1.0 - NOSE_COMP * (1.0 - math.cos(theta))
    plates = (ArmorPlate.make(left, tip, "front", k),
              ArmorPlate.make(tip, right, "front", k)) + base.plates
    # прежняя плоская плита остаётся в списке: по ней считаются удары в передние концы гусениц

    hit_parts = (outline, *base.track_polys)                 # корпус по контуру + две гусеницы

    ox, oy, ow, oh = base.deck_rect                          # палуба начинается сразу за плечами
    deck_y = sh_y + 0.05
    deck = (ox, deck_y, ow, oy + oh - deck_y)

    fenders = []                                             # подкрылки не должны висеть перед плечами
    for fx, fy, fw, fh in base.fender_rects:
        y0 = max(fy, sh_y)
        fenders.append((fx, y0, fw, fy + fh - y0))

    centroid_y = (tip_y + 2.0 * sh_y) / 3.0                  # накладная броня: вписана в треугольник
    kit = tuple(shrink_polygon([left, tip, right], 0.0, centroid_y, 0.78))
    bar_y = sh_y - 0.20
    bar_hw = half_w * (bar_y - tip_y) / (sh_y - tip_y) - 0.06
    bar = (-bar_hw, bar_y, 2.0 * bar_hw, 0.20)

    return replace(base, key=f"{base.key}+pike", nose=NOSE_PIKE, outline=outline,
                   hit_parts=hit_parts, plates=plates, front_plate=(left, tip, right),
                   deck_rect=deck, fender_rects=tuple(fenders),
                   front_kit_poly=kit, front_kit_bar=bar)

_NOSE_CACHE = {}

def layout_with_nose(base, nose):
    """Раскладка с выбранным носом. Плоский нос: сама базовая раскладка."""
    if nose != NOSE_PIKE or base.nose == NOSE_PIKE:
        return base
    layout = _NOSE_CACHE.get(base.key)
    if layout is None:
        layout = _NOSE_CACHE[base.key] = _make_pike(base)
    return layout

def nose_front_factor():
    """Во сколько раз приведённая броня щучьего носа при ударе строго в лоб
    отличается от ползунка «Лоб» (1.0 = ровно ползунок)."""
    theta = math.radians(NOSE_ANGLE_DEG)
    k = 1.0 - NOSE_COMP * (1.0 - math.cos(theta))
    return k / math.cos(theta)

# ==========================================
# 5. КЛАССИФИКАЦИЯ ПО ПОЛЗУНКАМ
# ==========================================
CLASS_W_ARMOR = 1.0
CLASS_W_POWER = 0.5
CLASS_LIGHT_BELOW = -0.20      # индекс ниже этого: лёгкий
CLASS_HEAVY_ABOVE = 0.15       # выше этого: тяжёлый (стартовые значения, подгоняются по отладке)
CLASS_BORDER_EPS = 0.03        # «рядом с порогом»: ещё чуть-чуть, и силуэт сменится

def near_class_border(index):
    """Индекс в пределах CLASS_BORDER_EPS от порога смены класса."""
    return min(abs(index - CLASS_LIGHT_BELOW), abs(index - CLASS_HEAVY_ABOVE)) <= CLASS_BORDER_EPS

def class_index(armor_t, power_t):
    """Индекс «тяжести»: много брони и мало мощности = больше."""
    return CLASS_W_ARMOR * armor_t - CLASS_W_POWER * power_t

def class_for_index(index):
    if index < CLASS_LIGHT_BELOW:
        return HullClass.LIGHT
    if index > CLASS_HEAVY_ABOVE:
        return HullClass.HEAVY
    return HullClass.MEDIUM

def classify(armor_t, power_t):
    """Класс корпуса по нормированным броне и мощности (обе 0..1)."""
    return class_for_index(class_index(armor_t, power_t))

# ==========================================
# 6. ПОЛОЖЕНИЕ БАШНИ ПО ТЯЖЕСТИ КОРПУСА
# ==========================================
TURRET_AXIS_FRONT_M = 0.3      # ось башни у эталона (минус = позади центра корпуса)
TURRET_AXIS_REAR_M = -0.5      # самое заднее положение
TURRET_SHIFT_FROM = -0.05      # индекс, с которого башня начинает уезжать назад (эталон ≈ -0.09 стоит на месте)
TURRET_SHIFT_TO = 0.45         # индекс, на котором башня уже в крайнем заднем положении
TURRET_AXIS_STEP_M = 0.1       # квантование: ограничивает число вариантов спрайта

def turret_axis_for(cls, index):
    """Ось башни вдоль корпуса, м (плюс = впереди центра корпуса). Чем тяжелее индекс, тем дальше назад.
    У лёгкого корпуса башня всегда по центру."""
    if cls is HullClass.LIGHT:
        return LIGHT_LAYOUT.axis_fwd_m
    t = clamp((index - TURRET_SHIFT_FROM) / (TURRET_SHIFT_TO - TURRET_SHIFT_FROM), 0.0, 1.0)
    axis = round_to(lerp(TURRET_AXIS_FRONT_M, TURRET_AXIS_REAR_M, t), TURRET_AXIS_STEP_M)
    return round(axis, 3) + 0.0                      # + 0.0 убирает «-0.0»

_AXIS_CACHE = {}

def layout_with_axis(base, axis_fwd_m):
    """Раскладка с другим положением оси башни. Форма корпуса, гусеницы и плиты те же.
    Применять ДО layout_with_nose: ключ нового варианта включает ось."""
    if abs(base.axis_fwd_m - axis_fwd_m) < 1e-9:
        return base
    key = (base.key, axis_fwd_m)
    layout = _AXIS_CACHE.get(key)
    if layout is None:
        layout = _AXIS_CACHE[key] = replace(base, key=f"{base.key}@{axis_fwd_m:+.1f}",
                                            axis_fwd_m=axis_fwd_m)
    return layout