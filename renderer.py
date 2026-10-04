"""renderer.py — вся отрисовка: земля (чанки), декор, танк, отладка."""
import math
from collections import OrderedDict

import pygame

from core import CHUNK_SIZE, CELL_SIZE

# ---------- Палитра танка ----------
TRACK_COLOR = (45, 45, 45)
TRACK_LINE_COLOR = (20, 20, 20)
FRONT_ARMOR_COLOR = (115, 140, 60)
SIDE_ARMOR_COLOR = (85, 107, 47)
REAR_ARMOR_COLOR = (65, 80, 35)
DECK_COLOR = (95, 118, 52)
ARMOR_OUTLINE_COLOR = (35, 48, 18)
ENGINE_GRILL_COLOR = (30, 40, 20)
TURRET_COLOR = (120, 150, 40)
GUN_COLOR = (100, 100, 100)
HATCH_COLOR = (60, 80, 30)

TANK_SURFACE_SIZE = (200, 200)
MIN_CACHED_CHUNKS = 40


def _shade(color, k):
    """Умножить цвет на коэффициент (k<1 темнее, k>1 светлее)."""
    return tuple(max(0, min(255, int(c * k))) for c in color)


class Renderer:
    def __init__(self, world_generator):
        self.world = world_generator
        self.font = pygame.font.Font(None, 22)

        self._chunk_cache = OrderedDict()   # (cx, cy) -> Surface
        self._hull_cache = {}               # (шаг левой, шаг правой) -> Surface
        self.turret_surface = self._build_turret_surface()

    # ==========================================
    # ГЛАВНЫЙ МЕТОД
    # ==========================================
    def draw(self, screen, camera, tank, debug_lines=None):
        self._draw_ground(screen, camera)
        self._draw_tank(screen, camera, tank)
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

        hull = self._get_hull_surface(tank)
        rotated_hull = pygame.transform.rotate(hull, -tank.hull_angle)
        screen.blit(rotated_hull, rotated_hull.get_rect(center=center))

        rotated_turret = pygame.transform.rotate(self.turret_surface, -tank.turret_angle)
        screen.blit(rotated_turret, rotated_turret.get_rect(center=center))

    def _get_hull_surface(self, tank):
        """Корпус для текущей фазы гусениц. Фаз всего 10x10, поэтому кэшируем."""
        key = (int(tank.left_track_offset), int(tank.right_track_offset))
        surf = self._hull_cache.get(key)
        if surf is None:
            surf = self._build_hull_surface(key[0], key[1], tank.TRACK_STEP)
            self._hull_cache[key] = surf
        return surf

    @staticmethod
    def _draw_track_lines(surface, x1, x2, cy, offset, step):
        start_y = cy - 55 - int(step)
        end_y = cy + 55 + int(step)
        y = start_y + offset
        while y < end_y:
            if cy - 53 <= y <= cy + 53:
                pygame.draw.line(surface, TRACK_LINE_COLOR, (x1, int(y)), (x2, int(y)), 2)
            y += step

    def _build_hull_surface(self, left_off, right_off, track_step):
        surface = pygame.Surface(TANK_SURFACE_SIZE, pygame.SRCALPHA)
        cx, cy = TANK_SURFACE_SIZE[0] // 2, TANK_SURFACE_SIZE[1] // 2

        # 1. Гусеницы
        pygame.draw.rect(surface, TRACK_COLOR, (cx - 45, cy - 55, 20, 110))
        pygame.draw.rect(surface, TRACK_COLOR, (cx + 25, cy - 55, 20, 110))
        self._draw_track_lines(surface, cx - 45, cx - 26, cy, left_off, track_step)
        self._draw_track_lines(surface, cx + 25, cx + 44, cy, right_off, track_step)

        # 2. Палуба
        pygame.draw.rect(surface, DECK_COLOR, (cx - 20, cy - 25, 40, 50))

        # 3. Лобовая броня
        front = [(cx - 30, cy - 25), (cx - 24, cy - 50), (cx + 24, cy - 50), (cx + 30, cy - 25)]
        pygame.draw.polygon(surface, FRONT_ARMOR_COLOR, front)
        pygame.draw.polygon(surface, ARMOR_OUTLINE_COLOR, front, 2)

        # 4. Борта
        for rect in ((cx - 30, cy - 25, 10, 75), (cx + 20, cy - 25, 10, 75)):
            pygame.draw.rect(surface, SIDE_ARMOR_COLOR, rect)
            pygame.draw.rect(surface, ARMOR_OUTLINE_COLOR, rect, 2)

        # 5. Корма и жалюзи МТО
        rear = (cx - 20, cy + 25, 40, 25)
        pygame.draw.rect(surface, REAR_ARMOR_COLOR, rear)
        pygame.draw.rect(surface, ARMOR_OUTLINE_COLOR, rear, 2)
        pygame.draw.rect(surface, ENGINE_GRILL_COLOR, (cx - 15, cy + 30, 12, 12))
        pygame.draw.rect(surface, ENGINE_GRILL_COLOR, (cx + 3, cy + 30, 12, 12))
        for y_line in range(cy + 33, cy + 40, 3):
            pygame.draw.line(surface, (15, 20, 10), (cx - 14, y_line), (cx - 4, y_line), 1)
            pygame.draw.line(surface, (15, 20, 10), (cx + 4, y_line), (cx + 14, y_line), 1)
        return surface

    @staticmethod
    def _build_turret_surface():
        surface = pygame.Surface(TANK_SURFACE_SIZE, pygame.SRCALPHA)
        cx, cy = TANK_SURFACE_SIZE[0] // 2, TANK_SURFACE_SIZE[1] // 2

        pygame.draw.rect(surface, GUN_COLOR, (cx - 5, cy - 90, 10, 70))
        pygame.draw.rect(surface, (70, 70, 70), (cx - 7, cy - 95, 14, 15))

        turret = [(cx - 16, cy - 25), (cx + 16, cy - 25), (cx + 28, cy + 25), (cx - 28, cy + 25)]
        pygame.draw.polygon(surface, TURRET_COLOR, turret)
        pygame.draw.polygon(surface, ARMOR_OUTLINE_COLOR, turret, 2)

        pygame.draw.circle(surface, HATCH_COLOR, (cx, cy + 5), 8)
        pygame.draw.circle(surface, ARMOR_OUTLINE_COLOR, (cx, cy + 5), 8, 1)
        return surface

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