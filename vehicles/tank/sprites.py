"""tank/sprites.py — отрисовка танка: корпус, гусеницы, башня, ствол, тень.
Все размеры здесь в МЕТРАХ эталонного спрайта (x вправо, y вниз, перед = -y)."""
import math

import pygame

from .params import (TURRET_FRONT_M, TRACK_LINK_M, TRACK_OFFSET_M,
                     BARREL_LEN_STEP_M, BARREL_THICK_STEP_M, BARREL_HIDDEN_M)
from engine import LRUCache, SHADOW_ALPHA, heading_vector

# ==========================================
# 1. КОНСТАНТЫ РИСОВКИ
# ==========================================
SS = 2                                   # суперсэмплинг: рисуем в SS раз крупнее, затем smoothscale
OUTLINE_W = SS                           # толщина контура ≈ 1 px на экране при любом зуме
TRACK_PHASES = 6                         # сколько фаз анимации у гусеницы
HULL_SHIFT_M = 0.3                       # корпус сдвинут назад: ось башни = центр спрайта = центр танка
HULL_HALF_M = 3.7                        # половина стороны квадратной заготовки корпуса, м
TURRET_HALF_M = 2.1                      # половина стороны заготовки башни (без ствола), м
TRACK_X = TRACK_OFFSET_M                 # центр гусеницы от оси, м
TRACK_W = 0.75
TRACK_TOP = -3.1                         # передний край гусеницы (в координатах корпуса)
TRACK_LEN = 6.3

SHADOW_HULL_M = (0.25, 0.35)             # смещение тени корпуса, м
SHADOW_TURRET_M = (0.40, 0.55)           # башня выше, поэтому тень дальше

PAINT_K = 0.55                           # насколько сильно корпус и башня подкрашиваются цветом команды

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

def _paint(color, paint):
    """Подмешивает цвет команды к цвету детали. paint=None: деталь остаётся как есть."""
    if paint is None:
        return color
    return tuple(int(c + (p - c) * PAINT_K) for c, p in zip(color, paint))

# ==========================================
# 2. «РУЧКА» ДЛЯ РИСОВАНИЯ В МЕТРАХ
# ==========================================
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

# ==========================================
# 3. ОТРИСОВЩИК ТАНКА
# ==========================================

