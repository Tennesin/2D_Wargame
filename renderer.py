"""renderer.py — вся отрисовка: земля (чанки с зумом), декор, танк, отладка."""
import math
from collections import OrderedDict

import pygame

from core import CHUNK_SIZE, CELL_SIZE, PX_PER_M
from tank_spec import TURRET_FRONT_M

# ---------- Земля ----------
MIN_CACHED_CHUNKS = 40


def ground_lod(zoom):
    """Чем дальше камера, тем крупнее клетка земли (меньше расчётов шума): 1, 2, 4, 8."""
    if zoom >= 0.35:
        return 1
    if zoom >= 0.17:
        return 2
    if zoom >= 0.12:
        return 4
    return 8


# ---------- Рисовка танка: всё в МЕТРАХ эталонного спрайта (x вправо, y вниз, перед = -y) ----------
SS = 2                                   # суперсэмплинг: рисуем в SS раз крупнее, затем smoothscale
OUTLINE_W = SS                           # толщина контура ≈ 1 px на экране при любом зуме
TRACK_PHASES = 6                         # сколько фаз анимации у гусеницы
HULL_SHIFT_M = 0.3                       # корпус сдвинут назад: ось башни = центр спрайта = центр танка
HULL_HALF_M = 3.7                        # половина стороны квадратной заготовки корпуса, м
TURRET_HALF_M = 2.1                      # половина стороны заготовки башни (без ствола), м
TRACK_X = 1.6                            # центр гусеницы от оси, м
TRACK_W = 0.75
TRACK_TOP = -3.1                         # передний край гусеницы (в координатах корпуса)
TRACK_LEN = 6.3
TRACK_LINK_M = 0.2                       # шаг траков (= Tank.TRACK_STEP / PX_PER_M)

SHADOW_ALPHA = 80
SHADOW_HULL_M = (0.25, 0.35)             # смещение тени корпуса, м
SHADOW_TURRET_M = (0.40, 0.55)           # башня выше, поэтому тень дальше

OUTLINE = (38, 33, 28)
TRACK_BODY = (58, 54, 49)
TRACK_LINK = (118, 111, 100)

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

def _shade(color, k):
    """Умножить цвет на коэффициент (k<1 темнее, k>1 светлее)."""
    return tuple(max(0, min(255, int(c * k))) for c in color)


def _egg(a, front, rear, n=28):
    """Яйцевидный контур башни: узкий нос, широкая корма. a — полуширина, front/rear — полудлины (м)."""
    pts = []
    for i in range(n):
        t = 2.0 * math.pi * i / n
        ux, uy = math.sin(t), math.cos(t)                      # uy > 0 — вперёд
        x = a * ux * (1.0 - 0.22 * max(0.0, uy) ** 2)
        y = -(front if uy > 0 else rear) * uy
        pts.append((x, y))
    return pts


class _Pen:
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


