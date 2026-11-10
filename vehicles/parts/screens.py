"""vehicles/parts/screens.py — экраны как детали."""
import math
from types import SimpleNamespace

from engine import clamp, edge_normal_away
from vehicles.chassis.hull_noses import screen_pieces
from vehicles.chassis.params import (
    FRONT_SCREEN, SCREEN_GAP_M, SCREEN_GAP_TOL_M, SCREEN_ANGLE_TOL_DEG, SCREEN_EDGE_EPS_M,
    SCREEN_LEN_MIN_M, SCREEN_LEN_MAX_M, SCREEN_LEN_DEFAULT_M, SCREEN_SNAP_M, SCREEN_MM_MIN,
)
from vehicles.chassis.screens import (
    MountEdge, Screen, mount_edges, limits, group_of, group_length,
)
from .model import Part, SURFACE_HULL, SURFACE_TURRET
from .shapes import turret_outline

SHEET_KINDS = ("screen", "turret_screen")
_EPS = SCREEN_EDGE_EPS_M

def _unit(e):
    ln = e.length
    return (e.b[0] - e.a[0]) / ln, (e.b[1] - e.a[1]) / ln, ln

def normal_of(p):
    r = math.radians(p.angle)
    return math.sin(r), -math.cos(r)

def effective_mm(p, global_mm):
    """Своя толщина главнее общей. Общая шкала 0: берём минимум."""
    base = p.mm if p.mm is not None else max(global_mm, SCREEN_MM_MIN)
    return clamp(base, SCREEN_MM_MIN, FRONT_SCREEN.max)

# ---------- построение и поиск ----------
def make_sheet(kind, edge, s, w, mm=None):
    """Лист длиной w, центр на расстоянии s от начала кромки."""
    ux, uy, _ = _unit(edge)
    cx = edge.a[0] + ux * s + edge.n[0] * SCREEN_GAP_M
    cy = edge.a[1] + uy * s + edge.n[1] * SCREEN_GAP_M
    angle = math.degrees(math.atan2(edge.n[0], -edge.n[1])) % 360.0
    surface = SURFACE_TURRET if kind == "turret_screen" else SURFACE_HULL
    return Part(kind, x=round(cx, 4), y=round(cy, 4), w=round(w, 4),
                angle=round(angle, 3), surface=surface, mm=mm)

def locate(edges, p):
    """(кромка, s0, s1) для листа p или None: лист должен стоять на зазоре от кромки, параллельно ей и целиком на ней."""
    nx, ny = normal_of(p)
    cos_tol = math.cos(math.radians(SCREEN_ANGLE_TOL_DEG))
    for e in edges:
        if nx * e.n[0] + ny * e.n[1] < cos_tol:
            continue
        ux, uy, ln = _unit(e)
        dx, dy = p.x - e.a[0], p.y - e.a[1]
        if abs(dx * e.n[0] + dy * e.n[1] - SCREEN_GAP_M) > SCREEN_GAP_TOL_M:
            continue
        s = dx * ux + dy * uy
        s0, s1 = s - p.w / 2.0, s + p.w / 2.0
        if s0 < -_EPS or s1 > ln + _EPS:
            continue
        return e, s0, s1
    return None

def snap(edges, kind, u, v, w, mm=None, cap_of=None):
    """Лист у ближайшей к точке (u, v) кромки. None: кромок рядом нет."""
    best = None
    for e in edges:
        ux, uy, ln = _unit(e)
        t = clamp((u - e.a[0]) * ux + (v - e.a[1]) * uy, 0.0, ln)
        d = math.hypot(u - (e.a[0] + ux * t), v - (e.a[1] + uy * t))
        if d <= SCREEN_SNAP_M and (best is None or d < best[0]):
            best = (d, e, t, ln)
    if best is None:
        return None
    _, e, t, ln = best
    w = min(w, ln, cap_of(e) if cap_of else w)
    return make_sheet(kind, e, clamp(t, w / 2.0, ln - w / 2.0), w, mm)

def snap_hull(layout, u, v, w=SCREEN_LEN_DEFAULT_M, mm=None):
    edges = mount_edges(layout)
    return snap(edges, "screen", u, v, w, mm, lambda e: limits(e)[0] * group_length(edges, e))

def snap_turret(style, u, v, w=SCREEN_LEN_DEFAULT_M):
    return snap(turret_edges(style), "turret_screen", u, v, w)

