"""vehicles/pen.py — палитра техники, фактура корпуса (зерно) и «ручка» Pen для рисования в метрах."""
import random
import pygame

SS = 2                                   # суперсэмплинг: рисуем в SS раз крупнее, затем smoothscale
OUTLINE_W = SS                           # толщина контура ≈ 1 px на экране при любом зуме

OUTLINE = (38, 33, 28)
TRACK_BODY = (58, 54, 49)
TRACK_LINK = (118, 111, 100)
TRACK_BROKEN = (84, 50, 42)              # сбитая гусеница: ржаво-бурая
TRACK_BROKEN_MARK = (150, 70, 50)        # трещины на ней

SKIRT_MAIN = (150, 142, 124)
SCREEN_MAIN = (128, 122, 108)
SCREEN_MESH = (70, 66, 58)
HULL_MAIN = (170, 160, 140)
HULL_LIGHT = (200, 191, 169)
HULL_DARK = (126, 117, 101)
DECK = (155, 146, 126)
RING = (112, 104, 90)
GRILL = (72, 66, 58)
GRILL_LINE = (112, 104, 91)

TURRET_MAIN = (184, 174, 152)
TURRET_LIGHT = (210, 202, 182)
TURRET_DARK = (140, 131, 114)

GUN = (112, 110, 105)
GUN_LIGHT = (150, 147, 140)
GUN_DARK = (62, 60, 56)
EMBLEM_COLOR = (245, 215, 80)

PAINT_K = 0.55                           # насколько сильно корпус и башня подкрашиваются цветом команды
def apply_paint(color, paint):
    """Подмешивает цвет команды к цвету детали. paint=None: деталь остаётся как есть."""
    if paint is None:
        return color
    return tuple(int(c + (p - c) * PAINT_K) for c, p in zip(color, paint))

# --- фактура корпуса ---
GRAIN_TILE_PX = 128          # сторона бесшовного тайла зерна, px
GRAIN_DOTS = 2600            # сколько точек зерна на тайл
GRAIN_DEPTH = 0.09           # самая тёмная точка затемняет цвет на столько (0.09 = 9%)
GRAIN_BASE = 0.015           # общее лёгкое затемнение тайла
GRAIN_SCRATCHES = 40         # короткие царапины на тайл
GRAIN_MIN_PPM = 16.0         # при меньшем масштабе (пикселей на метр) зерно не накладываем: оно мерцает
_grain_tile = None

def _make_grain_tile():
    """Бесшовный тайл: светлый фон с редкими тёмными точками и короткими царапинами.
    Каждая точка занимает один пиксель, поэтому швов на стыках тайлов нет;
    царапины заворачиваются по модулю, чтобы они тоже не рвались на краю."""
    rng = random.Random(20240)
    T = GRAIN_TILE_PX
    tile = pygame.Surface((T, T))
    base = round(255 * (1.0 - GRAIN_BASE))
    tile.fill((base, base, base))
    for _ in range(GRAIN_DOTS):
        x, y = rng.randrange(T), rng.randrange(T)
        v = 255 - round(255 * GRAIN_DEPTH * rng.random() ** 1.5)    # чаще слабые, изредка сильные
        tile.set_at((x, y), (v, v, v))
    for _ in range(GRAIN_SCRATCHES):
        x, y = rng.randrange(T), rng.randrange(T)
        sx, sy = rng.choice(((1, 0), (0, 1), (1, 1), (1, -1)))
        v = 255 - round(255 * GRAIN_DEPTH * 0.9)
        for i in range(rng.randint(3, 8)):
            tile.set_at(((x + sx * i) % T, (y + sy * i) % T), (v, v, v))
    return tile.convert()

def apply_grain(surf, ppm, offset=(0, 0)):
    """Накладывает зерно на готовый спрайт (после smoothscale). BLEND_RGB_MULT меняет только цвет,
    альфа-канал (прозрачность вокруг корпуса) остаётся прежним. offset разводит узор корпуса и башни."""
    global _grain_tile
    if ppm < GRAIN_MIN_PPM:
        return
    if _grain_tile is None:
        _grain_tile = _make_grain_tile()
    T = GRAIN_TILE_PX
    w, h = surf.get_size()
    ox, oy = offset
    for y in range(-(oy % T), h, T):
        for x in range(-(ox % T), w, T):
            surf.blit(_grain_tile, (x, y), special_flags=pygame.BLEND_RGB_MULT)

def outline_x_at(outline, y):
    """Левый и правый край выпуклого контура на высоте y: (x_мин, x_макс) или (None, None)."""
    xs = []
    n = len(outline)
    for i in range(n):
        (x0, y0), (x1, y1) = outline[i], outline[(i + 1) % n]
        if min(y0, y1) <= y <= max(y0, y1):
            if y1 == y0:
                xs += [x0, x1]
            else:
                xs.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))
    return (min(xs), max(xs)) if xs else (None, None)

class Pen:
    """Рисует в метрах относительно центра поверхности (с суперсэмплингом и контуром 1 px)."""

    def __init__(self, surf, k, ox=0.0, oy=0.0):
        self.s = surf
        self.k = k                        # пикселей поверхности на метр
        self.ox, self.oy = ox, oy         # сдвиг начала координат, м
        self.cx = surf.get_width() / 2
        self.cy = surf.get_height() / 2

    def p(self, x, y):
        return (self.cx + (x + self.ox) * self.k, self.cy + (y + self.oy) * self.k)

    def poly(self, color, pts, outline=OUTLINE):
        big = [self.p(x, y) for x, y in pts]
        pygame.draw.polygon(self.s, color, big)
        if outline:
            pygame.draw.polygon(self.s, outline, big, OUTLINE_W)

    def rect(self, color, x, y, w, h, outline=OUTLINE, r=0.0):
        x0, y0 = self.p(x, y)
        rect = pygame.Rect(round(x0), round(y0), max(1, round(w * self.k)), max(1, round(h * self.k)))
        radius = round(r * self.k)
        pygame.draw.rect(self.s, color, rect, border_radius=radius)
        if outline:
            pygame.draw.rect(self.s, outline, rect, OUTLINE_W, border_radius=radius)

    def ellipse(self, color, cx, cy, rx, ry, outline=OUTLINE):
        x0, y0 = self.p(cx - rx, cy - ry)
        rect = pygame.Rect(round(x0), round(y0), max(2, round(2 * rx * self.k)), max(2, round(2 * ry * self.k)))
        pygame.draw.ellipse(self.s, color, rect)
        if outline:
            pygame.draw.ellipse(self.s, outline, rect, OUTLINE_W)

    def line(self, color, x1, y1, x2, y2, w):
        pygame.draw.line(self.s, color, self.p(x1, y1), self.p(x2, y2), max(1, round(w * self.k)))

    def set_clip(self, x, y, w, h):
        x0, y0 = self.p(x, y)
        self.s.set_clip(pygame.Rect(round(x0), round(y0), round(w * self.k), round(h * self.k)))

    def clear_clip(self):
        self.s.set_clip(None)