class Renderer:
    def __init__(self, world_generator):
        self.world = world_generator
        self.font = pygame.font.Font(None, 22)

        self._zoom = None                   # зум, под который сейчас построены кэши
        self._ppm = 0.0                     # пикселей экрана на метр эталонного спрайта (= PX_PER_M * zoom)

        self._chunk_cache = OrderedDict()   # (cx, cy, lod) -> Surface, как построено (без масштаба)
        self._scaled_cache = OrderedDict()  # (cx, cy) -> Surface, уже под текущий зум
        self._hull_cache = {}               # (фаза левой, фаза правой, цвет) -> Surface
        self._turret_cache = {}             # цвет -> Surface
        self._barrel_cache = {}             # (длина, толщина) -> Surface
        self._sil_cache = {}                # ключ -> силуэт для тени

        self._shadow_buf = None             # создаётся и растёт по мере надобности

    # ==========================================
    # ГЛАВНЫЙ МЕТОД
    # ==========================================
    def draw(self, screen, camera, tank, debug_lines=None, effects=None):
        self._sync_zoom(camera.zoom)
        self._draw_ground(screen, camera)
        if effects is not None:
            effects.draw_ground(screen, camera)      # пятна от взрывов лежат под танком
        self._draw_tank(screen, camera, tank)
        if effects is not None:
            effects.draw(screen, camera)
        if debug_lines:
            self._draw_debug(screen, debug_lines)

    def _sync_zoom(self, zoom):
        """При смене зума сбрасываем всё, что зависит от масштаба (земля-базовые чанки остаются)."""
        if zoom == self._zoom:
            return
        self._zoom = zoom
        self._ppm = PX_PER_M * zoom
        self._scaled_cache.clear()
        for cache in (self._hull_cache, self._turret_cache, self._barrel_cache, self._sil_cache):
            cache.clear()

    # ==========================================
    # ЗЕМЛЯ И ЧАНКИ
    # ==========================================
    def _draw_ground(self, screen, camera):
        z = camera.zoom
        lod = ground_lod(z)
        left, top = camera.origin_px()
        width, height = screen.get_size()

        span = CHUNK_SIZE * z                  # размер чанка на экране (дробный)
        size = math.ceil(span)                 # заготовка чуть больше шага -> швов между чанками нет

        cx0 = math.floor(left / span)
        cx1 = math.floor((left + width - 1) / span)
        cy0 = math.floor(top / span)
        cy1 = math.floor((top + height - 1) / span)

        visible = 0
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                tile = self._get_scaled_chunk(cx, cy, lod, size)
                screen.blit(tile, (round(cx * span) - left, round(cy * span) - top))
                visible += 1

        limit = max(MIN_CACHED_CHUNKS, visible + 12)
        self._trim_ordered(self._chunk_cache, limit)
        self._trim_ordered(self._scaled_cache, limit)

    @staticmethod
    def _trim_ordered(cache, limit):
        while len(cache) > limit:
            cache.popitem(last=False)

    def _get_scaled_chunk(self, cx, cy, lod, size):
        key = (cx, cy)
        tile = self._scaled_cache.get(key)
        if tile is None:
            base = self._get_chunk(cx, cy, lod)
            tile = base if base.get_width() == size else pygame.transform.smoothscale(base, (size, size))
            self._scaled_cache[key] = tile
        else:
            self._scaled_cache.move_to_end(key)
            bkey = (cx, cy, lod)
            if bkey in self._chunk_cache:
                self._chunk_cache.move_to_end(bkey)
        return tile

    def _get_chunk(self, cx, cy, lod):
        key = (cx, cy, lod)
        chunk = self._chunk_cache.get(key)
        if chunk is None:
            chunk = self._build_chunk(cx, cy, lod)
            self._chunk_cache[key] = chunk
        else:
            self._chunk_cache.move_to_end(key)
        return chunk

    def _build_chunk(self, cx, cy, lod):
        """Чанк в уменьшенном виде: при lod=4 это 8x8 клеток вместо 32x32 (в 16 раз меньше расчётов шума)."""
        cells = CHUNK_SIZE // (CELL_SIZE * lod)
        cell_world = CELL_SIZE * lod
        surf = pygame.Surface((cells * CELL_SIZE, cells * CELL_SIZE))
        for j in range(cells):
            for i in range(cells):
                color = self.world.ground_color(cx * cells + i, cy * cells + j, cell_world)
                surf.fill(color, (i * CELL_SIZE, j * CELL_SIZE, CELL_SIZE, CELL_SIZE))

        if lod == 1:                         # на дальнем зуме декор всё равно меньше пикселя
            for deco in self.world.chunk_decorations(cx, cy):
                self._draw_decoration(surf, deco)
        return surf.convert()

    # ==========================================
    # ДЕКОР
    # ==========================================
    def _draw_decoration(self, surf, d):
        if d.kind == "flower":
            self._draw_flower(surf, d)
        elif d.kind == "stone":
            self._draw_stone(surf, d)
        elif d.kind == "bush":
            self._draw_bush(surf, d)
        elif d.kind == "tuft":
            self._draw_tuft(surf, d)

    @staticmethod
    def _draw_flower(surf, d):
        x, y = int(d.x), int(d.y)
        r = int(d.size)
        turn = (d.variant % 72)
        for k in range(5):
            a = math.radians(k * 72 + turn)
            px = int(round(x + math.cos(a) * r))
            py = int(round(y + math.sin(a) * r))
            pygame.draw.circle(surf, d.color, (px, py), max(2, int(r * 0.7)))
        pygame.draw.circle(surf, (250, 220, 60), (x, y), max(1, r // 2))

    @staticmethod
    def _draw_stone(surf, d):
        x, y = int(d.x), int(d.y)
        w = max(6, int(d.size * 2))
        h = max(5, int(d.size * 1.5) + d.variant % 3)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (x, y)
        pygame.draw.ellipse(surf, (45, 70, 45), rect.move(2, 3))          # тень
        pygame.draw.ellipse(surf, d.color, rect)
        pygame.draw.ellipse(surf, _shade(d.color, 0.7), rect, 1)          # контур
        hl = pygame.Rect(0, 0, max(2, w // 3), max(2, h // 3))
        hl.center = (x - w // 5, y - h // 5)
        pygame.draw.ellipse(surf, _shade(d.color, 1.25), hl)              # блик

    @staticmethod
    def _draw_bush(surf, d):
        x, y = int(d.x), int(d.y)
        r = max(4, int(d.size * 0.65))
        pygame.draw.circle(surf, _shade(d.color, 0.6), (x + 2, y + 3), r + 1)   # тень
        for ox, oy in ((-0.5, 0.3), (0.5, 0.2), (0.0, -0.5)):
            pygame.draw.circle(surf, d.color, (int(x + ox * r), int(y + oy * r)), r)
        pygame.draw.circle(surf, _shade(d.color, 1.3), (x - r // 3, y - r // 2), max(2, r // 2))
        if d.variant % 3 == 0:                                                  # ягоды
            for ox, oy in ((-3, -1), (2, 2), (3, -3)):
                pygame.draw.circle(surf, (200, 40, 50), (x + ox, y + oy), 2)

    @staticmethod
    def _draw_tuft(surf, d):
        x, y = int(d.x), int(d.y)
        s = d.size / 6.0
        flip = -1 if d.variant % 2 else 1
        for bx, by in ((-4, -6), (-1.5, -9), (1.5, -8), (4, -5)):
            pygame.draw.line(surf, d.color, (x, y),
                             (int(x + bx * s * flip), int(y + by * s)), 1)

    # ==========================================
    # ТАНК
    # ==========================================
    def _draw_tank(self, screen, camera, tank):
        ppm = self._ppm
        sx, sy = camera.world_to_screen(tank.x, tank.y)
        cx, cy = int(round(sx)), int(round(sy))

        spec = tank.spec
        hs, ts = spec.HULL_SCALE, spec.TURRET_SCALE
        bl = int(round(spec.BARREL_LEN_M / 0.25))          # длина ствола в шагах по 0.25 м (меньше вариантов в кэше)
        bt = int(round(spec.BARREL_THICK_M / 0.02))        # толщина в шагах по 2 см
        team = tank.team_color
        lp = int(tank.left_track_offset / tank.TRACK_STEP * TRACK_PHASES) % TRACK_PHASES
        rp = int(tank.right_track_offset / tank.TRACK_STEP * TRACK_PHASES) % TRACK_PHASES

        hull = self._get_hull(lp, rp, team)
        turret = self._get_turret(team)
        barrel = self._get_barrel(bl, bt)

        hull_rot = pygame.transform.rotozoom(hull, -tank.hull_angle, hs)
        turret_rot = pygame.transform.rotozoom(turret, -tank.turret_angle, ts)
        barrel_rot = pygame.transform.rotozoom(barrel, -tank.turret_angle, ts)

        # ствол — отдельный спрайт: его центр лежит на оси башни на расстоянии f от центра танка
        # (откат просто уменьшает f)
        a = math.radians(tank.turret_angle)
        f = (TURRET_FRONT_M + bl * 0.125 - 0.25 - tank.recoil_m) * ppm * ts
        hull_rect = hull_rot.get_rect(center=(cx, cy))
        turret_rect = turret_rot.get_rect(center=(cx, cy))
        barrel_rect = barrel_rot.get_rect(center=(round(cx + math.sin(a) * f), round(cy - math.cos(a) * f)))

        # --- тень: все силуэты в общий буфер непрозрачным чёрным, потом буфер целиком полупрозрачно ---
        hox, hoy = (round(v * ppm * hs) for v in SHADOW_HULL_M)
        tox, toy = (round(v * ppm * hs) for v in SHADOW_TURRET_M)
        sil_hull = pygame.transform.rotozoom(
            self._get_sil(("hull", lp, rp, team), hull), -tank.hull_angle, hs)
        sil_turret = pygame.transform.rotozoom(
            self._get_sil(("turret", team), turret), -tank.turret_angle, ts)
        sil_barrel = pygame.transform.rotozoom(
            self._get_sil(("barrel", bl, bt), barrel), -tank.turret_angle, ts)
        parts = (
            (sil_hull, sil_hull.get_rect(center=hull_rect.center).move(hox, hoy)),
            (sil_barrel, sil_barrel.get_rect(center=barrel_rect.center).move(tox, toy)),
            (sil_turret, sil_turret.get_rect(center=turret_rect.center).move(tox, toy)),
        )
        union = parts[0][1].unionall([r for _, r in parts[1:]])
        buf = self._ensure_shadow_buf(union.w, union.h)
        buf.fill((0, 0, 0, 0), (0, 0, union.w, union.h))
        for surf, rect in parts:
            buf.blit(surf, (rect.x - union.x, rect.y - union.y))
        screen.blit(buf, union.topleft, area=(0, 0, union.w, union.h))

        # --- сам танк: корпус, ствол (под башней), башня ---
        screen.blit(hull_rot, hull_rect)
        screen.blit(barrel_rot, barrel_rect)
        screen.blit(turret_rot, turret_rect)

    @staticmethod
    def _make_silhouette(surface):
        mask = pygame.mask.from_surface(surface)
        return mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))

    def _ensure_shadow_buf(self, w, h):
        """Буфер тени: пересоздаётся только если нужен больший размер."""
        need = max(w, h)
        if self._shadow_buf is None or self._shadow_buf.get_width() < need:
            size = (need + 63) // 64 * 64
            self._shadow_buf = pygame.Surface((size, size), pygame.SRCALPHA)
            self._shadow_buf.set_alpha(SHADOW_ALPHA)
        return self._shadow_buf

    @staticmethod
    def _trim_cache(cache, limit):
        """Не даёт кэшу расти бесконечно при перетаскивании ползунков."""
        while len(cache) > limit:
            cache.pop(next(iter(cache)))      # самый старый ключ

    def _get_sil(self, key, surface):
        sil = self._sil_cache.get(key)
        if sil is None:
            sil = self._make_silhouette(surface)
            self._sil_cache[key] = sil
            self._trim_cache(self._sil_cache, 120)
        return sil

    def _get_hull(self, lp, rp, team_color):
        key = (lp, rp, team_color)
        surf = self._hull_cache.get(key)
        if surf is None:
            surf = self._build_hull(lp, rp, team_color)
            self._hull_cache[key] = surf
            self._trim_cache(self._hull_cache, 40)
        return surf

    def _get_turret(self, team_color):
        surf = self._turret_cache.get(team_color)
        if surf is None:
            surf = self._build_turret(team_color)
            self._turret_cache[team_color] = surf
        return surf

    def _get_barrel(self, bl, bt):
        key = (bl, bt)
        surf = self._barrel_cache.get(key)
        if surf is None:
            surf = self._build_barrel(bl, bt)
            self._barrel_cache[key] = surf
            self._trim_cache(self._barrel_cache, 40)
        return surf

    @staticmethod
    def _draw_track(pen, x, phase):
        """Одна гусеница: лента + поперечные звенья, бегущие с фазой phase."""
        left = x - TRACK_W / 2
        pen.rect(TRACK_BODY, left, TRACK_TOP, TRACK_W, TRACK_LEN, r=0.22)

        pen.set_clip(left + 0.05, TRACK_TOP + 0.05, TRACK_W - 0.1, TRACK_LEN - 0.1)
        y = TRACK_TOP - TRACK_LINK_M + phase * TRACK_LINK_M / TRACK_PHASES
        while y < TRACK_TOP + TRACK_LEN:
            pen.line(TRACK_LINK, left + 0.07, y, left + TRACK_W - 0.07, y, 0.06)
            y += TRACK_LINK_M
        pen.clear_clip()

    def _build_hull(self, lp, rp, team_color):
        ppm = self._ppm
        size = 2 * math.ceil(HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS, 0.0, HULL_SHIFT_M)     # координаты корпуса: центр корпуса = (0, 0)

        # 1. Гусеницы (чуть выступают за нос и корму)
        self._draw_track(pen, -TRACK_X, lp)
        self._draw_track(pen, TRACK_X, rp)

        # 2. Корпус: короткий клин спереди, скошенные углы сзади
        pen.poly(HULL_MAIN, [(-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (1.35, 2.65),
                             (1.15, 2.9), (-1.15, 2.9), (-1.35, 2.65), (-1.35, -2.1)])

        # 3. Подкрылки (полки над гусеницами)
        pen.rect(HULL_DARK, 1.35, -2.1, 0.22, 4.75)
        pen.rect(HULL_DARK, -1.57, -2.1, 0.22, 4.75)

        # 4. Лобовая плита (светлее: обращена к свету) и палуба
        pen.poly(HULL_LIGHT, [(-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (-1.35, -2.1)])
        pen.rect(DECK, -1.25, -2.05, 2.50, 4.40, ow=1) if False else pen.rect(DECK, -1.25, -2.05, 2.50, 4.40)

        # 5. Погон башни: тёмное кольцо вокруг оси (контактная тень под башней)
        pen.ellipse(RING, 0.0, -HULL_SHIFT_M, 1.35, 1.35, outline=None)

        # 6. Люк механика-водителя
        pen.ellipse(HULL_DARK, 0.65, -1.65, 0.24, 0.24)

        # 7. МТО: решётка и жалюзи
        pen.rect(GRILL, -0.95, 1.00, 1.90, 1.20)
        for ly in (1.30, 1.55, 1.80, 2.05):
            pen.line(GRILL_LINE, -0.80, ly, 0.80, ly, 0.05)

        # 8. Кормовая плита и две полоски цвета игрока
        pen.rect(HULL_DARK, -1.15, 2.40, 2.30, 0.50)
        pen.rect(team_color, -0.85, 2.50, 0.60, 0.30)
        pen.rect(team_color, 0.25, 2.50, 0.60, 0.30)

        return pygame.transform.smoothscale(big, (size, size))

    def _build_turret(self, team_color):
        ppm = self._ppm
        size = 2 * math.ceil(TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)                        # центр спрайта = ось башни

        # 1. Шестиугольный корпус башни + светлая вставка поверх
        pen.poly(TURRET_MAIN, [(-0.70, -1.55), (0.70, -1.55), (1.30, 0.00),
                               (0.70, 1.65), (-0.70, 1.65), (-1.30, 0.00)])
        pen.poly(TURRET_LIGHT, [(-0.48, -1.05), (0.48, -1.05), (0.88, 0.00),
                                (0.48, 1.12), (-0.48, 1.12), (-0.88, 0.00)], outline=TURRET_DARK)

        # 2. Маска орудия: выступает вперёд из башни, ствол выходит из её торца
        pen.rect(TURRET_DARK, -0.55, -TURRET_FRONT_M, 1.10, 0.60, r=0.08)

        # 3. Люки: заряжающего (нейтральный) и командира (цвет игрока)
        pen.ellipse(TURRET_DARK, -0.45, 0.85, 0.24, 0.24)
        pen.ellipse(TURRET_DARK, 0.42, 0.30, 0.42, 0.42)
        pen.ellipse(team_color, 0.42, 0.30, 0.32, 0.32)

        return pygame.transform.smoothscale(big, (size, size))

    def _build_barrel(self, bl, bt):
        """Ствол: узкая вертикальная картинка (дульный срез сверху). Центр — середина видимой длины."""
        ppm = self._ppm
        length = bl * 0.25
        thick = bt * 0.02
        half = (length + 0.5) / 2.0                      # +0.5 м уходит под башню
        w = max(2, 2 * math.ceil((thick + 0.30) * ppm / 2.0))
        h = max(2, round(2.0 * half * ppm))
        big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)

        pen.rect(GUN, -thick / 2, -half, thick, 2.0 * half)                       # ствол
        pen.rect(GUN_LIGHT, -(thick + 0.08) / 2, -half + 0.35 * length,
                 thick + 0.08, 0.30, r=0.05)                                      # эжектор
        pen.rect(GUN_DARK, -(thick + 0.06) / 2, -half, thick + 0.06, 0.22)        # дульный срез

        return pygame.transform.smoothscale(big, (w, h))

    # ==========================================
    # ОТЛАДКА
    # ==========================================
    def _draw_debug(self, screen, lines):
        y = 8
        for text in lines:
            shadow = self.font.render(text, True, (0, 0, 0))
            label = self.font.render(text, True, (255, 255, 255))
            screen.blit(shadow, (11, y + 1))
            screen.blit(label, (10, y))
            y += 20