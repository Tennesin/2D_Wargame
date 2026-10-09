"""game/scenes/menu.py — главное меню: «Играть» и «Выйти»."""
import pygame

from engine import get_text
from ui import Button, DELETE_BUTTON_COLORS
from .base import Scene

BG = (28, 31, 36)
TITLE_TEXT = "Top-Down Танк"
TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 48
TITLE_OFFSET = 110          # насколько заголовок выше центра окна

BUTTON_W, BUTTON_H = 260, 52
BUTTON_GAP = 16
BUTTON_FONT = 24

class MenuScene(Scene):
    def __init__(self, on_play, on_quit):
        self.on_play = on_play           # функция без аргументов: начать игру
        self.on_quit = on_quit           # функция без аргументов: закрыть приложение

        self.play_button = Button((0, 0, BUTTON_W, BUTTON_H), "Играть")
        self.quit_button = Button((0, 0, BUTTON_W, BUTTON_H), "Выйти")
        self._title_pos = (0, 0)
        self._size = None
        self._layout(pygame.display.get_surface().get_size())

    def _layout(self, size):
        """Расставляет элементы по центру окна (вызывается при смене размера)."""
        self._size = size
        cx, cy = size[0] // 2, size[1] // 2
        self._title_pos = (cx, cy - TITLE_OFFSET)
        self.play_button.rect.center = (cx, cy)
        self.quit_button.rect.center = (cx, cy + BUTTON_H + BUTTON_GAP)

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
                if self.quit_button.collidepoint(event.pos):
                    self.on_quit()
                    return

    def draw(self, screen):
        screen.fill(BG)
        title = get_text(TITLE_TEXT, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()      # у меню нет InputHandler, мышь читаем здесь
        self.play_button.draw(screen, mouse, font_size=BUTTON_FONT)
        self.quit_button.draw(screen, mouse, font_size=BUTTON_FONT, colors=DELETE_BUTTON_COLORS)