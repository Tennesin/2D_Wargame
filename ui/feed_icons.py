"""ui/feed_icons.py — иконки ленты урона: снаряд, щит, таран («>>») и плюс с цветным свечением.
О танках и игре не знает: рисует по названию иконки и тону."""
from enum import Enum, auto

import pygame

from engine import COLOR_GOOD, COLOR_WARN, COLOR_BAD
from .upgrade_icons import make_upgrade_icon

SS = 4                       # рисуем в SS раз крупнее, затем smoothscale
ICON_PX = 28                 # сторона самой иконки
GLOW_PAD = 6                 # запас под свечение вокруг иконки
GLOW_SHRINK = 3              # во сколько раз уменьшаем перед растяжением: так получается размытие
GLOW_PASSES = 3              # сколько раз накладываем свечение (иначе оно слишком слабое)
BOX_PX = ICON_PX + 2 * GLOW_PAD      # сторона готовой картинки (иконка + свечение)

OUTLINE = (24, 26, 30)
STEEL = (190, 205, 225)
STEEL_DARK = (132, 150, 176)
LIGHT = (232, 236, 242)
PLUS_FILL = (120, 230, 120)

class FeedIcon(Enum):
    SHELL = auto()           # снаряд: удар игрока по технике
    SHIELD = auto()          # щит: удар по игроку
    RAM = auto()             # «>>»: таран
    PLUS = auto()            # плюс: лечение

class FeedTone(Enum):
    GOOD = auto()            # зелёный
    WARN = auto()            # жёлтый
    BAD = auto()             # красный

TONE_COLORS = {FeedTone.GOOD: COLOR_GOOD, FeedTone.WARN: COLOR_WARN, FeedTone.BAD: COLOR_BAD}

# ==========================================
# ИКОНКИ (нейтральные цвета: цвет событию даёт только свечение)
# ==========================================

def _shell_icon(size):
    """Снаряд остриём вверх-вправо (слева направо по диагонали)."""
    side = size * SS
    L = int(side * 1.35)                 # горизонтальный холст с запасом: после поворота углы обрежутся
    flat = pygame.Surface((L, L), pygame.SRCALPHA)
    cy = L / 2.0
    half = 0.11
    ow = SS

    body = pygame.Rect(round(0.03 * L), round(cy - half * L), round(0.55 * L), round(2 * half * L))
    pygame.draw.rect(flat, STEEL, body)
    pygame.draw.rect(flat, OUTLINE, body, ow)

    tip = [(0.58 * L, cy - half * L), (0.97 * L, cy), (0.58 * L, cy + half * L)]
    pygame.draw.polygon(flat, STEEL_DARK, tip)
    pygame.draw.polygon(flat, OUTLINE, tip, ow)

    band = pygame.Rect(round(0.36 * L), round(cy - half * L), round(0.06 * L), round(2 * half * L))
    pygame.draw.rect(flat, STEEL_DARK, band)
    pygame.draw.rect(flat, OUTLINE, band, ow)

    rot = pygame.transform.rotate(flat, 45)            # против часовой: остриё уходит вверх-вправо
    big = pygame.Surface((side, side), pygame.SRCALPHA)
    big.blit(rot, rot.get_rect(center=big.get_rect().center))
    return pygame.transform.smoothscale(big, (size, size))

def _shield_icon(size):
    return make_upgrade_icon("armor", (size, size))

def _ram_icon(size):
    """Два шеврона «>>»."""
    big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    u = size * SS / 34.0
    w, h, th, gap = 11 * u, 22 * u, 5 * u, 9 * u
    x0 = (size * SS - (w + gap)) / 2.0
    y0 = (size * SS - h) / 2.0
    chevron = [(0, 0), (th, 0), (w, h / 2.0), (th, h), (0, h), (w - th, h / 2.0)]
    for dx in (0, gap):
        poly = [(x0 + dx + px, y0 + py) for px, py in chevron]
        pygame.draw.polygon(big, LIGHT, poly)
        pygame.draw.polygon(big, OUTLINE, poly, SS)
    return pygame.transform.smoothscale(big, (size, size))

def _plus_icon(size):
    """Крест."""
    side = size * SS
    big = pygame.Surface((side, side), pygame.SRCALPHA)
    a, t = 0.40, 0.14
    pts = [(-t, -a), (t, -a), (t, -t), (a, -t), (a, t), (t, t),
           (t, a), (-t, a), (-t, t), (-a, t), (-a, -t), (-t, -t)]
    poly = [(side * (0.5 + x), side * (0.5 + y)) for x, y in pts]
    pygame.draw.polygon(big, PLUS_FILL, poly)
    pygame.draw.polygon(big, OUTLINE, poly, SS)
    return pygame.transform.smoothscale(big, (size, size))

_PAINTERS = {FeedIcon.SHELL: _shell_icon, FeedIcon.SHIELD: _shield_icon,
             FeedIcon.RAM: _ram_icon, FeedIcon.PLUS: _plus_icon}

# ==========================================
# СВЕЧЕНИЕ И СБОРКА
# ==========================================

def make_glow(icon, color, pad=GLOW_PAD, shrink=GLOW_SHRINK):
    """Размытое свечение по форме иконки: маска одним цветом, уменьшение и растяжение обратно.
    Цвет «пустых» пикселей тот же, чтобы края не темнели при размытии."""
    w, h = icon.get_size()
    size = (w + 2 * pad, h + 2 * pad)
    flat = pygame.mask.from_surface(icon).to_surface(setcolor=(*color, 255), unsetcolor=(*color, 0))
    glow = pygame.Surface(size, pygame.SRCALPHA)
    glow.fill((*color, 0))
    glow.blit(flat, (pad, pad))
    small = pygame.transform.smoothscale(glow, (max(1, size[0] // shrink), max(1, size[1] // shrink)))
    return pygame.transform.smoothscale(small, size)

def make_feed_icon(icon, tone):
    """Готовая картинка BOX_PX x BOX_PX: свечение цвета тона и иконка поверх."""
    base = _PAINTERS[icon](ICON_PX)
    glow = make_glow(base, TONE_COLORS[tone])
    out = pygame.Surface((BOX_PX, BOX_PX), pygame.SRCALPHA)
    for _ in range(GLOW_PASSES):
        out.blit(glow, (0, 0))
    out.blit(base, (GLOW_PAD, GLOW_PAD))
    return out