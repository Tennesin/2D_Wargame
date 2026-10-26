"""game/scenes/new_map.py — параметры новой карты: размер и тип (естественная или пустая).
Как и меню, сцена сама читает события (у неё нет InputHandler)."""
import random
import pygame

from engine import WORLD_MIN_M, WORLD_MAX_M, WORLD_DEFAULT_M, Param, get_text
from ui import (Button, SectionHeader, InfoText, ChoiceRow, make_param_row,
                draw_plate, ACTIVE_BUTTON_COLORS)
from world import build_natural, build_empty, MODE_NATURAL, MODE_EMPTY
from world.mapdata import DEFAULT_NAME
from .base import Scene
from ..content import texts

TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 40
COL_W = 440
TITLE_BLOCK_H = 70
AFTER_GAP = 24
BTN_W, BTN_H = 212, 52
BTN_GAP = 16
BUTTON_FONT = 24
MAP_STEP = 50.0              # шаг ползунков размера, м

def _size_row(key, label):
    param = Param(label, "м", WORLD_MIN_M, WORLD_MAX_M, WORLD_DEFAULT_M, MAP_STEP)
    return make_param_row({key: param}, key)

class NewMapScene(Scene):
    def __init__(self, on_create, on_back, on_quit):
        """on_create(map_data): готовая карта (ещё не сохранённая) уходит в редактор."""
        self.on_create = on_create
        self.on_back = on_back
        self.on_quit = on_quit

        self.row_w = _size_row("w", texts.NEWMAP_WIDTH)
        self.row_l = _size_row("l", texts.NEWMAP_LENGTH)
        self.rows = (self.row_w, self.row_l)
        self.mode_row = ChoiceRow("mode", texts.NEWMAP_MODE,
                                  [(MODE_NATURAL, texts.NEWMAP_NATURAL), (MODE_EMPTY, texts.NEWMAP_EMPTY)],
                                  MODE_NATURAL)
        self.items = [SectionHeader(texts.NEWMAP_SIZE), self.row_w, self.row_l,
                      SectionHeader(texts.NEWMAP_TYPE), self.mode_row,
                      InfoText(texts.NEWMAP_HINT)]
        self.create_button = Button((0, 0, BTN_W, BTN_H), texts.NEWMAP_CREATE)
        self.back_button = Button((0, 0, BTN_W, BTN_H), texts.BACK)

        self._drag = None
        self._title_pos = (0, 0)
        self._plate = pygame.Rect(0, 0, 0, 0)
        self._size = None
        self._layout(pygame.display.get_surface().get_size())

    # ---------- раскладка ----------
    def _place(self, x, top):
        """Раскладывает колонку от высоты top. Возвращает её высоту."""
        y = top
        self._title_pos = (x + COL_W // 2, y + TITLE_BLOCK_H // 2)
        y += TITLE_BLOCK_H
        for item in self.items:
            item.layout(x, y, COL_W)
            y += item.height
        y += AFTER_GAP
        self.create_button.rect.topleft = (x, y)
        self.back_button.rect.topleft = (x + BTN_W + BTN_GAP, y)
        return y + BTN_H - top

    def _layout(self, size):
        """Первый проход считает высоту, второй ставит колонку по центру окна."""
        self._size = size
        w, h = size
        x = (w - COL_W) // 2
        total = self._place(x, 0)
        top = max(20, (h - total) // 2)
        self._place(x, top)
        self._plate = pygame.Rect(x - 28, top - 12, COL_W + 56, total + 24)

    # ---------- действия ----------
    def _create(self):
        width, length = self.row_w.value, self.row_l.value
        seed = random.randrange(1, 1_000_000)
        if self.mode_row.value == MODE_EMPTY:
            data = build_empty(DEFAULT_NAME, width, length, seed)
        else:
            data = build_natural(seed, width, length)         # имя по умолчанию: «Сид N»
        self.on_create(data)

    def _drag_to(self, mouse_x):
        if self._drag is not None:
            self._drag.slider.set_from_mouse(mouse_x)

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
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._create()
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.create_button.collidepoint(event.pos):
                    self._create()
                    return
                if self.back_button.collidepoint(event.pos):
                    self.on_back()
                    return
                for row in self.rows:
                    if row.hit_rect().collidepoint(event.pos):
                        self._drag = row
                        self._drag_to(event.pos[0])
                        break
                choice = self.mode_row.hit(event.pos)
                if choice is not None:
                    self.mode_row.value = choice
            elif event.type == pygame.MOUSEMOTION:
                self._drag_to(event.pos[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._drag = None

    def draw(self, screen):
        draw_plate(screen, self._plate)
        title = get_text(texts.NEWMAP_TITLE, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        for item in self.items:
            item.draw(screen, mouse)
        self.create_button.draw(screen, mouse, font_size=BUTTON_FONT, colors=ACTIVE_BUTTON_COLORS)
        self.back_button.draw(screen, mouse, font_size=BUTTON_FONT)