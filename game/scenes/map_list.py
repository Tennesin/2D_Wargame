"""game/scenes/map_list.py — список сохранённых карт: создать новую, открыть в редакторе, удалить.
Как и меню, сцена сама читает события (у неё нет InputHandler)."""
import pygame

from engine import get_text, FONT_SIZE_LABEL
from ui import Button, ListBox, draw_plate, ACTIVE_BUTTON_COLORS, DELETE_BUTTON_COLORS
from ui.theme import TEXT_DIM
from .base import Scene
from ..content import texts

TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 40
COL_W = 560
TITLE_BLOCK_H = 64
GAP = 12
BTN_H = 48
BTN_W = (COL_W - GAP) // 2
STATUS_H = 26
LIST_MIN_H, LIST_MAX_H = 140, 520
BUTTON_FONT = 22
CONFIRM_MS = 3000            # сколько ждём второго нажатия «Удалить»

C_BAD = (240, 80, 70)
C_GOOD = (110, 220, 110)
C_WARN = (240, 200, 70)

class MapListScene(Scene):
    def __init__(self, session, on_new, on_open, on_back, on_quit):
        """on_new(): создать карту; on_open(map_data): открыть загруженную карту в редакторе."""
        self.store = session.maps
        self.on_new = on_new
        self.on_open = on_open
        self.on_back = on_back
        self.on_quit = on_quit

        self.list = ListBox((0, 0, COL_W, 200), texts.MAPS_EMPTY)
        self.new_button = Button((0, 0, BTN_W, BTN_H), texts.MAPS_NEW)
        self.open_button = Button((0, 0, BTN_W, BTN_H), texts.MAPS_OPEN)
        self.delete_button = Button((0, 0, BTN_W, BTN_H), texts.MAPS_DELETE)
        self.back_button = Button((0, 0, BTN_W, BTN_H), texts.BACK)

        self._confirm = None                     # (файл, момент, до которого действует подтверждение)
        self._status = ("", TEXT_DIM)
        self._title_pos = (0, 0)
        self._status_pos = (0, 0)
        self._plate = pygame.Rect(0, 0, 0, 0)
        self._size = None
        self._layout(pygame.display.get_surface().get_size())
        self._reload()

    # ---------- данные ----------
    def _reload(self, select=None):
        infos = self.store.list()
        items = [(i.file, i.name,
                  texts.MAPS_INFO.format(w=i.width_m, l=i.length_m, kind=texts.MAPS_KIND.get(i.mode, i.mode)))
                 for i in infos]
        self.list.set_items(items, select)

    def _set_status(self, text, color=TEXT_DIM):
        self._status = (text, color)

    # ---------- раскладка ----------
    def _layout(self, size):
        self._size = size
        w, h = size
        fixed = TITLE_BLOCK_H + GAP + STATUS_H + GAP + 2 * BTN_H + GAP    # всё, кроме самого списка
        list_h = max(LIST_MIN_H, min(LIST_MAX_H, h - fixed - 60))
        total = fixed + list_h
        x = (w - COL_W) // 2
        top = max(20, (h - total) // 2)

        self._title_pos = (w // 2, top + TITLE_BLOCK_H // 2)
        y = top + TITLE_BLOCK_H
        self.list.layout((x, y, COL_W, list_h))
        y += list_h + GAP
        self._status_pos = (w // 2, y + STATUS_H // 2)
        y += STATUS_H + GAP
        self.new_button.rect.topleft = (x, y)
        self.open_button.rect.topleft = (x + BTN_W + GAP, y)
        y += BTN_H + GAP
        self.delete_button.rect.topleft = (x, y)
        self.back_button.rect.topleft = (x + BTN_W + GAP, y)
        self._plate = pygame.Rect(x - 28, top - 12, COL_W + 56, total + 24)

    # ---------- действия ----------
    def _open(self):
        key = self.list.selected_key
        if key is None:
            return
        data = self.store.load(key)
        if data is None:
            self._set_status(texts.MAPS_LOAD_FAILED, C_BAD)
            self._reload()
            return
        self.on_open(data)

    def _delete(self):
        key = self.list.selected_key
        if key is None:
            return
        now = pygame.time.get_ticks()
        if self._confirm is None or self._confirm[0] != key or now > self._confirm[1]:
            self._confirm = (key, now + CONFIRM_MS)
            self._set_status(texts.MAPS_CONFIRM, C_WARN)
            return
        self._confirm = None
        if self.store.delete(key):
            self._set_status(texts.MAPS_DELETED, C_GOOD)
        else:
            self._set_status(texts.MAPS_DELETE_FAILED, C_BAD)
        self._reload()

    def _confirming(self):
        c = self._confirm
        return c is not None and c[0] == self.list.selected_key and pygame.time.get_ticks() <= c[1]

    # ---------- кадр ----------
    def update(self, dt):
        size = pygame.display.get_surface().get_size()
        if 0 not in size and size != self._size:
            self._layout(size)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.on_quit()
                return
            if self.list.handle_event(event) == "activate":
                self._open()
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.on_back()
                    return
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._open()
                    return
                if event.key == pygame.K_DOWN:
                    self.list.move(1)
                elif event.key == pygame.K_UP:
                    self.list.move(-1)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.new_button.collidepoint(event.pos):
                    self.on_new()
                    return
                if self.open_button.collidepoint(event.pos):
                    self._open()
                    return
                if self.delete_button.collidepoint(event.pos):
                    self._delete()
                elif self.back_button.collidepoint(event.pos):
                    self.on_back()
                    return

        has = self.list.selected is not None
        self.open_button.enabled = has
        self.delete_button.enabled = has
        self.delete_button.label = texts.MAPS_DELETE_SURE if self._confirming() else texts.MAPS_DELETE

    def draw(self, screen):
        draw_plate(screen, self._plate)
        title = get_text(texts.MAPS_TITLE, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        self.list.draw(screen, mouse)
        text, color = self._status
        if text:
            label = get_text(text, FONT_SIZE_LABEL, color)
            screen.blit(label, label.get_rect(center=self._status_pos))

        self.new_button.draw(screen, mouse, font_size=BUTTON_FONT, colors=ACTIVE_BUTTON_COLORS)
        self.open_button.draw(screen, mouse, font_size=BUTTON_FONT)
        self.delete_button.draw(screen, mouse, font_size=BUTTON_FONT,
                                colors=DELETE_BUTTON_COLORS if self._confirming() else None)
        self.back_button.draw(screen, mouse, font_size=BUTTON_FONT)