"""ui/plate.py — полупрозрачная плашка под содержимое сцен, у которых за спиной движущийся фон."""
import pygame

from engine import AlphaLayer
from .theme import BG_COLOR, PANEL_BORDER

_layer = AlphaLayer()

def draw_plate(screen, rect, alpha=205, radius=10):
    """Тёмная плашка с рамкой: текст на ней читается на любом фоне."""
    rect = pygame.Rect(rect).clip(screen.get_rect())
    if rect.w <= 0 or rect.h <= 0:
        return
    layer = _layer.begin(rect.size)
    pygame.draw.rect(layer, (*BG_COLOR, alpha), layer.get_rect(), border_radius=radius)
    pygame.draw.rect(layer, PANEL_BORDER, layer.get_rect(), 1, border_radius=radius)
    screen.blit(layer, rect.topleft)