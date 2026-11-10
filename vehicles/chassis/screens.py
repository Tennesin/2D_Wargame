"""vehicles/chassis/screens.py — экраны корпуса как геометрия: кромки крепления, лист-отрезок, луч снаряда
через листы, масса и эквивалентная броня. Без pygame и без Part: правила размещения в vehicles/parts/screens.py."""
import math
from typing import NamedTuple

from vehicles.chassis.hull_noses import front_edges
from vehicles.chassis.params import (
    SCREEN_END_MARGIN_M, SCREEN_FRONT_ONE, SCREEN_FRONT_SUM, SCREEN_SIDE_ONE, SCREEN_SIDE_SUM,
    SCREEN_HEIGHT_M, SCREEN_MASS_K, STEEL_T_PER_M3,
)

class MountEdge(NamedTuple):
    key: str          # "front0".., "side_l", "side_r", у башни "t0"..
    face: str         # "front" | "side" | "turret"
    a: tuple          # начало кромки, метры корпуса
    b: tuple
    n: tuple          # наружная нормаль

    @property
    def length(self):
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

class Screen(NamedTuple):
    """Лист, действующий в игре. Координаты в метрах корпуса."""
    a: tuple
    b: tuple
    n: tuple
    mm: float
    face: str

    @property
    def length(self):
        return math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])

_EDGES = {}

def mount_edges(layout):
    """Кромки, на которые можно ставить экраны: лобовые рёбра носа и внешние грани гусениц. Кормы нет."""
    edges = _EDGES.get(layout.key)
    if edges is None:
        edges = _EDGES[layout.key] = tuple(_make_edges(layout))
    return edges

def _make_edges(layout):
    out = []
    for i, (a, b, _) in enumerate(front_edges(layout)):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        nx, ny = dy / ln, -dx / ln
        if ny > 0.0:                                   # перёд корпуса = минус y
            nx, ny = -nx, -ny
        out.append(MountEdge(f"front{i}", "front", a, b, (nx, ny)))
    r = layout.track_x + layout.track_w / 2.0
    y0 = layout.track_top + SCREEN_END_MARGIN_M
    y1 = layout.track_top + layout.track_len - SCREEN_END_MARGIN_M
    out.append(MountEdge("side_l", "side", (-r, y0), (-r, y1), (-1.0, 0.0)))
    out.append(MountEdge("side_r", "side", (r, y0), (r, y1), (1.0, 0.0)))
    return out

def limits(edge):
    """(доля для одного листа, доля для всех листов) группы кромки."""
    if edge.face == "front":
        return SCREEN_FRONT_ONE, SCREEN_FRONT_SUM
    return SCREEN_SIDE_ONE, SCREEN_SIDE_SUM

def group_of(edge):
    """Лоб считается одной группой (все его рёбра), каждый борт отдельной."""
    return "front" if edge.face == "front" else edge.key

def group_length(edges, edge):
    g = group_of(edge)
    return sum(e.length for e in edges if group_of(e) == g)

def ray_crossings(screens, ox, oy, dx, dy, back, fwd):
    """Листы, которые пересекает луч O + t·d, t в [-back, fwd] (d единичный, метры корпуса).
    [(t, лист, cos угла к нормали)] по возрастанию t."""
    out = []
    for s in screens:
        ex, ey = s.b[0] - s.a[0], s.b[1] - s.a[1]
        den = dx * ey - dy * ex
        if abs(den) < 1e-9:
            continue
        ax, ay = s.a[0] - ox, s.a[1] - oy
        t = (ax * ey - ay * ex) / den
        u = (ax * dy - ay * dx) / den
        if -back <= t <= fwd and 0.0 <= u <= 1.0:
            out.append((t, s, abs(dx * s.n[0] + dy * s.n[1])))
    out.sort(key=lambda r: r[0])
    return out

def screen_mass_t(screens):
    """Масса листов при size_k = 1: длина × толщина × условная высота × плотность стали × коэффициент сетки."""
    return sum(s.length * s.mm / 1000.0 * SCREEN_HEIGHT_M * STEEL_T_PER_M3 * SCREEN_MASS_K for s in screens)

def equivalent_armor(layout, screens):
    """(добавка ко лбу, добавка к борту), мм: средняя толщина листов по длине кромок. Нужна цене."""
    edges = mount_edges(layout)
    lf = sum(e.length for e in edges if e.face == "front")
    ls = sum(e.length for e in edges if e.face == "side")
    f = sum(s.length * s.mm for s in screens if s.face == "front") / lf if lf else 0.0
    d = sum(s.length * s.mm for s in screens if s.face == "side") / ls if ls else 0.0
    return f, d