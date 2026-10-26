"""ui/minimap.py — квадратная рамка с превью карты. Картинку приносят снаружи, сам виджет карту не строит."""
import pygame

from engine import get_text, FONT_SIZE_LABEL
from .theme import SLIDER_BG_COLOR, PANEL_BORDER, TEXT_DIM

class MiniMap:
    def __init__(self, placeholder="Нет превью"):
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.placeholder = placeholder
        self._src = None
        self._scaled = None
        self._scaled_size = None

    def layout(self, x, y, side):
        self.rect = pygame.Rect(x, y, side, side)

    def set_image(self, surface):
        """surface: готовая картинка (32 бита) или None: показывается заглушка."""
        self._src = surface
        self._scaled = None
        self._scaled_size = None

    def _fit(self):
        iw, ih = self._src.get_size()
        inner = self.rect.inflate(-6, -6)
        k = min(inner.w / iw, inner.h / ih)
        return max(1, int(iw * k)), max(1, int(ih * k))

    def draw(self, surface, mouse_pos):
        pygame.draw.rect(surface, SLIDER_BG_COLOR, self.rect, border_radius=4)
        if self._src is None:
            txt = get_text(self.placeholder, FONT_SIZE_LABEL, TEXT_DIM)
            surface.blit(txt, txt.get_rect(center=self.rect.center))
        else:
            size = self._fit()
            if self._scaled is None or self._scaled_size != size:
                self._scaled = pygame.transform.smoothscale(self._src, size)
                self._scaled_size = size
            surface.blit(self._scaled, self._scaled.get_rect(center=self.rect.center))
        pygame.draw.rect(surface, PANEL_BORDER, self.rect, 1, border_radius=4)