"""vehicles/chassis/hull_noses.py — скошенные носы корпуса (щучий, клин) и лобовые экраны.
Базовую раскладку берёт из hulls.py и возвращает производную с другим носом."""
import math
from dataclasses import replace

from engine import shrink_polygon
from vehicles.chassis.hulls import ArmorPlate, NOSE_FLAT, NOSE_PIKE, NOSE_WEDGE

NOSE_MIN_FRONT_MM = 250.0   # щучий нос доступен при лобовой броне СТРОГО больше этого
NOSE_ANGLE_DEG = 38.0       # угол плит к направлению «в лоб»; строго меньше 60°
NOSE_COMP = 0.5             # 0: плиты полной толщины (лоб сильнее ползунка), 1: ровно «ползунок» в лоб
NOSE_TIP_MARGIN_M = 0.05    # остриё не доходит до переднего края хитбокса на столько
PIKE_BAND_M = 0.55          # толщина «плиты носа» вдоль скатов; за ней идёт V-образный клин палубы

# --- клин: скошенный нос сверхтяжёлых машин ---
SUPERHEAVY_MASS_T = 90.0     # от этой массы скошенный нос = «клин», легче = «щучий»
WEDGE_FACE_HALF_M = 0.70     # полуширина плоской лобовой плиты по центру
WEDGE_ANGLE_DEG = 35.0       # угол боковых скосов к поперечной линии (нормаль скоса отклонена на столько от «вперёд»)
WEDGE_FACE_MARGIN_M = 0.20   # лобовая плита не доходит до переднего края хитбокса на столько
WEDGE_FACE_K = 1.0           # коэффициент толщины центральной плиты (как у плоского лба)
WEDGE_SLOPE_K = 0.92         # коэффициент толщины боковых скосов (литые, чуть тоньше)
WEDGE_ACCEL_K = 0.85         # начальный разгон: -15%
WEDGE_TURN_K = 0.90          # поворот корпуса (скорость и угловое ускорение): -10%

# ==========================================
# ЩУЧИЙ НОС
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
        y0 = max(fy, sh_y + PIKE_BAND_M)                     # подкрылок начинается там, где кончается плита носа
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

def _make_wedge(base):
    """Производная раскладка с клином: плоская лобовая плита по центру и два боковых скоса,
    плечи стоят на полной ширине корпуса (она у раскладки не больше внутреннего края гусениц).
    Сам нос тяжелее щучьего: штрафы к разгону и повороту лежат в accel_k / turn_k."""
    half_w = base.outline[2][0]
    if abs(base.outline[3][0] - half_w) > 1e-9 or abs(base.outline[-1][0] + half_w) > 1e-9:
        raise ValueError(f"{base.key}: для клина боковые грани контура должны быть вертикальными")

    f = min(WEDGE_FACE_HALF_M, 0.6 * half_w)
    face_y = -(base.coll_half_l_m - WEDGE_FACE_MARGIN_M)
    sh_y = face_y + (half_w - f) * math.tan(math.radians(WEDGE_ANGLE_DEG))   # y плеч
    face_l, face_r = (-f, face_y), (f, face_y)
    left, right = (-half_w, sh_y), (half_w, sh_y)

    outline = (face_l, face_r, right, *base.outline[3:-1], left)

    plates = (ArmorPlate.make(left, face_l, "front", WEDGE_SLOPE_K),
              ArmorPlate.make(face_l, face_r, "front", WEDGE_FACE_K),
              ArmorPlate.make(face_r, right, "front", WEDGE_SLOPE_K)) + base.plates
    hit_parts = (outline, *base.track_polys)

    ox, oy, ow, oh = base.deck_rect                          # палуба начинается сразу за плечами
    deck_y = sh_y + 0.05
    deck = (ox, deck_y, ow, oy + oh - deck_y)

    fenders = []
    for fx, fy, fw, fh in base.fender_rects:                 # у тяжёлого их нет, но код общий
        y0 = max(fy, sh_y + 0.20)
        fenders.append((fx, y0, fw, fy + fh - y0))

    quad = [left, face_l, face_r, right]                     # накладка: вписана в трапецию носа
    kit_cy = sum(y for _, y in quad) / 4.0
    kit = tuple(shrink_polygon(quad, 0.0, kit_cy, 0.80))
    bar = (-(half_w - 0.08), sh_y + 0.12, 2.0 * (half_w - 0.08), 0.20)
    wedge = ((half_w, sh_y + 0.12), (half_w, sh_y + 1.12), (half_w - 0.30, sh_y + 0.17))

    return replace(base, key=f"{base.key}+wedge", nose=NOSE_WEDGE, outline=outline,
                   hit_parts=hit_parts, plates=plates, front_plate=(left, face_l, face_r, right),
                   deck_rect=deck, fender_rects=tuple(fenders),
                   front_kit_poly=kit, front_kit_bar=bar, front_kit_wedge=wedge,
                   accel_k=WEDGE_ACCEL_K, turn_k=WEDGE_TURN_K)

