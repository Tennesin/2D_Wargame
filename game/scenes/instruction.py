"""game/scenes/instruction.py — инструкция: вкладки слева, прокручиваемая страница справа.
Как и меню, сцена сама читает события (у неё нет InputHandler)."""
import pygame

from engine import get_text
from ui import Button, ScrollArea, ACTIVE_BUTTON_COLORS
from ui.theme import BG_COLOR, LINE_COLOR, SCROLLBAR_GAP
from .base import Scene
from .. import texts
from ..guide import PAGES, build_page

BG = BG_COLOR
TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 40
TAB_FONT = 20

MARGIN = 24
TABS_W = 230
TAB_H = 48
TAB_GAP = 10
TITLE_BLOCK_H = 70          # место под заголовок сверху
CONTENT_MAX_W = 1100        # на очень широком окне страница не растягивается дальше этого
CONTENT_MIN_W = 300
ITEM_GAP = 6                # зазор между блоками страницы

class InstructionScene(Scene):
    def __init__(self, on_back, on_quit):
        self.on_back = on_back
        self.on_quit = on_quit

        self.tabs = [Button((0, 0, TABS_W, TAB_H), title) for title, _ in PAGES]
        self.back_button = Button((0, 0, TABS_W, TAB_H), texts.BACK)
        self.scroll = ScrollArea()
        self.content_rect = pygame.Rect(0, 0, 0, 0)

        self._cache = {}                 # номер страницы -> список блоков (строим при первом открытии)
        self.page = 0
        self._items = self._page_items(0)
        self._size = None
        self._layout(pygame.display.get_surface().get_size())

    # ---------- страницы ----------
    def _page_items(self, index):
        items = self._cache.get(index)
        if items is None:
            items = self._cache[index] = build_page(index)
        return items

    def _set_page(self, index):
        if index == self.page:
            return
        self.page = index
        self._items = self._page_items(index)
        self.scroll.offset = 0
        self._place_items()

    # ---------- раскладка ----------
    def _layout(self, size):
        """Вкладки слева, «Назад» внизу слева, страница справа. Вызывается при смене размера окна."""
        self._size = size
        w, h = size
        y = TITLE_BLOCK_H
        for tab in self.tabs:
            tab.rect.topleft = (MARGIN, y)
            y += TAB_H + TAB_GAP
        self.back_button.rect.topleft = (MARGIN, h - MARGIN - TAB_H)

        x = MARGIN + TABS_W + MARGIN
        width = max(CONTENT_MIN_W, min(CONTENT_MAX_W, w - x - MARGIN))
        self.content_rect = pygame.Rect(x, TITLE_BLOCK_H, width, max(0, h - TITLE_BLOCK_H - MARGIN))
        self._place_items()

    def _place_items(self):
        """Высота блоков зависит от ширины (перенос текста), поэтому сначала раскладка без прокрутки,
        потом границы прокрутки, потом раскладка уже со сдвигом."""
        rect = self.content_rect
        inner_w = rect.width - SCROLLBAR_GAP
        y = rect.y
        for item in self._items:
            item.layout(rect.x, y, inner_w)
            y += item.height + ITEM_GAP
        self.scroll.update_bounds(y - rect.y - ITEM_GAP, rect.height)

        y = rect.y - self.scroll.offset
        for item in self._items:
            item.layout(rect.x, y, inner_w)
            y += item.height + ITEM_GAP

    def _scroll(self, steps):
        """steps > 0 вверх, < 0 вниз (как у колёсика)."""
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
                    self.on_back()
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
                if self.back_button.collidepoint(event.pos):
                    self.on_back()
                    return
                for i, tab in enumerate(self.tabs):
                    if tab.collidepoint(event.pos):
                        self._set_page(i)
                        break

    def draw(self, screen):
        screen.fill(BG)
        title = get_text(texts.INSTRUCTION_TITLE, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, (MARGIN, 14))

        mouse = pygame.mouse.get_pos()
        for i, tab in enumerate(self.tabs):
            tab.draw(screen, mouse, font_size=TAB_FONT,
                     colors=ACTIVE_BUTTON_COLORS if i == self.page else None)
        self.back_button.draw(screen, mouse, font_size=TAB_FONT)

        sep_x = MARGIN + TABS_W + MARGIN // 2
        pygame.draw.line(screen, LINE_COLOR, (sep_x, TITLE_BLOCK_H), (sep_x, screen.get_height() - MARGIN), 1)

        # страницу рисуем с обрезкой, чтобы при прокрутке она не вылезала за свою область
        screen.set_clip(self.content_rect)
        for item in self._items:
            if item.rect.colliderect(self.content_rect):
                item.draw(screen, mouse)
        screen.set_clip(None)
        self.scroll.draw_scrollbar(screen, self.content_rect)