# ---------- охват и допустимость (корпус) ----------
def accept(layout, parts):
    """Листы, прошедшие правила, по порядку списка: [(Part, кромка, s0, s1)]. Не на кромке, короче минимума,
    длиннее доли одного листа, сверх суммарного охвата или поверх другого листа: пропускаются."""
    edges = mount_edges(layout)
    used, spans, out = {}, {}, []
    for p in parts:
        loc = locate(edges, p)
        if loc is None:
            continue
        e, s0, s1 = loc
        w = s1 - s0
        one, total = limits(e)
        g, L = group_of(e), group_length(edges, e)
        if w < SCREEN_LEN_MIN_M - _EPS or w > one * L + _EPS:
            continue
        if used.get(g, 0.0) + w > total * L + _EPS:
            continue
        if any(s0 < b - _EPS and s1 > a + _EPS for a, b in spans.get(e.key, ())):
            continue
        used[g] = used.get(g, 0.0) + w
        spans.setdefault(e.key, []).append((s0, s1))
        out.append((p, e, s0, s1))
    return out

def coverage(layout, parts):
    """{"front"|"side_l"|"side_r": (занято, длина группы)}, метры."""
    edges = mount_edges(layout)
    used = {}
    for _, e, s0, s1 in accept(layout, parts):
        used[group_of(e)] = used.get(group_of(e), 0.0) + (s1 - s0)
    out = {}
    for e in edges:
        g = group_of(e)
        if g not in out:
            out[g] = (used.get(g, 0.0), group_length(edges, e))
    return out

def max_length(layout, others, p):
    """Наибольшая длина листа p при остальных листах others (центр листа остаётся на месте)."""
    edges = mount_edges(layout)
    loc = locate(edges, p)
    if loc is None:
        return p.w
    e, s0, s1 = loc
    c, ln = (s0 + s1) / 2.0, e.length
    one, total = limits(e)
    L = group_length(edges, e)
    half, used = min(c, ln - c), 0.0
    for _, qe, q0, q1 in accept(layout, others):
        if group_of(qe) == group_of(e):
            used += q1 - q0
        if qe.key == e.key:
            if q0 >= c:
                half = min(half, q0 - c)
            elif q1 <= c:
                half = min(half, c - q1)
    return max(0.0, min(2.0 * half, one * L, total * L - used, SCREEN_LEN_MAX_M))

# ---------- авто-набор и итог для физики ----------
def auto_screen_parts(layout, global_mm):
    """Авто-набор: те же листы, что раньше рисовал _draw_front_screen. Шкала 0: листов нет."""
    if global_mm <= 0.0:
        return []
    out = []
    for (ax, ay), (bx, by), (nx, ny) in screen_pieces(layout):
        angle = math.degrees(math.atan2(nx, -ny)) % 360.0
        out.append(Part("screen", x=round((ax + bx) / 2.0 + nx * SCREEN_GAP_M, 4),
                        y=round((ay + by) / 2.0 + ny * SCREEN_GAP_M, 4),
                        w=round(math.hypot(bx - ax, by - ay), 4), angle=round(angle, 3),
                        surface=SURFACE_HULL))
    return out

def screens_of(layout, design, global_mm):
    """Листы, действующие в игре: из авто-набора или из ручного списка корпуса. Единственный источник
    и для рисунка (resolve), и для физики, массы, цены."""
    from .design import resolve                # design импортирует этот модуль
    if design.hull is None:
        parts = auto_screen_parts(layout, global_mm)
    else:
        parts = [p for p in resolve(design.hull, SimpleNamespace(layout=layout), SURFACE_HULL)
                 if p.kind == "screen"]
    out = []
    for p, e, _, _ in accept(layout, parts):
        r = math.radians(p.angle)
        ux, uy = math.cos(r), math.sin(r)
        half = p.w / 2.0
        out.append(Screen((p.x - ux * half, p.y - uy * half), (p.x + ux * half, p.y + uy * half),
                          (math.sin(r), -math.cos(r)), effective_mm(p, global_mm), e.face))
    return tuple(out)

# ---------- башня (только картинка) ----------
_TURRET = {}

def turret_edges(style):
    """Кромки по контуру башни без кормовых (нормаль смотрит назад) и без коротышей."""
    edges = _TURRET.get(style)
    if edges is None:
        pts = turret_outline(style)
        out = []
        for i, a in enumerate(pts):
            b = pts[(i + 1) % len(pts)]
            nx, ny = edge_normal_away(a[0], a[1], b[0], b[1], 0.0, 0.0)
            if ny > 0.5 or math.hypot(b[0] - a[0], b[1] - a[1]) < SCREEN_LEN_MIN_M:
                continue
            out.append(MountEdge(f"t{i}", "turret", a, b, (nx, ny)))
        edges = _TURRET[style] = tuple(out)
    return edges

def turret_free(style, others, p):
    """Лист башни на кромке и не поверх другого листа."""
    edges = turret_edges(style)
    loc = locate(edges, p)
    if loc is None:
        return False
    e, s0, s1 = loc
    for q in others:
        l2 = locate(edges, q)
        if l2 and l2[0].key == e.key and s0 < l2[2] - _EPS and s1 > l2[1] + _EPS:
            return False
    return True