"""ui/damage_feed.py — невидимая зона справа от сводки танка: до трёх записей «иконка + число».
Новая запись выплывает справа и встаёт в верхний блок, старые опускаются ниже, из нижнего блока запись
пропадает мгновенно. Запись живёт не дольше LIFE_S. О танках и бое не знает; мышь не перехватывает."""
import math

import pygame

from engine import get_text, fmt_num, FONT_SIZE_TITLE
from .hud import MARGIN, WIDTH, HEIGHT
from .feed_icons import make_feed_icon, BOX_PX

SLOTS = 3
BLOCK_W = 130
BLOCK_H = BOX_PX                     # 40
BLOCK_GAP = 6
PITCH = BLOCK_H + BLOCK_GAP
ZONE_GAP = 12                        # зазор между сводкой и зоной
FEED_RIGHT = MARGIN + WIDTH + ZONE_GAP + BLOCK_W    # правая граница зоны (её читает occupied_corner)

LIFE_S = 5.0
FADE_IN_S = 0.25
FADE_OUT_S = 0.40
ENTER_DX = 90.0                      # откуда выплывает новая запись (px правее своего места)
SMOOTH = 12.0                        # чем больше, тем резвее запись догоняет своё место (1/с)

TEXT_COLOR = (235, 235, 235)
SHADOW_COLOR = (0, 0, 0)
TEXT_GAP = 4                         # зазор между иконкой и числом

def feed_zone(size):
    """Прямоугольник зоны для окна size: по вертикали по центру сводки танка."""
    w, h = size
    height = SLOTS * BLOCK_H + (SLOTS - 1) * BLOCK_GAP
    return pygame.Rect(MARGIN + WIDTH + ZONE_GAP,
                       h - MARGIN - HEIGHT + (HEIGHT - height) // 2, BLOCK_W, height)

class _Entry:
    __slots__ = ("surf", "slot", "row", "dx", "age")

    def __init__(self, surf):
        self.surf = surf
        self.slot = 0                # целевой блок (0 верхний)
        self.row = 0.0               # текущее положение по вертикали, в блоках (плавно)
        self.dx = ENTER_DX           # смещение вправо от своего места (плавно к нулю)
        self.age = 0.0

class DamageFeed:
    def __init__(self):
        self._entries = []           # от старых к новым
        self._icons = {}             # (иконка, тон) -> готовая картинка

    def _icon(self, icon, tone):
        key = (icon, tone)
        surf = self._icons.get(key)
        if surf is None:
            surf = self._icons[key] = make_feed_icon(icon, tone)
        return surf

    def _block(self, icon, tone, value):
        """Картинка записи целиком: иконка слева, число справа. Собирается один раз."""
        surf = pygame.Surface((BLOCK_W, BLOCK_H), pygame.SRCALPHA)
        surf.blit(self._icon(icon, tone), (0, 0))
        text = fmt_num(value)
        shadow = get_text(text, FONT_SIZE_TITLE, SHADOW_COLOR)
        label = get_text(text, FONT_SIZE_TITLE, TEXT_COLOR)
        pos = label.get_rect(midleft=(BOX_PX + TEXT_GAP, BLOCK_H // 2))
        surf.blit(shadow, pos.move(1, 1))
        surf.blit(label, pos)
        return surf

    def push(self, icon, tone, value):
        """Новая запись: остальные опускаются на блок ниже, вышедшая за нижний блок исчезает сразу."""
        for e in self._entries:
            e.slot += 1
        self._entries = [e for e in self._entries if e.slot < SLOTS]
        self._entries.append(_Entry(self._block(icon, tone, value)))

    def clear(self):
        self._entries.clear()

    def update(self, dt):
        if not self._entries:
            return
        k = 1.0 - math.exp(-SMOOTH * dt)
        for e in self._entries:
            e.age += dt
            e.row += (e.slot - e.row) * k
            e.dx += (0.0 - e.dx) * k
        self._entries = [e for e in self._entries if e.age < LIFE_S]

    @staticmethod
    def _alpha(age):
        if age < FADE_IN_S:
            k = age / FADE_IN_S
        elif age > LIFE_S - FADE_OUT_S:
            k = (LIFE_S - age) / FADE_OUT_S
        else:
            k = 1.0
        return max(0, min(255, round(255 * k)))

    def draw(self, screen):
        if not self._entries:
            return
        zone = feed_zone(screen.get_size())
        for e in self._entries:
            alpha = self._alpha(e.age)
            if alpha <= 0:
                continue
            e.surf.set_alpha(alpha)
            screen.blit(e.surf, (zone.x + round(e.dx), zone.y + round(e.row * PITCH)))