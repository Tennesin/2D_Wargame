"""ui/upgrade_icons.py — процедурные иконки улучшений для ячеек панели и страницы инструкции.
О танках и игре не знает: рисует по названию значка ("damage", "armor", "engine", "pierce",
"drives", "ballistics", "blast")."""
import math

import pygame

SS = 4                      # рисуем в SS раз крупнее, затем smoothscale
CELL_ICON_PX = 30           # сторона иконки в ячейке панели улучшений

OUTLINE = (24, 26, 30)
LIGHT = (232, 236, 242)
STEEL = (190, 205, 225)
STEEL_DARK = (132, 150, 176)
BRASS = (226, 182, 84)
BRASS_DARK = (168, 124, 50)
GREEN = (110, 225, 110)
YELLOW = (255, 214, 70)
ORANGE = (255, 140, 50)

class _Canvas:
    """Рисует в долях стороны (0..1), всё с тёмным контуром."""

    def __init__(self, surf):
        self.s = surf
        self.w, self.h = surf.get_size()
        self.ol = max(SS, round(self.w * 0.035))       # толщина контура

    def p(self, x, y):
        return x * self.w, y * self.h

    def poly(self, color, pts, outline=True):
        q = [self.p(x, y) for x, y in pts]
        pygame.draw.polygon(self.s, color, q)
        if outline:
            pygame.draw.polygon(self.s, OUTLINE, q, self.ol)

    def outline(self, pts):
        pygame.draw.polygon(self.s, OUTLINE, [self.p(x, y) for x, y in pts], self.ol)

    def rect(self, color, x0, y0, x1, y1):
        r = pygame.Rect(round(x0 * self.w), round(y0 * self.h),
                        round((x1 - x0) * self.w), round((y1 - y0) * self.h))
        pygame.draw.rect(self.s, color, r)
        pygame.draw.rect(self.s, OUTLINE, r, self.ol)

    def circle(self, color, cx, cy, r, outline=True):
        c = (round(cx * self.w), round(cy * self.h))
        rad = max(1, round(r * self.w))
        pygame.draw.circle(self.s, color, c, rad)
        if outline:
            pygame.draw.circle(self.s, OUTLINE, c, rad, self.ol)

    def ring(self, color, cx, cy, r, width):
        c = (round(cx * self.w), round(cy * self.h))
        rad = round(r * self.w)
        wd = max(1, round(width * self.w))
        pygame.draw.circle(self.s, OUTLINE, c, rad + self.ol, wd + 2 * self.ol)
        pygame.draw.circle(self.s, color, c, rad, wd)

    def stroke(self, color, pts, width, outline=True):
        """Ломаная заданной толщины с круглыми концами и (по желанию) тёмным контуром."""
        q = [self.p(x, y) for x, y in pts]
        passes = ((OUTLINE, width * self.w + 2 * self.ol), (color, width * self.w)) if outline \
            else ((color, width * self.w),)
        for col, wd in passes:
            wd = max(1, round(wd))
            for a, b in zip(q, q[1:]):
                pygame.draw.line(self.s, col, a, b, wd)
            for x, y in q:
                pygame.draw.circle(self.s, col, (round(x), round(y)), max(1, wd // 2))

def _plus(cx, cy, a, t):
    """Вершины креста с длиной плеча a и полутолщиной t."""
    return [(cx - t, cy - a), (cx + t, cy - a), (cx + t, cy - t), (cx + a, cy - t),
            (cx + a, cy + t), (cx + t, cy + t), (cx + t, cy + a), (cx - t, cy + a),
            (cx - t, cy + t), (cx - a, cy + t), (cx - a, cy - t), (cx - t, cy - t)]

def _seg_dist(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    ln = abx * abx + aby * aby
    t = 0.0 if ln <= 1e-9 else max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ln))
    return math.hypot(ax + abx * t - px, ay + aby * t - py)

# ==========================================
# ИКОНКИ
# ==========================================

def _damage(c, level):
    """Заряженный снаряд по диагонали (остриём вверх-вправо) и искра заряда."""
    tmp = pygame.Surface(c.s.get_size(), pygame.SRCALPHA)
    t = _Canvas(tmp)
    t.rect(BRASS_DARK, 0.06, 0.35, 0.12, 0.65)                                    # закраина гильзы
    t.rect(BRASS, 0.12, 0.37, 0.52, 0.63)                                         # гильза
    t.poly(STEEL, [(0.52, 0.37), (0.68, 0.37), (0.90, 0.50), (0.68, 0.63), (0.52, 0.63)])   # боевая часть
    t.stroke(LIGHT, [(0.16, 0.43), (0.48, 0.43)], 0.03, outline=False)            # блик
    rot = pygame.transform.rotozoom(tmp, 45, 0.72)
    c.s.blit(rot, rot.get_rect(center=(c.w // 2, c.h // 2)))
    cx, cy, big, small = 0.82, 0.18, 0.14, 0.045                                  # четырёхлучевая искра
    c.poly(YELLOW, [(cx, cy - big), (cx + small, cy - small), (cx + big, cy), (cx + small, cy + small),
                    (cx, cy + big), (cx - small, cy + small), (cx - big, cy), (cx - small, cy - small)])

def _armor(c, level):
    """Щит: левая половина светлее, правая темнее."""
    body = [(0.5, 0.08), (0.8, 0.14), (0.8, 0.52), (0.74, 0.68), (0.62, 0.82), (0.5, 0.92),
            (0.38, 0.82), (0.26, 0.68), (0.2, 0.52), (0.2, 0.14)]
    left = [(0.5, 0.08), (0.2, 0.14), (0.2, 0.52), (0.26, 0.68), (0.38, 0.82), (0.5, 0.92)]
    c.poly(STEEL_DARK, body)
    c.poly(STEEL, left, outline=False)
    c.outline(body)

def _engine(c, level):
    """Две шевронные стрелки «>>» остриём вверх и маленький зелёный плюс."""
    chevron = [(0.22, 0.46), (0.5, 0.20), (0.78, 0.46), (0.78, 0.58), (0.5, 0.32), (0.22, 0.58)]
    for dy in (0.26, 0.0):
        c.poly(LIGHT, [(x, y + dy) for x, y in chevron])
    c.poly(GREEN, _plus(0.80, 0.20, 0.13, 0.045))

def _pierce(c, level):
    """Пластина брони, пробитая дротиком."""
    c.rect(STEEL_DARK, 0.42, 0.10, 0.58, 0.90)
    c.poly(STEEL, [(0.20, 0.44), (0.06, 0.24), (0.30, 0.44)])                     # оперение
    c.poly(STEEL, [(0.20, 0.56), (0.06, 0.76), (0.30, 0.56)])
    c.rect(LIGHT, 0.12, 0.43, 0.66, 0.57)                                         # тело
    c.poly(ORANGE, [(0.66, 0.40), (0.95, 0.50), (0.66, 0.60)])                    # наконечник

def _drives(c, level):
    """Две круговые стрелки: вращение (приводы поворота)."""
    for a0, a1 in ((15, 140), (195, 320)):
        outer, inner = [], []
        for i in range(11):
            a = math.radians(a0 + (a1 - a0) * i / 10)
            outer.append((0.5 + 0.34 * math.cos(a), 0.5 + 0.34 * math.sin(a)))
            inner.append((0.5 + 0.20 * math.cos(a), 0.5 + 0.20 * math.sin(a)))
        a = math.radians(a1)
        ca, sa = math.cos(a), math.sin(a)
        px, py = 0.5 + 0.27 * ca, 0.5 + 0.27 * sa
        head = [(px + ca * 0.15, py + sa * 0.15), (px - sa * 0.20, py + ca * 0.20),
                (px - ca * 0.15, py - sa * 0.15)]
        c.poly(LIGHT, outer + head + inner[::-1])
    c.circle(YELLOW, 0.5, 0.5, 0.06)

def _ballistics(c, level):
    """Снайперский прицел: кольцо, четыре штриха и точка."""
    c.ring(LIGHT, 0.5, 0.5, 0.30, 0.06)
    for seg in (((0.05, 0.5), (0.38, 0.5)), ((0.62, 0.5), (0.95, 0.5)),
                ((0.5, 0.05), (0.5, 0.38)), ((0.5, 0.62), (0.5, 0.95))):
        c.stroke(LIGHT, list(seg), 0.05)
    c.circle(YELLOW, 0.5, 0.5, 0.045)

def _blast(c, level):
    """Экраны (по числу уровней) под тупым углом и пять жёлтых лучей взрыва, упирающихся в них."""
    level = max(1, min(3, level))

    def screen(k):
        ax = 0.32 + 0.15 * k
        return [(ax + 0.24, 0.46 - 0.24), (ax, 0.46), (ax, 0.92)]

    first = screen(0)
    ox, oy = 0.09, 0.36                                                           # центр взрыва
    for deg in (-12, 6, 24, 42, 60):
        dx, dy = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        t = 0.10
        while t < 0.8:                                                            # идём по лучу до экрана
            x, y = ox + dx * t, oy + dy * t
            if min(_seg_dist(x, y, *first[0], *first[1]),
                   _seg_dist(x, y, *first[1], *first[2])) < 0.08:
                break
            t += 0.01
        c.stroke(YELLOW, [(ox + dx * 0.10, oy + dy * 0.10), (ox + dx * t, oy + dy * t)], 0.05)
    c.circle(ORANGE, ox, oy, 0.07)
    c.circle(YELLOW, ox, oy, 0.035, outline=False)
    for k in range(level - 1, -1, -1):                                            # дальние линии первыми
        c.stroke(STEEL, screen(k), 0.06)

_PAINTERS = {"damage": _damage, "armor": _armor, "engine": _engine, "pierce": _pierce,
             "drives": _drives, "ballistics": _ballistics, "blast": _blast}

def make_upgrade_icon(kind, size, level=1, bg=None):
    """Готовая поверхность size = (w, h) с иконкой kind. level влияет только на «blast» (число экранов).
    bg: цвет плитки под иконкой (для списков; в ячейках фон рисует сама панель) или None."""
    w, h = size
    big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
    if bg is not None:
        pygame.draw.rect(big, bg, big.get_rect(), border_radius=SS * 5)
    painter = _PAINTERS.get(kind)
    if painter is not None:
        painter(_Canvas(big), level)
    return pygame.transform.smoothscale(big, (w, h))