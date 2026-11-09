"""ui/palette.py — левая колонка выбора: прокручиваемый список «иконка + подпись», один пункт выбран.
Слой интерфейса (covers, handle_event, cancel_drag). О деталях и танках не знает."""
import pygame

from engine import get_text, FONT_SIZE_HEADER, FONT_SIZE_LABEL
from .plate import draw_plate
from .theme import BUTTON_COLORS, SLIDER_FILL_COLOR, TEXT_COLOR
from .widgets import ScrollArea

ROW_H = 48
PAD = 8
TITLE_H = 34
ICON_W = 40

class PartPalette:
    def __init__(self, title="Детали"):
        self.title = title
        self.visible = False
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.items = []                 # [(ключ, подпись, иконка или None)]
        self.selected = None
        self.on_pick = None             # колбэк(ключ или None)
        self.scroll = ScrollArea()
        self._list = pygame.Rect(0, 0, 10, 10)

    # ---------- данные и раскладка ----------
    def set_items(self, items):
        self.items = list(items)
        if self.selected not in [key for key, _, _ in self.items]:
            self.selected = None
        self._bounds()

    def set_selected(self, key):
        self.selected = key

    def layout(self, rect):
        rect = pygame.Rect(rect)
        if rect != self.rect:
            self.rect = rect
            self._list = pygame.Rect(rect.x + PAD, rect.y + TITLE_H, rect.w - 2 * PAD,
                                     max(0, rect.h - TITLE_H - PAD))
            self._bounds()

    def _bounds(self):
        self.scroll.update_bounds(len(self.items) * ROW_H, self._list.height)

    # ---------- интерфейс слоя ----------
    def covers(self, pos):
        return self.visible and self.rect.collidepoint(pos)

    def cancel_drag(self):
        pass

    def handle_event(self, event, mouse_pos):
        if not self.visible:
            return False
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos):
                self.scroll.scroll_by_wheel(event.y)
                return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            if event.button == 1 and self._list.collidepoint(event.pos):
                i = (event.pos[1] - self._list.y + self.scroll.offset) // ROW_H
                if 0 <= i < len(self.items):
                    key = self.items[i][0]
                    self.selected = None if key == self.selected else key
                    if self.on_pick is not None:
                        self.on_pick(self.selected)
            return True
        return False

    # ---------- рисование ----------
    @staticmethod
    def _fit(text, width, color):
        """Подпись, обрезанная с «…», чтобы влезла в width."""
        label = get_text(text, FONT_SIZE_LABEL, color)
        while label.get_width() > width and len(text) > 2:
            text = text[:-2]
            label = get_text(text + "…", FONT_SIZE_LABEL, color)
        return label

    def draw(self, screen, mouse_pos):
        if not self.visible:
            return
        draw_plate(screen, self.rect, alpha=215, radius=8)
        screen.blit(get_text(self.title, FONT_SIZE_HEADER, TEXT_COLOR), (self.rect.x + PAD + 2, self.rect.y + 8))
        old_clip = screen.get_clip()
        screen.set_clip(self._list)
        inside = self._list.collidepoint(mouse_pos)
        for i, (key, text, icon) in enumerate(self.items):
            row = pygame.Rect(self._list.x, self._list.y + i * ROW_H - self.scroll.offset,
                              self._list.w - 8, ROW_H - 4)
            if row.bottom < self._list.top or row.top > self._list.bottom:
                continue
            if key == self.selected:
                bg, fg = SLIDER_FILL_COLOR, (30, 30, 30)
            elif inside and row.collidepoint(mouse_pos):
                bg, fg = BUTTON_COLORS["hover"], TEXT_COLOR
            else:
                bg, fg = BUTTON_COLORS["normal"], TEXT_COLOR
            pygame.draw.rect(screen, bg, row, border_radius=5)
            if icon is not None:
                screen.blit(icon, icon.get_rect(midleft=(row.x + 4, row.centery)))
            label = self._fit(text, row.w - ICON_W - 14, fg)
            screen.blit(label, label.get_rect(midleft=(row.x + ICON_W + 10, row.centery)))
        screen.set_clip(old_clip)
        self.scroll.draw_scrollbar(screen, self._list)