"""game/scenes/table_scene.py — страница-таблица: заголовок, прокручиваемый список блоков и кнопки внизу.
Общая основа для «Итогов боя» и «Статистики». Как и меню, сама читает события."""
import pygame

from engine import get_text
from ui import ScrollArea, draw_plate
from ui.theme import BG_COLOR, SCROLLBAR_GAP
from .base import Scene

BG = BG_COLOR
TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 40
TITLE_BLOCK_H = 70
MARGIN = 24
CONTENT_W = 620
ITEM_GAP = 6
BTN_W, BTN_H = 220, 52
BTN_GAP = 16
BUTTON_FONT = 24

class TableScene(Scene):
    def __init__(self, title, items, buttons, on_quit, on_escape):
        """buttons: [(Button, колбэк), ...] слева направо. on_escape: что делает Esc."""
        self.title = title
        self.items = items
        self.buttons = buttons
        self.on_quit = on_quit
        self.on_escape = on_escape
        self.scroll = ScrollArea()
        self.content_rect = pygame.Rect(0, 0, 0, 0)
        self._title_pos = (0, 0)
        self._size = None
        self._layout(pygame.display.get_surface().get_size())

    # ---------- раскладка ----------
    def _layout(self, size):
        self._size = size
        w, h = size
        total = len(self.buttons) * BTN_W + (len(self.buttons) - 1) * BTN_GAP
        x, y = (w - total) // 2, h - MARGIN - BTN_H
        for button, _ in self.buttons:
            button.rect.topleft = (x, y)
            x += BTN_W + BTN_GAP

        width = max(300, min(CONTENT_W, w - 2 * MARGIN))
        self.content_rect = pygame.Rect((w - width) // 2, TITLE_BLOCK_H, width,
                                        max(0, y - MARGIN - TITLE_BLOCK_H))
        self._title_pos = (w // 2, TITLE_BLOCK_H // 2)
        self._place_items()

    def _place_items(self):
        """Сначала раскладка без прокрутки (нужна общая высота), затем границы, затем со сдвигом."""
        rect = self.content_rect
        inner_w = rect.width - SCROLLBAR_GAP
        y = rect.y
        for item in self.items:
            item.layout(rect.x, y, inner_w)
            y += item.height + ITEM_GAP
        self.scroll.update_bounds(y - rect.y - ITEM_GAP, rect.height)

        y = rect.y - self.scroll.offset
        for item in self.items:
            item.layout(rect.x, y, inner_w)
            y += item.height + ITEM_GAP

    def _scroll(self, steps):
        self.scroll.scroll_by_wheel(steps)
        self._place_items()

    # ---------- кадр ----------
    def update(self, dt):
        size = pygame.display.get_surface().get_size()
        if 0 not in size and size != self._size:
            self._layout(size)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.on_quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.on_escape()
                    return
                if event.key == pygame.K_DOWN:
                    self._scroll(-1)
                elif event.key == pygame.K_UP:
                    self._scroll(1)
                elif event.key == pygame.K_PAGEDOWN:
                    self._scroll(-6)
                elif event.key == pygame.K_PAGEUP:
                    self._scroll(6)
            elif event.type == pygame.MOUSEWHEEL:
                self._scroll(event.y)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button, callback in self.buttons:
                    if button.collidepoint(event.pos):
                        callback()
                        return

    def draw(self, screen):
        plate = pygame.Rect(self.content_rect.x - 16, 6,
                            self.content_rect.width + 32,
                            self.content_rect.bottom + 10 - 6)
        draw_plate(screen, plate)
        plate.top, plate.bottom = 6, self.content_rect.bottom + 10
        title = get_text(self.title, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        screen.set_clip(self.content_rect)
        for item in self.items:
            if item.rect.colliderect(self.content_rect):
                item.draw(screen, mouse)
        screen.set_clip(None)
        self.scroll.draw_scrollbar(screen, self.content_rect)

        for button, _ in self.buttons:
            button.draw(screen, mouse, font_size=BUTTON_FONT)