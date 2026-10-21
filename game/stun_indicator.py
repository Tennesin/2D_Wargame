"""game/stun_indicator.py — тонкая жёлтая линия над оглушённой техникой: сколько секунд осталось."""
import pygame

from engine import clamp

LINE_W = 46               # ширина полной линии, px
LINE_H = 3
LIFT_EXTRA_PX = 22        # на сколько выше синего указателя бота (см. bot_markers.py)
COLOR = (255, 220, 60)
BACK = (30, 26, 10)

class StunIndicator:
    def __init__(self, fleet, camera):
        self.fleet = fleet
        self.camera = camera

    def draw(self, screen):
        zoom = self.camera.zoom
        w, h = screen.get_size()
        for t in self.fleet.vehicles:
            if not t.alive or t.stun_left <= 0.0:
                continue
            sx, sy = self.camera.world_to_screen(t.x, t.y)
            lift = (t.spec.COLLISION_HALF_L_PX + 60.0) * zoom + 10.0     # та же высота, что у маркера бота
            y = sy - lift - LIFT_EXTRA_PX
            if not (-LINE_W <= sx <= w + LINE_W and -LINE_H <= y <= h + LINE_H):
                continue
            frac = clamp(t.stun_left / t.stun_total, 0.0, 1.0) if t.stun_total > 0.0 else 0.0
            full = pygame.Rect(0, 0, LINE_W, LINE_H)
            full.center = (round(sx), round(y))
            pygame.draw.rect(screen, BACK, full.inflate(2, 2))           # тёмная подложка для читаемости
            bar = pygame.Rect(0, 0, max(1, round(LINE_W * frac)), LINE_H)
            bar.midleft = full.midleft
            pygame.draw.rect(screen, COLOR, bar)