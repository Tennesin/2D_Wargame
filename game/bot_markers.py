"""game/bot_markers.py — синие треугольники-указатели на ботов (на экране и у края экрана)."""
import math
import pygame

from .settings import BOT_MARKERS_ENABLED
from engine import PX_PER_M, get_text, clamp, FONT_SIZE_LABEL, hp_color

EDGE_INSET = 24              # отступ указателя от края экрана, px
EDGE_SIZE = 13               # размер треугольника у края
ON_SIZE = 9                  # размер треугольника над видимым ботом
FILL = (70, 150, 255)
OUTLINE = (10, 20, 50)
TEXT = (150, 195, 255)

BAR_W = 36                   # ширина полоски HP, px
BAR_H = 5                    # высота полоски HP, px
BAR_GAP = 4                  # зазор между остриём треугольника и полоской
BAR_BG = (30, 33, 40)
BAR_BORDER = (10, 20, 50)

class BotMarkers:
    def __init__(self, fleet, camera):
        self.fleet = fleet
        self.camera = camera

    def draw(self, screen):
        if not BOT_MARKERS_ENABLED:
            return
        w, h = screen.get_size()
        cx, cy = w / 2.0, h / 2.0
        hx, hy = cx - EDGE_INSET, cy - EDGE_INSET
        zoom = self.camera.zoom
        player = self.fleet.player

        for bot in self.fleet.bots:
            t = bot.tank
            if not t.alive:
                continue
            sx, sy = self.camera.world_to_screen(t.x, t.y)

            if abs(sx - cx) <= hx and abs(sy - cy) <= hy:
                # бот на экране: треугольник над танком, остриём вниз
                lift = (t.spec.COLLISION_HALF_L_PX + 60.0) * zoom + 10.0
                mx, my = sx, sy - lift
                self._triangle(screen, mx, my, math.pi / 2.0, ON_SIZE)
                self._hp_bar(screen, mx, my + ON_SIZE + BAR_GAP, t)   # полоска под остриём
                continue

            # бот за экраном: ставим указатель на край, остриё смотрит на бота
            dx, dy = sx - cx, sy - cy
            kx = hx / abs(dx) if dx else float("inf")
            ky = hy / abs(dy) if dy else float("inf")
            k = min(kx, ky)
            px, py = cx + dx * k, cy + dy * k
            ang = math.atan2(dy, dx)
            self._triangle(screen, px, py, ang, EDGE_SIZE)

            # подпись с дистанцией от танка игрока, чуть глубже внутрь экрана
            dist_m = math.hypot(t.x - player.x, t.y - player.y) / PX_PER_M
            label = get_text(f"{dist_m:.0f} м", FONT_SIZE_LABEL, TEXT)
            off = EDGE_SIZE + 16
            lx = px - math.cos(ang) * off
            ly = py - math.sin(ang) * off
            rect = label.get_rect(center=(round(lx), round(ly)))
            rect.clamp_ip(screen.get_rect())
            screen.blit(label, rect)

    @staticmethod
    def _triangle(screen, x, y, ang, size):
        """Равнобедренный треугольник с остриём в направлении ang (радианы, экранные оси)."""
        ux, uy = math.cos(ang), math.sin(ang)
        vx, vy = -uy, ux
        tip = (x + ux * size, y + uy * size)
        b1 = (x - ux * size * 0.6 + vx * size * 0.7, y - uy * size * 0.6 + vy * size * 0.7)
        b2 = (x - ux * size * 0.6 - vx * size * 0.7, y - uy * size * 0.6 - vy * size * 0.7)
        pygame.draw.polygon(screen, FILL, (tip, b1, b2))
        pygame.draw.polygon(screen, OUTLINE, (tip, b1, b2), 2)

    @staticmethod
    def _hp_bar(screen, cx, top, tank):
        """Полоска здоровья: центр по cx, верхний край на top. Без цифр, только заполнение."""
        frac = clamp(tank.hp / tank.max_hp, 0.0, 1.0) if tank.max_hp > 0 else 0.0
        color = hp_color(frac)

        bar = pygame.Rect(0, 0, BAR_W, BAR_H)
        bar.midtop = (round(cx), round(top))
        pygame.draw.rect(screen, BAR_BG, bar)
        if frac > 0.0:
            fill = pygame.Rect(bar.x, bar.y, max(1, round(BAR_W * frac)), BAR_H)
            pygame.draw.rect(screen, color, fill)
        pygame.draw.rect(screen, BAR_BORDER, bar.inflate(2, 2), 1)