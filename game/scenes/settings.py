"""game/scenes/settings.py — настройки: технические и игровые параметры.
Как и меню, сцена сама читает события (у неё нет InputHandler)."""
import pygame

from engine import get_text
from ui import Button, Checkbox, SectionHeader, InfoText, ChoiceRow, make_param_row
from ui.theme import BG_COLOR
from .base import Scene
from ..content import texts
from ..state.settings import FPS_CHOICES, ROUND_TIME

BG = BG_COLOR
TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 40

COL_W = 440
ROW_H = 44
ROW_GAP = 8
SECTION_GAP = 16
TITLE_BLOCK_H = 64
AFTER_GAP = 24
BACK_W, BACK_H = 260, 52
BUTTON_FONT = 24

class SettingsScene(Scene):
    def __init__(self, settings, on_back, on_quit):
        self.settings = settings
        self.on_back = on_back
        self.on_quit = on_quit

        # --- технические ---
        self.tech_header = SectionHeader(texts.SETTINGS_TECH)
        self.fps_row = ChoiceRow("fps", texts.SETTINGS_FPS_LIMIT,
                                 [(n, str(n)) for n in FPS_CHOICES], settings.fps_limit)
        self.show_fps_box = Checkbox((0, 0, COL_W, ROW_H), texts.SETTINGS_SHOW_FPS,
                                     checked=settings.show_fps)

        # --- игра ---
        self.game_header = SectionHeader(texts.SETTINGS_GAME)
        self.round_row = make_param_row({"round": ROUND_TIME}, "round")
        self.round_row.set_value(settings.round_time_s)
        self.rock_box = Checkbox((0, 0, COL_W, ROW_H), texts.SETTINGS_ROCK_HURTS,
                                 checked=settings.rock_hurts_tank)
        self.rock_hint = InfoText(texts.SETTINGS_ROCK_HURTS_HINT)
        self.ff_box = Checkbox((0, 0, COL_W, ROW_H), texts.SETTINGS_FRIENDLY_FIRE,
                               checked=settings.friendly_fire)
        self.ff_hint = InfoText(texts.SETTINGS_FRIENDLY_FIRE_HINT)

        # (галочка, имя поля в GameSettings)
        self.toggles = [(self.show_fps_box, "show_fps"),
                        (self.rock_box, "rock_hurts_tank"),
                        (self.ff_box, "friendly_fire")]
        self.back_button = Button((0, 0, BACK_W, BACK_H), texts.BACK)

        self._drag = False                      # тянут ли ползунок времени раунда
        self._size = None
        self._title_pos = (0, 0)
        self._layout(pygame.display.get_surface().get_size())

    # ---------- раскладка ----------
    @staticmethod
    def _place_box(box, x, y):
        box.rect.topleft = (x, y)
        return y + ROW_H + ROW_GAP

    def _place(self, x, top):
        """Раскладывает всю колонку от высоты top. Возвращает её высоту."""
        y = top
        self._title_pos = (x + COL_W // 2, y + TITLE_BLOCK_H // 2)
        y += TITLE_BLOCK_H

        for item in (self.tech_header, self.fps_row):
            item.layout(x, y, COL_W)
            y += item.height
        y = self._place_box(self.show_fps_box, x, y)
        y += SECTION_GAP

        for item in (self.game_header, self.round_row):
            item.layout(x, y, COL_W)
            y += item.height
        y = self._place_box(self.rock_box, x, y)
        self.rock_hint.layout(x, y - ROW_GAP, COL_W)
        y += self.rock_hint.height
        y = self._place_box(self.ff_box, x, y)
        self.ff_hint.layout(x, y - ROW_GAP, COL_W)
        y += self.ff_hint.height

        y += AFTER_GAP
        self.back_button.rect.midtop = (x + COL_W // 2, y)
        return y + BACK_H - top

    def _layout(self, size):
        """Центрированная колонка. Первый проход считает высоту, второй ставит по центру окна."""
        self._size = size
        w, h = size
        x = (w - COL_W) // 2
        total = self._place(x, 0)
        self._place(x, max(20, (h - total) // 2))

    # ---------- логика ----------
    def _drag_to(self, mouse_x):
        if self.round_row.slider.set_from_mouse(mouse_x):
            self.settings.round_time_s = self.round_row.value

    def update(self, dt):
        size = pygame.display.get_surface().get_size()
        if 0 not in size and size != self._size:
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
                choice = self.fps_row.hit(event.pos)
                if choice is not None:
                    self.fps_row.value = choice
                    self.settings.fps_limit = choice
                elif self.round_row.hit_rect().collidepoint(event.pos):
                    self._drag = True
                    self._drag_to(event.pos[0])
                else:
                    for box, attr in self.toggles:
                        if box.collidepoint(event.pos):
                            value = not getattr(self.settings, attr)
                            setattr(self.settings, attr, value)
                            box.checked = value
                            break
            elif event.type == pygame.MOUSEMOTION and self._drag:
                self._drag_to(event.pos[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self._drag = False

    def draw(self, screen):
        screen.fill(BG)
        title = get_text(texts.SETTINGS_TITLE, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        self.tech_header.draw(screen, mouse)
        self.fps_row.draw(screen, mouse)
        self.show_fps_box.draw(screen, mouse)
        self.game_header.draw(screen, mouse)
        self.round_row.draw(screen, mouse)
        self.rock_box.draw(screen, mouse)
        self.rock_hint.draw(screen, mouse)
        self.ff_box.draw(screen, mouse)
        self.ff_hint.draw(screen, mouse)
        self.back_button.draw(screen, mouse, font_size=BUTTON_FONT)