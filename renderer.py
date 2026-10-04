"""renderer.py — вся отрисовка: земля (чанки), декор, танк, отладка."""
import math
from collections import OrderedDict

import pygame

from core import CHUNK_SIZE, CELL_SIZE

# ---------- Рисовка танка ----------
SS = 2                                   # коэффициент сглаживания (рисуем в SS раз крупнее)
HULL_SURFACE_SIZE = (200, 200)           # итоговый размер заготовки корпуса
SHADOW_BUF_SIZE = 460                    # буфер тени (больше диагонали заготовки башни)
TURRET_FRONT = 35                        # от центра башни до передней плиты; ствол отсчитывается отсюда
SHADOW_ALPHA = 80
SHADOW_HULL_OFFSET = (5, 7)              # смещение тени корпуса на экране
SHADOW_TURRET_OFFSET = (7, 10)           # башня выше, поэтому тень дальше

OUTLINE = (38, 33, 28)                   # общий контур
TRACK_BODY = (58, 54, 49)                # лента гусеницы
TRACK_LINK = (118, 111, 100)             # звено трака

HULL_MAIN = (170, 160, 140)
HULL_LIGHT = (200, 191, 169)
HULL_DARK = (126, 117, 101)
DECK = (155, 146, 126)
GRILL = (72, 66, 58)
GRILL_LINE = (112, 104, 91)

TURRET_MAIN = (184, 174, 152)
TURRET_LIGHT = (210, 202, 182)
TURRET_DARK = (140, 131, 114)
HATCH = (172, 162, 142)

GUN = (112, 110, 105)
GUN_LIGHT = (150, 147, 140)

MIN_CACHED_CHUNKS = 40


def _shade(color, k):
    """Умножить цвет на коэффициент (k<1 темнее, k>1 светлее)."""
    return tuple(max(0, min(255, int(c * k))) for c in color)

def _rect(surf, color, x, y, w, h, outline=OUTLINE, ow=2, radius=0):
    """Прямоугольник (x, y — от центра танка) с контуром."""
    c = surf.get_width() // 2
    r = pygame.Rect(round(c + x * SS), round(c + y * SS), round(w * SS), round(h * SS))
    pygame.draw.rect(surf, color, r, border_radius=radius * SS)
    if outline:
        pygame.draw.rect(surf, outline, r, ow * SS, border_radius=radius * SS)

def _poly(surf, color, pts, outline=OUTLINE, ow=2):
    c = surf.get_width() // 2
    big = [(c + px * SS, c + py * SS) for px, py in pts]
    pygame.draw.polygon(surf, color, big)
    if outline:
        pygame.draw.polygon(surf, outline, big, ow * SS)

def _circle(surf, color, x, y, r, outline=OUTLINE, ow=1):
    c = surf.get_width() // 2
    pos = (round(c + x * SS), round(c + y * SS))
    pygame.draw.circle(surf, color, pos, round(r * SS))
    if outline:
        pygame.draw.circle(surf, outline, pos, round(r * SS), ow * SS)

def _line(surf, color, x1, y1, x2, y2, w=1):
    c = surf.get_width() // 2
    pygame.draw.line(surf, color, (c + x1 * SS, c + y1 * SS), (c + x2 * SS, c + y2 * SS), w * SS)


