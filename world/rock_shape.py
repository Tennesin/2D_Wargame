"""world/rock_shape.py — форма камня по параметрам редактора: размер, стабильность, сглаживание. Без pygame."""
import math

from engine import Param, TAU, clamp, lerp
from .mapdata import MAX_ROCK_R_PX

ROCK_PARAMS = {
    "rock_radius_m":  Param("Размер (радиус)", "м", 0.5, 20.0, 3.0, 0.5, 1),
    "rock_stability": Param("Стабильность",    "",  0.0, 1.0,  0.6, 0.05, 2),
    "rock_smooth":    Param("Сглаживание",     "",  0.0, 1.0,  0.5, 0.05, 2),
}

MAX_VERTS = 64               # столько вершин MapData принимает при загрузке
BASE_VERTS = (6, 12)         # число вершин до сглаживания: при сглаживании 0 и 1
MAX_SMOOTH_STEPS = 2         # сколько раз срезаем углы (Чайкин) при сглаживании 1
CHAIKIN = 0.25               # где на ребре ставим новые вершины
MAX_ROUGH = 0.25             # волнистость контура при стабильности 0
MAX_JITTER = 0.30            # случайный разброс радиусов при стабильности 0
MAX_STRETCH = 0.70           # насколько камень может вытянуться при стабильности 0
SAFE_R_K = 0.98              # запас до MAX_ROCK_R_PX (иначе сломается поиск соседей)

def _chaikin(pts):
    """Один проход срезания углов замкнутого многоугольника: вершин становится вдвое больше."""
    out = []
    n = len(pts)
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        out.append((ax + (bx - ax) * CHAIKIN, ay + (by - ay) * CHAIKIN))
        out.append((ax + (bx - ax) * (1.0 - CHAIKIN), ay + (by - ay) * (1.0 - CHAIKIN)))
    return out

def make_rock_points(rng, radius_px, stability, smoothness):
    """Вершины камня вокруг точки (0, 0), px мира. Фигура всегда «звёздчатая» относительно центра
    (углы вершин идут по возрастанию, растяжение и поворот сохраняют это свойство).
    stability 1: ровный многоугольник; чем меньше, тем больше волнистость, шум и вытянутость.
    smoothness: 0 грубые грани (6 вершин), 1 мягкий контур (много вершин и срезанные углы).
    Одно и то же зерно rng при близких параметрах даёт близкие формы: ползунки меняют камень плавно."""
    u = 1.0 - clamp(stability, 0.0, 1.0)
    m = clamp(smoothness, 0.0, 1.0)
    n = int(round(lerp(BASE_VERTS[0], BASE_VERTS[1], m)))
    steps = int(round(MAX_SMOOTH_STEPS * m))
    while steps > 0 and n * 2 ** steps > MAX_VERTS:
        steps -= 1

    rough, jitter = MAX_ROUGH * u, MAX_JITTER * u
    stretch = 1.0 + rng.uniform(0.0, MAX_STRETCH * u)
    p1, p2 = rng.uniform(0.0, TAU), rng.uniform(0.0, TAU)
    rot = rng.uniform(0.0, math.pi)

    pts = []
    for i in range(n):
        a = TAU * i / n
        k = (1.0 + rough * math.sin(2.0 * a + p1) + 0.6 * rough * math.sin(3.0 * a + p2)
             + rng.uniform(-jitter, jitter))
        k = max(0.4, k)
        pts.append((math.cos(a) * k, math.sin(a) * k))
    for _ in range(steps):
        pts = _chaikin(pts)

    cr, sr = math.cos(rot), math.sin(rot)
    out = []
    for x, y in pts:
        lx, ly = x * radius_px * stretch, y * radius_px / stretch
        out.append((lx * cr - ly * sr, lx * sr + ly * cr))

    limit = MAX_ROCK_R_PX * SAFE_R_K
    rmax = max(math.hypot(x, y) for x, y in out)
    if rmax > limit:
        s = limit / rmax
        out = [(x * s, y * s) for x, y in out]
    return [(round(x, 1), round(y, 1)) for x, y in out]