class TankRenderer:
    def __init__(self):
        self._ppm = 0.0
        self._hull_cache = LRUCache(120)  # (фаза левой, фаза правой, подкраска) -> Surface
        self._turret_cache = LRUCache(16)  # (цвет маски, подкраска) -> Surface
        self._barrel_cache = LRUCache(40)  # (длина, толщина) -> Surface
        self._sil_cache = LRUCache(120)  # ключ -> силуэт для тени
        self._shadow_buf = None

    def set_zoom(self, ppm):
        """Вызывается при смене зума: запоминает масштаб и сбрасывает кэши спрайтов."""
        self._ppm = ppm
        for cache in (self._hull_cache, self._turret_cache, self._barrel_cache, self._sil_cache):
            cache.clear()

    # ---------- главный метод ----------
    def draw(self, screen, camera, tank):
        ppm = self._ppm
        sx, sy = camera.world_to_screen(tank.x, tank.y)
        cx, cy = int(round(sx)), int(round(sy))

        spec = tank.spec
        hs, ts = spec.HULL_SCALE, spec.TURRET_SCALE
        bl = int(round(spec.BARREL_LEN_M / BARREL_LEN_STEP_M))  # длина ствола в шагах
        bt = int(round(spec.BARREL_THICK_M / BARREL_THICK_STEP_M))  # толщина в шагах
        team = tank.team_color
        paint = None if tank.team == "player" else team          # боты красятся цветом команды
        lp = int(tank.left_track_offset / tank.TRACK_STEP * TRACK_PHASES) % TRACK_PHASES
        rp = int(tank.right_track_offset / tank.TRACK_STEP * TRACK_PHASES) % TRACK_PHASES

        hull = self._get_hull(lp, rp, paint)
        turret = self._get_turret(team, paint)
        barrel = self._get_barrel(bl, bt)

        hull_rot = pygame.transform.rotozoom(hull, -tank.hull_angle, hs)
        turret_rot = pygame.transform.rotozoom(turret, -tank.turret_angle, ts)
        barrel_rot = pygame.transform.rotozoom(barrel, -tank.turret_angle, ts)

        # ствол — отдельный спрайт
        fx, fy = heading_vector(tank.turret_angle)
        f = (TURRET_FRONT_M + bl * BARREL_LEN_STEP_M / 2.0 - BARREL_HIDDEN_M / 2.0 - tank.recoil_m) * ppm * ts
        hull_rect = hull_rot.get_rect(center=(cx, cy))
        turret_rect = turret_rot.get_rect(center=(cx, cy))
        barrel_rect = barrel_rot.get_rect(center=(round(cx + fx * f), round(cy + fy * f)))

        # --- тень: все силуэты в общий буфер непрозрачным чёрным, потом буфер целиком полупрозрачно ---
        # форма у окрашенных и обычных деталей одинаковая, поэтому силуэты кэшируются без учёта краски
        hox, hoy = (round(v * ppm * hs) for v in SHADOW_HULL_M)
        tox, toy = (round(v * ppm * ts) for v in SHADOW_TURRET_M)
        sil_hull = pygame.transform.rotozoom(
            self._get_sil(("hull", lp, rp), hull), -tank.hull_angle, hs)
        sil_turret = pygame.transform.rotozoom(
            self._get_sil(("turret",), turret), -tank.turret_angle, ts)
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

    # ---------- тень и кэши ----------
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

    def _get_sil(self, key, surface):
        return self._sil_cache.get_or_build(key, lambda: self._make_silhouette(surface))

    def _get_hull(self, lp, rp, paint):
        return self._hull_cache.get_or_build((lp, rp, paint), lambda: self._build_hull(lp, rp, paint))

    def _get_turret(self, team_color, paint):
        return self._turret_cache.get_or_build((team_color, paint),
                                               lambda: self._build_turret(team_color, paint))

    def _get_barrel(self, bl, bt):
        return self._barrel_cache.get_or_build((bl, bt), lambda: self._build_barrel(bl, bt))

    # ---------- построение спрайтов ----------
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

    def _build_hull(self, lp, rp, paint):
        ppm = self._ppm
        size = 2 * math.ceil(HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS, 0.0, HULL_SHIFT_M)     # координаты корпуса: центр корпуса = (0, 0)

        hull_main = _paint(HULL_MAIN, paint)
        hull_light = _paint(HULL_LIGHT, paint)
        hull_dark = _paint(HULL_DARK, paint)
        deck = _paint(DECK, paint)

        # 1. Гусеницы (чуть выступают за нос и корму)
        self._draw_track(pen, -TRACK_X, lp)
        self._draw_track(pen, TRACK_X, rp)

        # 2. Корпус: короткий клин спереди, скошенные углы сзади
        pen.poly(hull_main, [(-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (1.35, 2.65),
                             (1.15, 2.9), (-1.15, 2.9), (-1.35, 2.65), (-1.35, -2.1)])

        # 3. Подкрылки (полки над гусеницами)
        pen.rect(hull_dark, 1.35, -2.1, 0.22, 4.75)
        pen.rect(hull_dark, -1.57, -2.1, 0.22, 4.75)

        # 4. Лобовая плита (светлее: обращена к свету) и палуба
        pen.poly(hull_light, [(-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (-1.35, -2.1)])
        pen.rect(deck, -1.25, -2.05, 2.50, 4.40)

        # 5. Погон башни: тёмное кольцо вокруг оси (контактная тень под башней)
        pen.ellipse(_paint(RING, paint), 0.0, -HULL_SHIFT_M, 1.35, 1.35, outline=None)

        # 6. Люк механика-водителя
        pen.ellipse(hull_dark, 0.65, -1.65, 0.24, 0.24)

        # 7. МТО: решётка и жалюзи
        pen.rect(GRILL, -0.95, 1.00, 1.90, 1.20)
        for ly in (1.30, 1.55, 1.80, 2.05):
            pen.line(GRILL_LINE, -0.80, ly, 0.80, ly, 0.05)

        # 8. Кормовая плита
        pen.rect(hull_dark, -1.15, 2.40, 2.30, 0.50)

        return pygame.transform.smoothscale(big, (size, size))

    def _build_turret(self, team_color, paint):
        ppm = self._ppm
        size = 2 * math.ceil(TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)                        # центр спрайта = ось башни

        turret_main = _paint(TURRET_MAIN, paint)
        turret_light = _paint(TURRET_LIGHT, paint)
        turret_dark = _paint(TURRET_DARK, paint)

        # 1. Шестиугольный корпус башни + светлая вставка поверх
        pen.poly(turret_main, [(-0.70, -1.55), (0.70, -1.55), (1.30, 0.00),
                               (0.70, 1.65), (-0.70, 1.65), (-1.30, 0.00)])
        pen.poly(turret_light, [(-0.48, -1.05), (0.48, -1.05), (0.88, 0.00),
                                (0.48, 1.12), (-0.48, 1.12), (-0.88, 0.00)], outline=turret_dark)

        # 2. Маска орудия: выступает вперёд из башни, ствол выходит из её торца
        pen.rect(team_color, -0.55, -TURRET_FRONT_M, 1.10, 0.60, r=0.08)

        # 3. Люк командира
        pen.ellipse(turret_dark, 0.42, 0.30, 0.42, 0.42)
        pen.ellipse(team_color, 0.42, 0.30, 0.32, 0.32)

        return pygame.transform.smoothscale(big, (size, size))

    def _build_barrel(self, bl, bt):
        """Ствол: узкая вертикальная картинка (дульный срез сверху). Центр — середина видимой длины."""
        ppm = self._ppm
        length = bl * BARREL_LEN_STEP_M
        thick = bt * BARREL_THICK_STEP_M
        half = (length + BARREL_HIDDEN_M) / 2.0  # часть уходит под башню
        w = max(2, 2 * math.ceil((thick + 0.30) * ppm / 2.0))
        h = max(2, round(2.0 * half * ppm))
        big = pygame.Surface((w * SS, h * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)

        pen.rect(GUN, -thick / 2, -half, thick, 2.0 * half)                       # ствол
        pen.rect(GUN_LIGHT, -(thick + 0.08) / 2, -half + 0.35 * length,
                 thick + 0.08, 0.30, r=0.05)                                      # эжектор
        pen.rect(GUN_DARK, -(thick + 0.06) / 2, -half, thick + 0.06, 0.22)        # дульный срез

        return pygame.transform.smoothscale(big, (w, h))