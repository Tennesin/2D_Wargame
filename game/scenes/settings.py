"""game/scenes/settings.py — настройки: какие архетипы вражеских танков могут появляться.
Как и меню, сцена сама читает события (у неё нет InputHandler)."""
import pygame

from ai import ARCHETYPES
from engine import get_text
from ui import Button, Checkbox
from .base import Scene

BG = (28, 31, 36)
TITLE_COLOR = (230, 230, 230)
SUB_COLOR = (150, 156, 166)
TITLE_SIZE = 40
SUB_SIZE = 22
HINT_SIZE = 16

ROW_W, ROW_H = 440, 44
ROW_GAP = 8
BACK_W, BACK_H = 260, 52
BUTTON_FONT = 24

TITLE_BLOCK_H = 64          # место под заголовок
SUB_BLOCK_H = 40            # под подзаголовок
HINT_BLOCK_H = 36           # под примечание под списком
AFTER_HINT_GAP = 16

SUBTITLE = "Враги: допустимые архетипы"
HINT = "Изменения вступят в силу в новой игре."

class SettingsScene(Scene):
    def __init__(self, prefs, on_back, on_quit):
        self.prefs = prefs
        self.on_back = on_back
        self.on_quit = on_quit

        self.rows = []                              # [(ключ архетипа, Checkbox)]
        for key, arch in ARCHETYPES.items():
            locked = prefs.is_locked(key)
            box = Checkbox((0, 0, ROW_W, ROW_H), arch.name,
                           checked=prefs.is_enabled(key),
                           enabled=not locked,
                           note="нельзя отключить" if locked else "",
                           swatch=arch.color)
            self.rows.append((key, box))
        self.back_button = Button((0, 0, BACK_W, BACK_H), "Назад")

        self._size = None
        self._title_pos = (0, 0)
        self._sub_pos = (0, 0)
        self._hint_pos = (0, 0)
        self._layout(pygame.display.get_surface().get_size())

    def _layout(self, size):
        """Центрированная колонка: заголовок, подзаголовок, список, примечание, «Назад»."""
        self._size = size
        w, h = size
        cx = w // 2
        list_h = len(self.rows) * ROW_H + (len(self.rows) - 1) * ROW_GAP
        total = TITLE_BLOCK_H + SUB_BLOCK_H + list_h + HINT_BLOCK_H + AFTER_HINT_GAP + BACK_H
        y = max(20, (h - total) // 2)

        self._title_pos = (cx, y + TITLE_BLOCK_H // 2)
        y += TITLE_BLOCK_H
        self._sub_pos = (cx, y + SUB_BLOCK_H // 2)
        y += SUB_BLOCK_H
        for _, box in self.rows:
            box.rect.topleft = (cx - ROW_W // 2, y)
            y += ROW_H + ROW_GAP
        y -= ROW_GAP                                # после последней строки зазор не нужен
        self._hint_pos = (cx, y + HINT_BLOCK_H // 2)
        y += HINT_BLOCK_H + AFTER_HINT_GAP
        self.back_button.rect.midtop = (cx, y)

    def update(self, dt):
        size = pygame.display.get_surface().get_size()
        if size != self._size:
            self._layout(size)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.on_quit()
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.on_back()
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.back_button.collidepoint(event.pos):
                    self.on_back()
                    return
                for key, box in self.rows:
                    if box.collidepoint(event.pos):          # у заблокированной строки всегда False
                        self.prefs.toggle(key)
                        box.checked = self.prefs.is_enabled(key)
                        break

    def draw(self, screen):
        screen.fill(BG)
        title = get_text("Настройки", TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))
        sub = get_text(SUBTITLE, SUB_SIZE, SUB_COLOR)
        screen.blit(sub, sub.get_rect(center=self._sub_pos))

        mouse = pygame.mouse.get_pos()
        for _, box in self.rows:
            box.draw(screen, mouse)
        hint = get_text(HINT, HINT_SIZE, SUB_COLOR)
        screen.blit(hint, hint.get_rect(center=self._hint_pos))
        self.back_button.draw(screen, mouse, font_size=BUTTON_FONT)