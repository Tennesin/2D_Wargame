"""vehicles/sprite_base.py — общая часть рисования техники с орудием: цвета, гусеницы, «ручка» Pen,
кэши спрайтов, тень, ствол и главный метод draw. Конкретный корпус и башню рисуют наследники
(tank/sprites.py, td/sprites.py). Все размеры здесь в МЕТРАХ эталонного спрайта
(x вправо, y вниз, перед = -y)."""
import math
import random

import pygame

from engine import (LRUCache, SHADOW_ALPHA, heading_vector, clamp, Team, PX_PER_M, lerp_color,
                    shrink_polygon)
from .chassis_params import TRACK_LINK_M
from .hulls import NOSE_FLAT, NOSE_PIKE, screen_pieces, SCREEN_OFFSET_M, SCREEN_THICK_M, PIKE_BAND_M
from .running_gear import LEFT, RIGHT
from .gun_params import BARREL_LEN_STEP_M, BARREL_THICK_STEP_M, BARREL_HIDDEN_M

# ==========================================
# 1. КОНСТАНТЫ РИСОВКИ
# ==========================================
SS = 2                                   # суперсэмплинг: рисуем в SS раз крупнее, затем smoothscale
OUTLINE_W = SS                           # толщина контура ≈ 1 px на экране при любом зуме
BREAK_MARK_REF_LEN = 6.3                 # длина гусеницы, для которой заданы смещения разрывов
BREAK_MARK_OFFSETS = (1.3, 2.9, 4.5)     # м от переднего края гусеницы

SHADOW_HULL_M = (0.25, 0.35)             # смещение тени корпуса, м
SHADOW_TURRET_M = (0.40, 0.55)           # башня выше, поэтому тень дальше

PAINT_K = 0.55                           # насколько сильно корпус и башня подкрашиваются цветом команды

OUTLINE = (38, 33, 28)
TRACK_BODY = (58, 54, 49)
TRACK_LINK = (118, 111, 100)
TRACK_BROKEN = (84, 50, 42)              # сбитая гусеница: ржаво-бурая
TRACK_BROKEN_MARK = (150, 70, 50)        # трещины на ней

SKIRT_MAIN = (150, 142, 124)
APPLIQUE = (138, 129, 112)
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

ANGLE_STEPS = 480
ANGLE_STEP = 360.0 / ANGLE_STEPS
ROT_CACHE_BYTES = 48 * 1024 * 1024       # бюджет памяти под кэш повёрнутых поверхностей
# --- фактура корпуса ---
GRAIN_TILE_PX = 128          # сторона бесшовного тайла зерна, px
GRAIN_DOTS = 2600            # сколько точек зерна на тайл
GRAIN_DEPTH = 0.09           # самая тёмная точка затемняет цвет на столько (0.09 = 9%)
GRAIN_BASE = 0.015           # общее лёгкое затемнение тайла
GRAIN_SCRATCHES = 40         # короткие царапины на тайл
GRAIN_MIN_PPM = 16.0         # при меньшем масштабе (пикселей на метр) зерно не накладываем: оно мерцает

SEAM_FRACS = (0.30, 0.62)    # где на палубе идут поперечные швы (доли длины палубы)
SEAM_W_M = 0.05              # толщина шва, м
RIVET_R_M = 0.04             # радиус заклёпки, м
RIVET_STEP_M = 0.5           # примерный шаг заклёпок вдоль шва, м

def apply_paint(color, paint):
    """Подмешивает цвет команды к цвету детали. paint=None: деталь остаётся как есть."""
    if paint is None:
        return color
    return tuple(int(c + (p - c) * PAINT_K) for c, p in zip(color, paint))

def layout_of(spec):
    """Раскладка корпуса техники (она есть у всей техники)."""
    return spec.layout

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

def _outline_x_at(outline, y):
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

# ==========================================
# 2. «РУЧКА» ДЛЯ РИСОВАНИЯ В МЕТРАХ
# ==========================================

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

# ==========================================
# 3. ОБЩИЙ ОТРИСОВЩИК
# ==========================================

