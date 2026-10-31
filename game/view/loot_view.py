"""game/view/loot_view.py — рисование добычи на земле: обломки с кольцом удержания."""
import math

import pygame

from engine import AlphaLayer
from ..match.loot.params import WRECK_FADE_S

BODY = (52, 48, 44)
SCORCH = (30, 27, 24)
TURRET = (66, 60, 54)
EDGE = (22, 20, 18)
HEAL = (110, 220, 110)
PAD = 10                     # запас вокруг обломков в слое, px экрана

class LootView:
    def __init__(self, loot):
        self.loot = loot
        self._alpha = AlphaLayer()

    def draw_ground(self, screen, camera):
        """Передаётся в Renderer.draw как ground_layer."""
        z = camera.zoom
        view = screen.get_rect()
        for w in self.loot.wrecks:
            sx, sy = camera.world_to_screen(w.x, w.y)
            r = w.extent * z
            if (sx + r + PAD < view.left or sx - r - PAD > view.right
                    or sy + r + PAD < view.top or sy - r - PAD > view.bottom):
                continue
            self._draw_wreck(screen, w, sx, sy, z, r)

    def _draw_wreck(self, screen, w, sx, sy, z, r):
        side = int(2 * (r + PAD)) + 2
        area = pygame.Rect(round(sx) - side // 2, round(sy) - side // 2, side, side).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        alpha = 255 if w.life >= WRECK_FADE_S else max(0, int(255 * w.life / WRECK_FADE_S))
        ox, oy = sx - area.x, sy - area.y                    # центр обломков в координатах слоя

        def pt(p):
            return ox + p[0] * z, oy + p[1] * z

        body = [pt(p) for p in w.body]
        layer = self._alpha.begin(area.size)
        pygame.draw.polygon(layer, (*BODY, alpha), body)
        pygame.draw.polygon(layer, (*SCORCH, alpha), [pt(p) for p in w.scorch])
        tx, ty = pt(w.turret_pos)
        center = (round(tx), round(ty))
        tr = max(2, round(w.turret_r * z))
        pygame.draw.circle(layer, (*TURRET, alpha), center, tr)
        pygame.draw.circle(layer, (*w.color, alpha), center, tr, min(tr, 2))   # кольцо цвета архетипа
        pygame.draw.polygon(layer, (*EDGE, alpha), body, 1)

        arm = max(4, round(tr * 0.7))                        # знак «+»: здесь можно подлечиться
        cx, cy = round(ox), round(oy)
        pygame.draw.line(layer, (*HEAL, alpha), (cx - arm, cy), (cx + arm, cy), 2)
        pygame.draw.line(layer, (*HEAL, alpha), (cx, cy - arm), (cx, cy + arm), 2)

        if w.hold > 0.0:                                     # дуга удержания по часовой стрелке... от верха
            rect = pygame.Rect(round(ox - r), round(oy - r), round(2 * r), round(2 * r))
            stop = math.pi / 2 + 2.0 * math.pi * w.hold_frac
            pygame.draw.arc(layer, (*HEAL, 255), rect, math.pi / 2, stop, 4)
        screen.blit(layer, area.topleft)