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
BLOCK_SHIFT = 50            # на сколько весь блок поднят выше центра окна (кнопок шесть)

BUTTON_W, BUTTON_H = 260, 52
BUTTON_GAP = 16
BUTTON_FONT = 24

class MenuScene(Scene):
    def __init__(self, on_play, on_constructor, on_instruction, on_settings, on_stats, on_quit):
        self.on_play = on_play                      # начать игру
        self.on_constructor = on_constructor        # открыть конструктор
        self.on_instruction = on_instruction        # открыть инструкцию
        self.on_settings = on_settings              # открыть настройки
        self.on_stats = on_stats                    # открыть статистику
        self.on_quit = on_quit                      # закрыть приложение

        self.play_button = Button((0, 0, BUTTON_W, BUTTON_H), texts.MENU_PLAY)
        self.constructor_button = Button((0, 0, BUTTON_W, BUTTON_H), texts.MENU_CONSTRUCTOR)
        self.instruction_button = Button((0, 0, BUTTON_W, BUTTON_H), texts.MENU_INSTRUCTION)
        self.settings_button = Button((0, 0, BUTTON_W, BUTTON_H), texts.MENU_SETTINGS)
        self.stats_button = Button((0, 0, BUTTON_W, BUTTON_H), texts.MENU_STATS)
        self.quit_button = Button((0, 0, BUTTON_W, BUTTON_H), texts.MENU_QUIT)
        self._title_pos = (0, 0)
        self._size = None
        self._layout(pygame.display.get_surface().get_size())

    def _layout(self, size):
        """Расставляет элементы по центру окна (вызывается при смене размера)."""
        self._size = size
        cx, cy = size[0] // 2, size[1] // 2 - BLOCK_SHIFT
        self._title_pos = (cx, cy - TITLE_OFFSET)
        step = BUTTON_H + BUTTON_GAP
        self.play_button.rect.center = (cx, cy)
        self.constructor_button.rect.center = (cx, cy + step)
        self.instruction_button.rect.center = (cx, cy + 2 * step)
        self.settings_button.rect.center = (cx, cy + 3 * step)
        self.stats_button.rect.center = (cx, cy + 4 * step)
        self.quit_button.rect.center = (cx, cy + 5 * step)

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
                if self.play_button.collidepoint(event.pos):
                    self.on_play()
                    return
                if self.constructor_button.collidepoint(event.pos):
                    self.on_constructor()
                    return
                if self.instruction_button.collidepoint(event.pos):
                    self.on_instruction()
                    return
                if self.settings_button.collidepoint(event.pos):
                    self.on_settings()
                    return
                if self.stats_button.collidepoint(event.pos):
                    self.on_stats()
                    return
                if self.quit_button.collidepoint(event.pos):
                    self.on_quit()
                    return

    def draw(self, screen):
        title = get_text(TITLE_TEXT, TITLE_SIZE, TITLE_COLOR)
        shadow = get_text(TITLE_TEXT, TITLE_SIZE, (0, 0, 0))
        screen.blit(shadow, shadow.get_rect(center=(self._title_pos[0] + 2, self._title_pos[1] + 2)))
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        self.play_button.draw(screen, mouse, font_size=BUTTON_FONT)
        self.constructor_button.draw(screen, mouse, font_size=BUTTON_FONT)
        self.instruction_button.draw(screen, mouse, font_size=BUTTON_FONT)
        self.settings_button.draw(screen, mouse, font_size=BUTTON_FONT)
        self.stats_button.draw(screen, mouse, font_size=BUTTON_FONT)
        self.quit_button.draw(screen, mouse, font_size=BUTTON_FONT, colors=DELETE_BUTTON_COLORS)