class Renderer:
    def __init__(self, world_generator):
        self.world = world_generator
        self.font = pygame.font.Font(None, 22)

        self._chunk_cache = OrderedDict()   # (cx, cy) -> Surface
        self._hull_cache = {}               # (фаза левой, фаза правой, цвет) -> Surface
        self._turret_cache = {}             # (цвет, длина ствола, толщина) -> Surface
        self._hull_sil_cache = {}           # цвет -> силуэт корпуса
        self._turret_sil_cache = {}         # ключ башни -> силуэт башни

        self._shadow_buf = None             # создаётся и растёт по мере надобности
        self._ensure_shadow_buf(SHADOW_BUF_SIZE)

    # ==========================================
    # ГЛАВНЫЙ МЕТОД
    # ==========================================
    def draw(self, screen, camera, tank, debug_lines=None, effects=None):
        self._draw_ground(screen, camera)
        self._draw_tank(screen, camera, tank)
        if effects is not None:
            effects.draw(screen, camera)
        if debug_lines:
            self._draw_debug(screen, debug_lines)

    # ==========================================
    # ЗЕМЛЯ И ЧАНКИ
    # ==========================================
    def _draw_ground(self, screen, camera):
        left, top = camera.top_left()
        width, height = screen.get_size()

        cx0 = left // CHUNK_SIZE
        cx1 = (left + width - 1) // CHUNK_SIZE
        cy0 = top // CHUNK_SIZE
        cy1 = (top + height - 1) // CHUNK_SIZE

        visible = 0
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                chunk = self._get_chunk(cx, cy)
                screen.blit(chunk, (cx * CHUNK_SIZE - left, cy * CHUNK_SIZE - top))
                visible += 1

        # выкидываем самые давно не использованные чанки
        limit = max(MIN_CACHED_CHUNKS, visible + 12)
        while len(self._chunk_cache) > limit:
            self._chunk_cache.popitem(last=False)

    def _get_chunk(self, cx, cy):
        key = (cx, cy)
        chunk = self._chunk_cache.get(key)
        if chunk is None:
            chunk = self._build_chunk(cx, cy)
            self._chunk_cache[key] = chunk
        else:
            self._chunk_cache.move_to_end(key)
        return chunk

    def _build_chunk(self, cx, cy):
        surf = pygame.Surface((CHUNK_SIZE, CHUNK_SIZE))
        cells = CHUNK_SIZE // CELL_SIZE
        for j in range(cells):
            for i in range(cells):
                color = self.world.ground_color(cx * cells + i, cy * cells + j)
                surf.fill(color, (i * CELL_SIZE, j * CELL_SIZE, CELL_SIZE, CELL_SIZE))

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
        sx, sy = camera.world_to_screen(tank.x, tank.y)
        center = (int(round(sx)), int(round(sy)))

        # --- параметры внешнего вида из спецификации (значения по умолчанию = эталон) ---
        spec = tank.spec
        hs = getattr(spec, "HULL_SCALE", 1.0)
        ts = getattr(spec, "TURRET_SCALE", 1.0)
        barrel_len = int(round(getattr(spec, "BARREL_LEN_PX", 100.0) / 4.0)) * 4   # шаг 4 px: меньше перестроек
        barrel_thick = int(round(getattr(spec, "BARREL_THICK_PX", 10.0)))
        recoil = int(round(tank.recoil_px / 2.0)) * 2      # шаг 2 px: мало вариантов в кэше
        tkey = (tank.team_color, barrel_len, barrel_thick, recoil)

        hull = self._get_hull_surface(tank)
        turret = self._get_turret_surface(tkey)
        hull_rot = pygame.transform.rotozoom(hull, -tank.hull_angle, hs)
        turret_rot = pygame.transform.rotozoom(turret, -tank.turret_angle, ts)

        # --- тень: сначала в буфер непрозрачным чёрным, потом весь буфер полупрозрачно ---
        sil_hull = self._get_hull_silhouette(tank.team_color, hull)
        sil_turret = self._get_turret_silhouette(tkey, turret)
        sil_hull_rot = pygame.transform.rotozoom(sil_hull, -tank.hull_angle, hs)
        sil_turret_rot = pygame.transform.rotozoom(sil_turret, -tank.turret_angle, ts)

        need = max(sil_hull_rot.get_width(), sil_hull_rot.get_height(),
                   sil_turret_rot.get_width(), sil_turret_rot.get_height()) + 2 * int(12 * hs) + 4
        buf = self._ensure_shadow_buf(need)
        buf.fill((0, 0, 0, 0))
        bc = buf.get_width() // 2
        hx, hy = round(SHADOW_HULL_OFFSET[0] * hs), round(SHADOW_HULL_OFFSET[1] * hs)
        tx, ty = round(SHADOW_TURRET_OFFSET[0] * hs), round(SHADOW_TURRET_OFFSET[1] * hs)
        buf.blit(sil_hull_rot, sil_hull_rot.get_rect(center=(bc + hx, bc + hy)))
        buf.blit(sil_turret_rot, sil_turret_rot.get_rect(center=(bc + tx, bc + ty)))
        screen.blit(buf, buf.get_rect(center=center))

        # --- сам танк ---
        screen.blit(hull_rot, hull_rot.get_rect(center=center))
        screen.blit(turret_rot, turret_rot.get_rect(center=center))

    @staticmethod
    def _make_silhouette(surface):
        mask = pygame.mask.from_surface(surface)
        return mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0))

    def _ensure_shadow_buf(self, size):
        """Буфер тени: пересоздаётся только если нужен больший размер."""
        if self._shadow_buf is None or self._shadow_buf.get_width() < size:
            size = (size + 63) // 64 * 64
            self._shadow_buf = pygame.Surface((size, size), pygame.SRCALPHA)
            self._shadow_buf.set_alpha(SHADOW_ALPHA)
        return self._shadow_buf

    @staticmethod
    def _trim_cache(cache, limit=64):
        """Не даёт кэшу башен расти бесконечно при перетаскивании ползунка."""
        while len(cache) > limit:
            cache.pop(next(iter(cache)))      # самый старый ключ

    def _get_hull_silhouette(self, team_color, hull):
        sil = self._hull_sil_cache.get(team_color)
        if sil is None:
            sil = self._make_silhouette(hull)
            self._hull_sil_cache[team_color] = sil
        return sil

    def _get_turret_silhouette(self, tkey, turret):
        sil = self._turret_sil_cache.get(tkey)
        if sil is None:
            sil = self._make_silhouette(turret)
            self._turret_sil_cache[tkey] = sil
            self._trim_cache(self._turret_sil_cache)
        return sil

    def _get_hull_surface(self, tank):
        """Корпус для текущей фазы гусениц и цвета команды (кэш)."""
        key = (int(tank.left_track_offset), int(tank.right_track_offset), tank.team_color)
        surf = self._hull_cache.get(key)
        if surf is None:
            surf = self._build_hull_surface(key[0], key[1], tank.team_color)
            self._hull_cache[key] = surf
        return surf

    def _get_turret_surface(self, tkey):
        """Башня для (цвет команды, длина ствола, толщина ствола) — кэш."""
        surf = self._turret_cache.get(tkey)
        if surf is None:
            surf = self._build_turret_surface(tkey)
            self._turret_cache[tkey] = surf
            self._trim_cache(self._turret_cache)
        return surf

    @staticmethod
    def _draw_track(surf, x, offset):
        """Одна гусеница: лента, звенья (бегут с фазой offset), опорные катки."""
        w, top, h = 22, -56, 112
        _rect(surf, TRACK_BODY, x, top, w, h, radius=7)

        # звенья рисуем только внутри ленты, чтобы не затирать контур
        c = surf.get_width() // 2
        clip = pygame.Rect(c + (x + 2) * SS, c + (top + 2) * SS, (w - 4) * SS, (h - 4) * SS)
        surf.set_clip(clip)
        y = -70 + offset
        while y < 62:
            _rect(surf, TRACK_LINK, x + 3, y, w - 6, 6, outline=None, radius=1)
            y += 10
        surf.set_clip(None)

    def _build_hull_surface(self, left_off, right_off, team_color):
        big = pygame.Surface((HULL_SURFACE_SIZE[0] * SS, HULL_SURFACE_SIZE[1] * SS), pygame.SRCALPHA)

        # 1. Гусеницы
        self._draw_track(big, -47, left_off)
        self._draw_track(big, 25, right_off)

        # 2. Силуэт корпуса
        _poly(big, HULL_MAIN, [(-26, -52), (26, -52), (32, -30), (32, 50), (-32, 50), (-32, -30)])

        # 3. Подкрылки (боковые полки над гусеницами)
        _rect(big, HULL_DARK, -32, -30, 8, 80)
        _rect(big, HULL_DARK, 24, -30, 8, 80)

        # 4. Палуба
        _rect(big, DECK, -24, -30, 48, 78, ow=1)

        # 5. Лобовая плита
        _poly(big, HULL_LIGHT, [(-24, -50), (24, -50), (30, -30), (-30, -30)])

        # 6. МТО: решётка и жалюзи
        _rect(big, GRILL, -20, 26, 40, 14, radius=2)
        for ly in (29, 32, 35, 38):
            _line(big, GRILL_LINE, -17, ly, 17, ly, 1)

        # 7. Кормовая плита и две полоски цвета команды (середина кормы)
        _rect(big, HULL_DARK, -22, 42, 44, 8, ow=2)
        _rect(big, team_color, -14, 44, 10, 4, ow=1)
        _rect(big, team_color, 4, 44, 10, 4, ow=1)

        return pygame.transform.smoothscale(big, HULL_SURFACE_SIZE)

    def _build_turret_surface(self, tkey):
        team_color, barrel_len, thick, recoil = tkey

        reach = TURRET_FRONT + barrel_len                  # вынос дульного среза от центра башни
        half = max(100, int(math.ceil(reach)) + 12)        # половина размера заготовки
        size = half * 2
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)

        # 1. Ствол: всё сдвигается на recoil вниз (в сторону башни), башня рисуется поверх и «съедает» его
        body_h = (reach - 6) - 24
        _rect(big, GUN, -thick / 2, -(reach - 6) + recoil, thick, body_h)
        ej_y = -(24 + 0.64 * (reach - 24)) + recoil
        _rect(big, GUN_LIGHT, -(thick + 4) / 2, ej_y, thick + 4, 8, radius=2)
        _rect(big, team_color, -(thick + 2) / 2, -reach + recoil, thick + 2, 8, radius=2)   # кончик ствола

        # 2. Корпус башни: симметричный шестиугольник
        turret = [(-15, -34), (15, -34), (29, 1), (15, 36), (-15, 36), (-29, 1)]
        _poly(big, TURRET_MAIN, turret)
        light = [(-10, -23), (10, -23), (19, 1), (10, 26), (-10, 26), (-19, 1)]
        _poly(big, TURRET_LIGHT, light, outline=TURRET_DARK, ow=1)

        # 3. Маска орудия (цвет команды)
        _rect(big, team_color, -12, -40, 24, 14, radius=3)

        # 4. Люк
        _circle(big, HATCH, 8, 8, 10, ow=2)

        return pygame.transform.smoothscale(big, (size, size))

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