class GunVehicleRenderer:
    """Порядок слоёв: тень, корпус, ствол, башня (качающаяся часть), передний слой (хук).
    Наследник обязан задать HULL_HALF_M и реализовать _build_hull и _build_turret."""

    HULL_HALF_M = None
    HAS_TURRET_SPRITE = True

    def __init__(self):
        self._ppm = 0.0
        self._hull_cache = LRUCache(240)
        self._turret_cache = LRUCache(40)
        self._barrel_cache = LRUCache(80)
        self._sil_cache = LRUCache(240)
        self._rot_cache = LRUCache(400)
        self._gear_cache = LRUCache(20)
        self._shadow_buf = None

    # ---------- что обязан сделать наследник ----------

    def _build_hull(self, paint, look, spec):
        raise NotImplementedError

    def _hull_shift_m(self, spec):
        """На сколько метров корпус сдвинут назад от центра спрайта (то же число, что идёт в Pen)."""
        raise NotImplementedError

    def _build_turret(self, team_color, paint, look, emblem, spec):
        raise NotImplementedError

    def _draw_front_layer(self, screen, tank, cx, cy, hull_k, hull_scale, team, paint, look):
        """Хук: детали, которые вращаются вместе с КОРПУСОМ, но рисуются ПОВЕРХ ствола."""
        return

    # ---------- масштаб ----------
    def set_zoom(self, ppm):
        """Вызывается при смене зума: запоминает масштаб и сбрасывает кэши спрайтов."""
        self._ppm = ppm
        for cache in (self._hull_cache, self._turret_cache, self._barrel_cache,
                      self._sil_cache, self._rot_cache, self._gear_cache):
            cache.clear()
        # размер повёрнутой поверхности растёт с зумом, поэтому лимит записей считаем от бюджета памяти
        side = 2.0 * self.HULL_HALF_M * ppm * 1.42
        per_surface = max(1.0, side * side * 4.0)
        self._rot_cache.limit = int(clamp(ROT_CACHE_BYTES / per_surface, 40, 3000))

    # ---------- главный метод ----------

    def draw(self, screen, camera, tank):
        ppm = self._ppm
        sx, sy = camera.world_to_screen(tank.x, tank.y)
        cx, cy = int(round(sx)), int(round(sy))

        spec = tank.spec
        look = spec.LOOK
        var = spec.HULL_VARIANT
        hs, ts = spec.HULL_SCALE, spec.TURRET_SCALE
        bl = int(round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M))
        bt = int(round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M))
        team = tank.team_color
        paint = None if tank.team is Team.PLAYER else team
        emblem = tank.emblem
        broken = (tank.tracks.is_broken(LEFT), tank.tracks.is_broken(RIGHT))

        hull_k = self._bucket(tank.hull_angle)
        turret_k = self._bucket(tank.turret_angle)
        barrel_key = (bl, bt, look.barrel_key)

        # корпус и ходовая больше не зависят от фазы гусениц: оба слоя берутся из кэша по углу
        gear_rot = self._rotated("gear", (var, broken),
                                 lambda: self._get_gear(spec, *broken), hull_k, hs)
        hull_rot = self._rotated("hull", (paint, look.hull_key, var),
                                 lambda: self._get_hull(paint, look, spec), hull_k, hs)
        barrel_rot = self._rotated("barrel", barrel_key,
                                   lambda: self._get_barrel(bl, bt, look), turret_k, ts)

        fx, fy = heading_vector(turret_k * ANGLE_STEP)
        f = (spec.GUN_FRONT_M + bl * BARREL_LEN_STEP_M / 2.0 - BARREL_HIDDEN_M / 2.0
             - tank.recoil_m) * ppm * ts
        hull_rect = hull_rot.get_rect(center=(cx, cy))
        gear_rect = gear_rot.get_rect(center=(cx, cy))
        barrel_rect = barrel_rot.get_rect(center=(round(cx + fx * f), round(cy + fy * f)))

        hox, hoy = (round(v * ppm * hs) for v in SHADOW_HULL_M)
        tox, toy = (round(v * ppm * ts) for v in SHADOW_TURRET_M)
        sil_hull = self._rotated(
            "sil_hull", (look.hull_key, var),
            lambda: self._get_sil(("hull", look.hull_key, var), self._gear_plus_hull(spec, paint, look)),
            hull_k, hs)
        sil_barrel = self._rotated(
            "sil_barrel", barrel_key,
            lambda: self._get_sil(("barrel", bl, bt, look.barrel_key), self._get_barrel(bl, bt, look)),
            turret_k, ts)
        parts = [
            (sil_hull, sil_hull.get_rect(center=hull_rect.center).move(hox, hoy)),
            (sil_barrel, sil_barrel.get_rect(center=barrel_rect.center).move(tox, toy)),
        ]

        turret_rot = turret_rect = None
        if self.HAS_TURRET_SPRITE:
            turret_key = (team, paint, look.turret_key, emblem, var)
            turret_rot = self._rotated("turret", turret_key,
                                       lambda: self._get_turret(team, paint, look, emblem, spec), turret_k, ts)
            turret_rect = turret_rot.get_rect(center=(cx, cy))
            sil_turret = self._rotated(
                "sil_turret", (look.turret_key, var),
                lambda: self._get_sil(("turret", look.turret_key, var),
                                      self._get_turret(team, paint, look, emblem, spec)),
                turret_k, ts)
            parts.append((sil_turret, sil_turret.get_rect(center=turret_rect.center).move(tox, toy)))

        union = parts[0][1].unionall([r for _, r in parts[1:]])
        buf = self._ensure_shadow_buf(union.w, union.h)
        buf.fill((0, 0, 0, 0), (0, 0, union.w, union.h))
        for surf, rect in parts:
            buf.blit(surf, (rect.x - union.x, rect.y - union.y))
        screen.blit(buf, union.topleft, area=(0, 0, union.w, union.h))

        screen.blit(gear_rot, gear_rect)                      # тело гусениц под корпусом
        self._draw_track_links(screen, tank, cx, cy, hull_k, hs, spec, broken)   # бегущие звенья
        screen.blit(hull_rot, hull_rect)                      # корпус перекрывает внутренние края гусениц
        screen.blit(barrel_rot, barrel_rect)
        if turret_rot is not None:
            screen.blit(turret_rot, turret_rect)
        self._draw_front_layer(screen, tank, cx, cy, hull_k, hs, team, paint, look)

    # ---------- тень и кэши ----------
    @staticmethod
    def _make_silhouette(surface):
        mask = pygame.mask.from_surface(surface)
        return mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))

    @staticmethod
    def _bucket(angle):
        """Номер положения угла (0..ANGLE_STEPS-1)."""
        return round(angle / ANGLE_STEP) % ANGLE_STEPS

    def _rotated(self, kind, base_key, get_base, bucket, scale):
        """Повёрнутая копия спрайта из кэша."""
        key = (kind, base_key, bucket, round(scale, 3))
        return self._rot_cache.get_or_build(
            key, lambda: pygame.transform.rotozoom(get_base(), -bucket * ANGLE_STEP, scale))

    def _ensure_shadow_buf(self, w, h):
        """Буфер тени: пересоздаётся только если нужен больший размер."""
        need = max(w, h)
        if self._shadow_buf is None or self._shadow_buf.get_width() < need:
            size = (need + 63) // 64 * 64
            self._shadow_buf = pygame.Surface((size, size), pygame.SRCALPHA)
            self._shadow_buf.set_alpha(SHADOW_ALPHA)
        return self._shadow_buf

    def _finish(self, surf, offset=(0, 0)):
        """Финальная обработка готового спрайта корпуса, башни или маски: зерно."""
        apply_grain(surf, self._ppm, offset)
        return surf

    def _get_sil(self, key, surface):
        return self._sil_cache.get_or_build(key, lambda: self._make_silhouette(surface))

    def _get_hull(self, paint, look, spec):
        return self._hull_cache.get_or_build(
            (paint, look.hull_key, spec.HULL_VARIANT),
            lambda: self._build_hull(paint, look, spec))

    def _get_turret(self, team_color, paint, look, emblem, spec):
        return self._turret_cache.get_or_build(
            (team_color, paint, look.turret_key, emblem, spec.HULL_VARIANT),
            lambda: self._build_turret(team_color, paint, look, emblem, spec))

    def _get_barrel(self, bl, bt, look):
        return self._barrel_cache.get_or_build(
            (bl, bt, look.barrel_key), lambda: self._build_barrel(bl, bt, look))

    # ---------- общие детали корпуса ----------

    @staticmethod
    def _draw_track_body(pen, layout, side, broken=False):
        """Тело гусеницы без звеньев (звенья бегут отдельно и рисуются прямо на экране).
        side: -1 левая, +1 правая."""
        tw, top, ln = layout.track_w, layout.track_top, layout.track_len
        left = side * layout.track_x - tw / 2
        if not broken:
            pen.rect(TRACK_BODY, left, top, tw, ln, r=0.22)
            return
        pen.rect(TRACK_BROKEN, left, top, tw, ln, r=0.22)
        for off in BREAK_MARK_OFFSETS:                       # разрывы поперёк ленты
            y = top + off * ln / BREAK_MARK_REF_LEN
            pen.line(TRACK_BROKEN_MARK, left + 0.08, y, left + tw - 0.08, y + 0.35, 0.08)

    def _build_gear(self, spec, left_broken, right_broken):
        """Слой ходовой: обе гусеницы. Лежит под корпусом, того же размера, что спрайт корпуса."""
        ppm = self._ppm
        size = 2 * math.ceil(self.HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = Pen(big, ppm * SS, 0.0, self._hull_shift_m(spec))
        layout = layout_of(spec)
        self._draw_track_body(pen, layout, -1, left_broken)
        self._draw_track_body(pen, layout, +1, right_broken)
        return pygame.transform.smoothscale(big, (size, size))

    def _get_gear(self, spec, left_broken=False, right_broken=False):
        return self._gear_cache.get_or_build(
            (spec.HULL_VARIANT, left_broken, right_broken),
            lambda: self._build_gear(spec, left_broken, right_broken))

    def _gear_plus_hull(self, spec, paint, look):
        """Ходовая + корпус одним спрайтом: из него строится силуэт тени. Зовётся только при промахе кэша."""
        surf = self._get_gear(spec).copy()
        surf.blit(self._get_hull(paint, look, spec), (0, 0))
        return surf

    def _draw_track_links(self, screen, tank, cx, cy, hull_k, scale, spec, broken):
        """Бегущие звенья целых гусениц: линии прямо на экране. Сбитая гусеница стоит без звеньев."""
        k = self._ppm * scale                        # экранных px на метр спрайта
        if TRACK_LINK_M * k < 3.0:                   # на дальнем зуме звенья сливаются
            return
        layout = layout_of(spec)
        fx, fy = heading_vector(hull_k * ANGLE_STEP)
        rx, ry = -fy, fx                             # вправо от корпуса
        shift = self._hull_shift_m(spec)
        width = max(1, round(0.06 * k))
        y_min = layout.track_top + 0.05
        y_max = layout.track_top + layout.track_len - 0.05

        def pt(x, y):                                # координаты корпуса (м) -> экран
            y += shift
            return (cx + (rx * x - fx * y) * k, cy + (ry * x - fy * y) * k)

        for side, offset, bad in ((-1, tank.left_track_offset, broken[0]),
                                  (1, tank.right_track_offset, broken[1])):
            if bad:
                continue
            xc = side * layout.track_x
            xa, xb = xc - layout.track_w / 2 + 0.07, xc + layout.track_w / 2 - 0.07
            y = layout.track_top - TRACK_LINK_M + offset / PX_PER_M   # смещение хранится в px эталона
            y += math.ceil((y_min - y) / TRACK_LINK_M) * TRACK_LINK_M
            while y < y_max:
                pygame.draw.line(screen, TRACK_LINK, pt(xa, y), pt(xb, y), width)
                y += TRACK_LINK_M

    @staticmethod
    def _draw_skirts(pen, level, paint, layout):
        """Бортовые экраны поверх гусениц. Не выходят за габарит гусениц, хитбокс не меняется."""
        if level <= 0:
            return
        color = apply_paint(SKIRT_MAIN, paint)
        y0, y1, width = layout.skirt_levels[min(level, len(layout.skirt_levels)) - 1]
        n = max(1, round((y1 - y0) / layout.skirt_pitch_m))   # плиты с зазором
        step = (y1 - y0) / n
        outer = layout.skirt_outer_x
        for x in (outer - width, -outer):
            for i in range(n):
                pen.rect(color, x, y0 + i * step + 0.03, width, step - 0.06)

    @staticmethod
    def _draw_seams(pen, layout, color):
        """Поперечные швы листов палубы от борта до борта, с рядом заклёпок.
        Шов доходит до самого контура корпуса, поэтому пересекает палубу и стыкуется с бортами:
        это «сшивает» части корпуса. Рисовать ПОСЛЕ палубы и ДО решёток, люков и башни."""
        dx, dy, dw, dh = layout.deck_rect
        for t in SEAM_FRACS:
            y = dy + dh * t
            lo, hi = _outline_x_at(layout.outline, y)
            if lo is None:
                continue
            x0, x1 = lo + 0.06, hi - 0.06
            pen.line(color, x0, y, x1, y, SEAM_W_M)
            n = max(2, round((x1 - x0) / RIVET_STEP_M))
            for i in range(1, n):
                pen.ellipse(color, x0 + (x1 - x0) * i / n, y + 0.11,
                            RIVET_R_M, RIVET_R_M, outline=None)

    @staticmethod
    def _draw_front_kit(pen, level, paint, layout):
        """Накладная броня на лбу. Плоский лоб: один многоугольник (+ планка и клинья на уровне 2).
        Щучий нос: отдельные пластины на скатах (см. _draw_pike_kit)."""
        if level <= 0:
            return
        if layout.nose == NOSE_PIKE:
            GunVehicleRenderer._draw_pike_kit(pen, paint, layout)
            return

        color = apply_paint(lerp_color(HULL_LIGHT, HULL_MAIN, 0.5), paint)
        edge = apply_paint(HULL_DARK, paint)

        poly = layout.front_kit_poly
        pen.poly(color, poly, outline=edge)
        cx = sum(x for x, _ in poly) / len(poly)
        cy = sum(y for _, y in poly) / len(poly)
        for x, y in poly:                                   # заклёпка в 0.14 м от каждого угла к центру
            dx, dy = cx - x, cy - y
            ln = math.hypot(dx, dy) or 1.0
            pen.ellipse(edge, x + dx / ln * 0.14, y + dy / ln * 0.14,
                        RIVET_R_M, RIVET_R_M, outline=None)

        if level >= 2:
            bx, by, bw, bh = layout.front_kit_bar
            pen.rect(color, bx, by, bw, bh, outline=edge, r=0.05)
            for sx in (-1, 1):                              # в раскладке задан правый клин
                pen.poly(color, [(sx * x, y) for x, y in layout.front_kit_wedge], outline=edge)

    PIKE_KIT_INSET = 0.78       # во сколько раз пластина меньше полосы ската (остаётся рамка вокруг)
    PIKE_KIT_LIGHTEN = 0.25     # насколько пластина светлее своей полосы

    @staticmethod
    def _draw_pike_kit(pen, paint, layout):
        """Накладка щучьего носа: по одной пластине на каждый скат. Пластина лежит внутри своей
        полосы (те же четыре угла, что в _draw_pike_plate), поэтому гребень по оси и V-шов остаются
        видны. Цвет = цвет полосы, чуть светлее: сохраняется свет слева."""
        left, tip, right = layout.front_plate
        b = PIKE_BAND_M
        apex = (0.0, tip[1] + b)
        bands = (
            ([left, tip, apex, (left[0], left[1] + b)], lerp_color(HULL_MAIN, HULL_LIGHT, 0.45)),
            ([tip, right, (right[0], right[1] + b), apex], lerp_color(HULL_MAIN, DECK, 0.30)),
        )
        edge = apply_paint(HULL_DARK, paint)
        for band, band_color in bands:
            cx = sum(x for x, _ in band) / 4.0
            cy = sum(y for _, y in band) / 4.0
            plate = shrink_polygon(band, cx, cy, GunVehicleRenderer.PIKE_KIT_INSET)
            color = apply_paint(lerp_color(band_color, HULL_LIGHT, GunVehicleRenderer.PIKE_KIT_LIGHTEN), paint)
            pen.poly(color, plate, outline=edge)
            px = sum(x for x, _ in plate) / 4.0
            py = sum(y for _, y in plate) / 4.0
            for x, y in plate:                              # заклёпка в 0.10 м от угла к центру пластины
                dx, dy = px - x, py - y
                ln = math.hypot(dx, dy) or 1.0
                pen.ellipse(edge, x + dx / ln * 0.10, y + dy / ln * 0.10,
                            RIVET_R_M, RIVET_R_M, outline=None)

    @staticmethod
    def _draw_front_screen(pen, level, paint, layout):
        """Четыре тонких листа перед лбом на стойках. level только включает показ:
        число и толщина листов от ползунка не зависят."""
        if level <= 0:
            return
        color = apply_paint(SCREEN_MAIN, paint)
        off = SCREEN_OFFSET_M
        for (ax, ay), (bx, by), (nx, ny) in screen_pieces(layout):
            p0 = (ax + nx * off, ay + ny * off)
            p1 = (bx + nx * off, by + ny * off)
            pen.line(SCREEN_MESH, ax, ay, p0[0], p0[1], 0.04)                  # стойки
            pen.line(SCREEN_MESH, bx, by, p1[0], p1[1], 0.04)
            pen.line(OUTLINE, p0[0], p0[1], p1[0], p1[1], SCREEN_THICK_M + 0.04)   # контур листа
            pen.line(color, p0[0], p0[1], p1[0], p1[1], SCREEN_THICK_M)            # сам лист

    @staticmethod
    def _draw_exhaust(pen, level, layout):
        """Выхлопные патрубки на кормовой плите."""
        if level <= 0:
            return
        r = 0.13 if level == 1 else 0.17
        for x in layout.exhaust_xs:
            pen.ellipse(GRILL, x, layout.exhaust_y, r, r)

    @staticmethod
    def _draw_deck(pen, y_end, hull_dark, deck_top, half_w=1.05, lead=0.45, min_free=0.9):
        """Моторная крышка на палубе между носом и башней."""
        y0 = deck_top + lead
        free = y_end - 0.15 - y0
        if free < min_free:
            return
        gw = half_w - 0.15
        pen.rect(hull_dark, -half_w, y0, 2.0 * half_w, free, r=0.05)        # рама крышки
        pen.rect(GRILL, -gw, y0 + 0.12, 2.0 * gw, free - 0.24)              # решётка
        ly = y0 + 0.32
        while ly < y0 + free - 0.2:                                         # жалюзи
            pen.line(GRILL_LINE, -(gw - 0.14), ly, gw - 0.14, ly, 0.05)
            ly += 0.26
        if free >= 2.2:                                                     # длинная палуба: два люка
            pen.rect(hull_dark, -gw, y0 + free / 2.0 - 0.05, 2.0 * gw, 0.10, outline=None)

    @staticmethod
    def _draw_pike_plate(pen, layout, paint):
        """Щучий нос: две полосы вдоль скатов (близкие тона) и клин палубы с V-образным передним краем.
        Рисовать ПОСЛЕ прямоугольника палубы: клин и полосы перекрывают его верхний контур."""
        left, tip, right = layout.front_plate
        hw = right[0]
        sh_y, tip_y = left[1], tip[1]
        b = PIKE_BAND_M
        apex = (0.0, tip_y + b)                    # вершина V
        lo_l, lo_r = (-hw, sh_y + b), (hw, sh_y + b)

        c_left = apply_paint(lerp_color(HULL_MAIN, HULL_LIGHT, 0.45), paint)
        c_right = apply_paint(lerp_color(HULL_MAIN, DECK, 0.30), paint)
        c_deck = apply_paint(DECK, paint)
        seam = apply_paint(HULL_DARK, paint)

        pen.poly(c_left, [left, tip, apex, lo_l], outline=None)
        pen.poly(c_right, [tip, right, lo_r, apex], outline=None)
        pen.poly(c_deck, [lo_l, apex, lo_r], outline=None)

        # наружный контур скатов (полосы перекрыли внутреннюю половину обводки корпуса)
        ow = OUTLINE_W / pen.k
        pen.line(OUTLINE, left[0], left[1], tip[0], tip[1], ow)
        pen.line(OUTLINE, tip[0], tip[1], right[0], right[1], ow)

        # гребень: от острия по оси, продолжается на клин палубы
        pen.line(seam, 0.0, tip_y + 0.06, 0.0, tip_y + b + 0.7, 0.05)

        # V-шов и заклёпки вдоль него
        for a, c in ((lo_l, apex), (apex, lo_r)):
            pen.line(seam, a[0], a[1], c[0], c[1], 0.05)
            n = max(2, round(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.45))
            for i in range(1, n):
                t = i / n
                pen.ellipse(seam, a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t - 0.10,
                            RIVET_R_M, RIVET_R_M, outline=None)

    @staticmethod
    def _draw_wedge_plate(pen, layout, paint):
        """Клин: центральная плоская плита и два боковых скоса (слева светлее, справа темнее,
        как у щучьего носа). Рисовать ПОСЛЕ прямоугольника палубы."""
        left, face_l, face_r, right = layout.front_plate
        sh_y = left[1]                                   # линия плеч
        c_face = apply_paint(HULL_LIGHT, paint)
        c_left = apply_paint(lerp_color(HULL_MAIN, HULL_LIGHT, 0.45), paint)
        c_right = apply_paint(lerp_color(HULL_MAIN, DECK, 0.30), paint)
        seam = apply_paint(HULL_DARK, paint)

        pen.poly(c_left, [left, face_l, (face_l[0], sh_y)], outline=None)
        pen.poly(c_right, [face_r, right, (face_r[0], sh_y)], outline=None)
        pen.poly(c_face, [face_l, face_r, (face_r[0], sh_y), (face_l[0], sh_y)], outline=None)

        ow = OUTLINE_W / pen.k                           # наружный контур носа
        for a, b in ((left, face_l), (face_l, face_r), (face_r, right)):
            pen.line(OUTLINE, a[0], a[1], b[0], b[1], ow)

        for x in (face_l[0], face_r[0]):                 # швы между плитами и стык с палубой
            pen.line(seam, x, face_l[1] + 0.04, x, sh_y, 0.05)
        pen.line(seam, left[0] + 0.04, sh_y, right[0] - 0.04, sh_y, 0.05)

        n = max(2, round((face_r[0] - face_l[0]) / 0.45))   # заклёпки вдоль лобового края
        for i in range(1, n):
            x = face_l[0] + (face_r[0] - face_l[0]) * i / n
            pen.ellipse(seam, x, face_l[1] + 0.14, RIVET_R_M, RIVET_R_M, outline=None)

    # ---------- ствол (одинаковый у всех) ----------
    def _build_barrel(self, bl, bt, look):
        """Ствол: узкая вертикальная картинка (дульный срез сверху). Центр — середина видимой длины."""
        ppm = self._ppm
        length = bl * BARREL_LEN_STEP_M
        thick = bt * BARREL_THICK_STEP_M
        half = (length + BARREL_HIDDEN_M) / 2.0  # часть уходит под башню
        w = max(2, 2 * math.ceil((thick + 0.30) * ppm / 2.0))
        h = max(2, round(2.0 * half * ppm))
        big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
        pen = Pen(big, ppm * SS)

        pen.rect(GUN, -thick / 2, -half, thick, 2.0 * half)                       # ствол
        pen.rect(GUN_LIGHT, -(thick + 0.08) / 2, -half + 0.35 * length,
                 thick + 0.08, 0.30, r=0.05)                                      # эжектор
        pen.rect(GUN_DARK, -(thick + 0.06) / 2, -half, thick + 0.06, 0.22)        # дульный срез

        if look.gun > 0:    # дульный тормоз: шире ствола, но в пределах заготовки (запас 0.30 м)
            bw = thick + (0.14 if look.gun == 1 else 0.22)
            pen.rect(GUN_DARK, -bw / 2, -half + 0.25, bw, 0.40, r=0.04)
            for y in (-half + 0.38, -half + 0.52):
                pen.line(GUN_LIGHT, -bw / 2 + 0.03, y, bw / 2 - 0.03, y, 0.04)

        return pygame.transform.smoothscale(big, (w, h))