_NOSE_CACHE = {}

def layout_with_nose(base, nose):
    """Раскладка с выбранным носом. Плоский нос (и уже скошенная раскладка): сама базовая."""
    if nose not in (NOSE_PIKE, NOSE_WEDGE) or base.nose != NOSE_FLAT:
        return base
    key = (base.key, nose)
    layout = _NOSE_CACHE.get(key)
    if layout is None:
        builder = _make_wedge if nose == NOSE_WEDGE else _make_pike
        layout = _NOSE_CACHE[key] = builder(base)
    return layout

def sloped_nose_for_mass(mass_t):
    """Какой скошенный нос положен машине такой массы."""
    return NOSE_WEDGE if mass_t >= SUPERHEAVY_MASS_T else NOSE_PIKE

def resolve_nose(requested, front_mm, mass_t):
    """Итоговый нос: плоский, щучий или клин. Скос доступен только при лобовой броне больше порога."""
    if requested not in (NOSE_PIKE, NOSE_WEDGE) or front_mm <= NOSE_MIN_FRONT_MM:
        return NOSE_FLAT
    return sloped_nose_for_mass(mass_t)

def nose_front_factor():
    """Во сколько раз приведённая броня щучьего носа при ударе строго в лоб
    отличается от ползунка «Лоб» (1.0 = ровно ползунок)."""
    theta = math.radians(NOSE_ANGLE_DEG)
    k = 1.0 - NOSE_COMP * (1.0 - math.cos(theta))
    return k / math.cos(theta)

def wedge_front_factor():
    """Приведённая броня боковых скосов клина при ударе строго по оси относительно ползунка «Лоб».
    Центральная плита даёт ровно 1.0."""
    return WEDGE_SLOPE_K / math.cos(math.radians(WEDGE_ANGLE_DEG))

# ==========================================
# ЛОБОВЫЕ ЭКРАНЫ
# ==========================================
SCREEN_COUNT = 4             # всего листов (на щучьем носу по два на скат)
SCREEN_COVER = 0.78          # какую долю длины лба закрывают листы
SCREEN_OFFSET_M = 0.12       # вынос листа вперёд от плиты, м
SCREEN_THICK_M = 0.07        # толщина листа на рисунке, м
SCREEN_HIT_DEPTH_M = 0.40    # насколько впереди плиты (м) точка попадания ещё считается «на лбу»
                             # (у плоского лба хитбокс чуть шире спрайта)

def _front_edges(layout):
    """Рёбра, вдоль которых стоят экраны: (a, b, сколько листов). Всего SCREEN_COUNT."""
    fp = layout.front_plate
    if layout.nose == NOSE_PIKE:
        left, tip, right = fp
        return ((left, tip, 2), (tip, right, 2))
    if layout.nose == NOSE_WEDGE:
        left, face_l, face_r, right = fp
        return ((left, face_l, 1), (face_l, face_r, 2), (face_r, right, 1))
    return ((fp[0], fp[1], SCREEN_COUNT),)

def screen_pieces(layout):
    """Листы экранов: ((a, b, (nx, ny)), ...). a и b лежат на самой плите, (nx, ny) смотрит наружу.
    На каждом ребре листы расставлены с равными просветами; по краям ребра полпросвета."""
    pieces = []
    for a, b, per_edge in _front_edges(layout):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        ux, uy = dx / length, dy / length
        nx, ny = uy, -ux
        if ny > 0.0:                                  # перед корпуса = минус y
            nx, ny = -nx, -ny
        piece = SCREEN_COVER * length / per_edge
        gap = (length - per_edge * piece) / per_edge
        pos = gap / 2.0
        for _ in range(per_edge):
            pieces.append(((a[0] + ux * pos, a[1] + uy * pos),
                           (a[0] + ux * (pos + piece), a[1] + uy * (pos + piece)),
                           (nx, ny)))
            pos += piece + gap
    return tuple(pieces)

def screen_hit(layout, u, v, tol=0.03):
    """Попала ли точка (u, v) (метры корпуса) НАПРОТИВ листа экрана: вдоль плиты в пределах листа
    и на лбу (не на гусенице и не на борту). Попадание в просвет между листами не считается."""
    for (ax, ay), (bx, by), (nx, ny) in screen_pieces(layout):
        dx, dy = bx - ax, by - ay
        t = ((u - ax) * dx + (v - ay) * dy) / (dx * dx + dy * dy)
        if not 0.0 <= t <= 1.0:
            continue
        depth = (u - ax) * nx + (v - ay) * ny          # > 0: точка впереди плиты
        if -tol <= depth <= SCREEN_HIT_DEPTH_M:
            return True
    return False