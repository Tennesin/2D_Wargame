"""game/scenes/menu.py — главное меню."""
import pygame

from engine import get_text
from ui import Button, DELETE_BUTTON_COLORS
from ui.theme import BG_COLOR
from .base import Scene
from ..config import GAME_TITLE
from ..content import texts

BG = BG_COLOR
TITLE_TEXT = GAME_TITLE
TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 48
TITLE_OFFSET = 110          # насколько заголовок выше первой кнопки
BLOCK_SHIFT = 80            # на сколько весь блок поднят выше центра окна (кнопок шесть)

BUTTON_W, BUTTON_H = 260, 52
BUTTON_GAP = 16
BUTTON_FONT = 24

class MenuScene(Scene):
    def __init__(self, on_play, on_maps, on_instruction, on_settings, on_stats, on_quit):
        self.on_play = on_play                      # начать игру
        self.on_quit = on_quit                      # закрыть приложение

        # сверху вниз: (подпись, колбэк, цвета кнопки или None)
        specs = ((texts.MENU_PLAY, on_play, None),
                 (texts.MENU_MAPS, on_maps, None),
                 (texts.MENU_INSTRUCTION, on_instruction, None),
                 (texts.MENU_SETTINGS, on_settings, None),
                 (texts.MENU_STATS, on_stats, None),
                 (texts.MENU_QUIT, on_quit, DELETE_BUTTON_COLORS))
        self.items = [(Button((0, 0, BUTTON_W, BUTTON_H), label), callback, colors)
                      for label, callback, colors in specs]
        self._title_pos = (0, 0)
        self._size = None
        self._layout(pygame.display.get_surface().get_size())

    def _layout(self, size):
        """Расставляет элементы по центру окна (вызывается при смене размера)."""
        self._size = size
        cx, cy = size[0] // 2, size[1] // 2 - BLOCK_SHIFT
        self._title_pos = (cx, cy - TITLE_OFFSET)
        step = BUTTON_H + BUTTON_GAP
        for i, (button, _, _) in enumerate(self.items):
            button.rect.center = (cx, cy + i * step)

    def update(self, dt):
        size = pygame.display.get_surface().get_size()
        if size != self._size:
            self._layout(size)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.on_quit()
                return
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.on_play()
                    return
                if event.key == pygame.K_ESCAPE:
                    self.on_quit()
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button, callback, _ in self.items:
                    if button.collidepoint(event.pos):
                        callback()
                        return

    def draw(self, screen):
        title = get_text(TITLE_TEXT, TITLE_SIZE, TITLE_COLOR)
        shadow = get_text(TITLE_TEXT, TITLE_SIZE, (0, 0, 0))
        screen.blit(shadow, shadow.get_rect(center=(self._title_pos[0] + 2, self._title_pos[1] + 2)))
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        for button, _, colors in self.items:
            button.draw(screen, mouse, font_size=BUTTON_FONT, colors=colors)