"""game/scenes/newgame.py — подготовка новой партии: выбор карты (случайная по сиду или сохранённая) с превью,
размер случайной карты, допустимые враги и сводка по технике игрока.
Как и меню, сцена сама читает события (у неё нет InputHandler)."""
import traceback

import pygame

from ai import ARCHETYPES
from engine import PX_PER_M, WORLD_MIN_M, WORLD_MAX_M, Param, get_text, FONT_SIZE_LABEL
from ui import (Button, Checkbox, SectionHeader, InfoText, StatsBlock, ListBox, MiniMap,
                make_param_row, ACTIVE_BUTTON_COLORS)
from ui.theme import BG_COLOR, LINE_COLOR, TEXT_COLOR, TEXT_DIM
from vehicles import VEHICLE_TYPES, RENDERERS, make_vehicle
from world import Camera, preview_from_seed, preview_from_map
from .base import Scene
from ..content import texts

BG = BG_COLOR
TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 40
TITLE_BLOCK_H = 70

MARGIN = 20
COL_GAP = 40
COL_WANT = (300, 400, 320)          # желаемые ширины колонок: карта, параметры и враги, техника
COL_MIN = (240, 320, 260)           # на узком окне колонки сжимаются, но не меньше этого
GAP = 12
MAP_SIDE_MAX = 280                  # сторона квадрата мини-карты
SEED_H = 36
SEED_BTN_W = 130
LIST_MIN_H = 110
RANDOM_KEY = "*random*"             # ключ строки «Случайная карта» (имя файла такого содержать не может)

MAP_STEP = 50.0                     # шаг ползунков размера карты, м
ARCH_ROW_H = 34
ARCH_GAP = 6
SECTION_GAP = 16

ICON_SIZE = (200, 230)
ICON_ZOOM_LEVEL = 6
ICON_CENTER_Y = -180.0
ICON_BG = (36, 40, 46)
CONSTRUCTOR_H = 40

BTN_W, BTN_H = 220, 52
BTN_GAP = 16
BOTTOM_GAP = 24
BUTTON_FONT = 24

STAT_KEYS = ("Стоимость", "HP", "Масса", "Макс. скорость", "Урон", "Пробитие", "Перезарядка")

def _map_row(key, label, value):
    param = Param(label, "м", WORLD_MIN_M, WORLD_MAX_M, value, MAP_STEP)
    return make_param_row({key: param}, key)

class NewGameScene(Scene):
    BACKGROUND = False
    def __init__(self, session, on_play, on_constructor, on_back, on_quit):
        self.session = session
        self.on_play = on_play                  # начать бой
        self.on_constructor = on_constructor    # открыть конструктор
        self.on_back = on_back                  # назад в меню
        self.on_quit = on_quit
        self._size = None                       # None: раскладка ещё не делалась
        session.prepare_seed()                  # на прошлом сиде уже играли: берём новый

        # --- карта: выбор (левая колонка) ---
        self.map_header = SectionHeader(texts.NEWGAME_MAP)
        self.minimap = MiniMap(texts.NEWGAME_NO_PREVIEW)
        self.seed_button = Button((0, 0, SEED_BTN_W, SEED_H), texts.NEWGAME_SEED_BTN)
        self.list = ListBox((0, 0, 10, 10), texts.MAPS_EMPTY)
        self._seed_pos = (0, 0)
        self._map = None                        # загруженная MapData или None (случайная карта)
        self._picked = None                     # ключ выбранной строки
        self._previews = {}                     # файл -> готовая картинка сохранённой карты
        self._infos = {}

        # --- карта: размер (средняя колонка) ---
        self.size_header = SectionHeader(texts.NEWGAME_SIZE)
        self.row_w = _map_row("w", texts.NEWGAME_WIDTH, session.map_w_m)
        self.row_h = _map_row("h", texts.NEWGAME_LENGTH, session.map_h_m)
        self.rows = (self.row_w, self.row_h)
        self.size_hint = InfoText(texts.NEWGAME_MAP_HINT)
        self.file_info = InfoText("")           # вместо ползунков, когда выбрана сохранённая карта
        self._drag = None
        self._size_dirty = False

        # --- враги ---
        self.arch_header = SectionHeader(texts.NEWGAME_ENEMIES)
        self.arch_rows = []                      # [(ключ архетипа, Checkbox)]
        for key, arch in ARCHETYPES.items():
            box = Checkbox((0, 0, 100, ARCH_ROW_H), arch.name, swatch=arch.color)
            self.arch_rows.append((key, box))
        self.arch_hint = InfoText(texts.NEWGAME_ENEMIES_HINT)
        self._refresh_arch_rows()

        # --- техника ---
        self.tank_header = SectionHeader(texts.NEWGAME_TANK)
        self.icon = self._make_icon()
        self.icon_rect = pygame.Rect(0, 0, *ICON_SIZE)
        self.stats = self._make_stats()
        self.constructor_button = Button((0, 0, ICON_SIZE[0], CONSTRUCTOR_H), texts.MENU_CONSTRUCTOR)

        # --- нижние кнопки ---
        self.play_button = Button((0, 0, BTN_W, BTN_H), texts.NEWGAME_START)
        self.back_button = Button((0, 0, BTN_W, BTN_H), texts.BACK)

        self._title_pos = (0, 0)
        self._pick(self._reload_list(session.map_file or RANDOM_KEY))
        self._layout(pygame.display.get_surface().get_size())

    # ---------- данные техники ----------
    def _make_icon(self):
        """Картинка техники игрока: тем же рендерером, что и в игре."""
        kind = self.session.kind
        vehicle = make_vehicle(kind, self.session.spec())
        camera = Camera(*ICON_SIZE)
        camera.zoom_by(ICON_ZOOM_LEVEL - camera.zoom_level)
        camera.center_on(0.0, ICON_CENTER_Y)
        renderer = RENDERERS[VEHICLE_TYPES[kind].renderer_key]()
        renderer.set_zoom(PX_PER_M * camera.zoom)
        surf = pygame.Surface(ICON_SIZE)
        surf.fill(ICON_BG)
        renderer.draw(surf, camera, vehicle)
        return surf

    def _make_stats(self):
        spec = self.session.spec()
        main = spec.main_stats()
        rows = {
            "Тип": VEHICLE_TYPES[self.session.kind].label,
            "Калибр": f"{spec.cal:.0f} мм",
            "Броня (лоб/борт/корма)": f"{spec.front:.0f}/{spec.side:.0f}/{spec.rear:.0f} мм",
        }
        rows.update({name: main[name] for name in STAT_KEYS})
        block = StatsBlock(list(rows))
        block.values.update(rows)
        return block

    # ---------- выбор карты ----------
    def _reload_list(self, want):
        """Перечитывает список карт. Возвращает ключ, который оказался выбран (want или случайная)."""
        infos = self.session.maps.list()
        self._infos = {i.file: i for i in infos}
        items = [(RANDOM_KEY, texts.NEWGAME_RANDOM, texts.NEWGAME_RANDOM_NOTE)]
        items += [(i.file, i.name,
                   texts.MAPS_INFO.format(w=i.width_m, l=i.length_m,
                                          kind=texts.MAPS_KIND.get(i.mode, i.mode)))
                  for i in infos]
        if want not in self._infos:
            want = RANDOM_KEY
        self.list.set_items(items, want)
        return want

    def _pick(self, key):
        """Выбрана строка списка: загружаем карту (если это файл), обновляем превью и режим сцены."""
        self._map = None
        if key != RANDOM_KEY:
            self._map = self.session.maps.load(key)
            if self._map is None:                    # файл пропал или повреждён: исчезнет из списка
                key = self._reload_list(RANDOM_KEY)
        self._picked = key
        self.session.map_file = None if self._map is None else key
        self.seed_button.enabled = self._map is None
        if self._map is not None:
            self.file_info.text = texts.NEWGAME_FILE_INFO.format(w=self._map.width_m, l=self._map.length_m)
        self._rebuild_preview()
        if self._size is not None:
            self._layout(self._size)

    def _rebuild_preview(self):
        """Превью выбранной карты. Ошибка в генерации превью игру не роняет: покажется заглушка."""
        surf = None
        try:
            if self._map is None:
                surf = preview_from_seed(self.session.map_seed, self.row_w.value, self.row_h.value)
            else:
                surf = self._previews.get(self._picked)
                if surf is None:
                    surf = self._previews[self._picked] = preview_from_map(self._map)
        except Exception:
            traceback.print_exc()
        self.minimap.set_image(surf)

    # ---------- раскладка ----------
    @staticmethod
    def _col_widths(w):
        avail = w - 2 * MARGIN - 2 * COL_GAP
        total = sum(COL_WANT)
        if avail >= total:
            return COL_WANT
        k = avail / total
        return tuple(max(mn, int(want * k)) for want, mn in zip(COL_WANT, COL_MIN))

    def _size_items(self, random_mode=None):
        if random_mode is None:
            random_mode = self._map is None
        if random_mode:
            return [self.size_header, self.row_w, self.row_h, self.size_hint]
        return [self.size_header, self.file_info]

    def _layout_mid(self, x, top, w, random_mode=None):
        """Размер карты и враги. Возвращает высоту колонки."""
        y = top
        for item in self._size_items(random_mode):
            item.layout(x, y, w)
            y += item.height
        y += SECTION_GAP
        self.arch_header.layout(x, y, w)
        y += self.arch_header.height
        for _, box in self.arch_rows:
            box.rect = pygame.Rect(x, y, w, ARCH_ROW_H)
            y += ARCH_ROW_H + ARCH_GAP
        y -= ARCH_GAP                                   # после последней строки зазор не нужен
        self.arch_hint.layout(x, y, w)
        return y + self.arch_hint.height - top

    def _layout_left(self, x, top, w, side, list_h):
        y = top
        self.map_header.layout(x, y, w)
        y += SectionHeader.height
        self.minimap.layout(x + (w - side) // 2, y, side)
        y += side + GAP
        self.seed_button.rect = pygame.Rect(x, y, SEED_BTN_W, SEED_H)
        self._seed_pos = (x + SEED_BTN_W + GAP, y + SEED_H // 2)
        y += SEED_H + GAP
        self.list.layout((x, y, w, list_h))

    def _layout(self, size):
        """Три колонки по центру; снизу «В бой» и «Назад»."""
        self._size = size
        w, h = size
        lw, mw, rw = self._col_widths(w)
        x_left = (w - (lw + mw + rw + 2 * COL_GAP)) // 2
        x_mid = x_left + lw + COL_GAP
        x_right = x_mid + mw + COL_GAP

        side = min(lw, MAP_SIDE_MAX)
        mid_h = self._layout_mid(x_mid, 0, mw, random_mode=True)    # пробная раскладка: высота нужна заранее
        head = SectionHeader.height + side + GAP + SEED_H + GAP
        list_h = max(LIST_MIN_H, mid_h - head)                      # список тянется до низа средней колонки
        right_h = (SectionHeader.height + 4 + ICON_SIZE[1] + GAP
                   + CONSTRUCTOR_H + GAP + self.stats.height)
        content_h = max(mid_h, head + list_h, right_h)

        total = TITLE_BLOCK_H + content_h + BOTTOM_GAP + BTN_H
        y0 = max(20, (h - total) // 2)
        self._title_pos = (w // 2, y0 + TITLE_BLOCK_H // 2)
        top = y0 + TITLE_BLOCK_H

        self._layout_mid(x_mid, top, mw)
        self._layout_left(x_left, top, lw, side, list_h)

        self.tank_header.layout(x_right, top, rw)
        y = top + self.tank_header.height + 4
        self.icon_rect.midtop = (x_right + rw // 2, y)
        y = self.icon_rect.bottom + GAP
        self.constructor_button.rect.midtop = (self.icon_rect.centerx, y)
        y += CONSTRUCTOR_H + GAP
        self.stats.layout(x_right, y, rw)

        bottom = top + content_h + BOTTOM_GAP
        self.play_button.rect.midtop = (w // 2 - BTN_W // 2 - BTN_GAP // 2, bottom)
        self.back_button.rect.midtop = (w // 2 + BTN_W // 2 + BTN_GAP // 2, bottom)

    def _refresh_arch_rows(self):
        """Галочки, доступность и примечания по текущим настройкам."""
        prefs = self.session.prefs
        for key, box in self.arch_rows:
            locked = prefs.is_locked(key)
            box.checked = prefs.is_enabled(key)
            box.enabled = not locked
            box.note = texts.NEWGAME_LOCKED_NOTE if locked else ""

    # ---------- логика ----------
    def _save(self):
        """Размер случайной карты живёт в сессии: make_map прочитает его при создании партии."""
        self.session.map_w_m = self.row_w.value
        self.session.map_h_m = self.row_h.value

    def _drag_to(self, mouse_x):
        if self._drag is not None and self._drag.slider.set_from_mouse(mouse_x):
            self._save()
            self._size_dirty = True              # превью перестроим, когда ползунок отпустят

    def update(self, dt):
        size = pygame.display.get_surface().get_size()
        if 0 not in size and size != self._size:
            self._layout(size)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.on_quit()
                return
            self.list.handle_event(event)        # выбор строки проверяем после цикла
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.on_back()
                    return
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._save()
                    self.on_play()
                    return
                if event.key == pygame.K_UP:
                    self.list.move(-1)
                elif event.key == pygame.K_DOWN:
                    self.list.move(1)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.play_button.collidepoint(event.pos):
                    self._save()
                    self.on_play()
                    return
                if self.back_button.collidepoint(event.pos):
                    self.on_back()
                    return
                if self.constructor_button.collidepoint(event.pos):
                    self._save()                      # выбор карты и размер не теряются при заходе в конструктор
                    self.on_constructor()
                    return
                if self._map is None:
                    if self.seed_button.collidepoint(event.pos):
                        self.session.fresh_seed()
                        self._rebuild_preview()
                    for row in self.rows:
                        if row.hit_rect().collidepoint(event.pos):
                            self._drag = row
                            self._drag_to(event.pos[0])
                            break
                for key, box in self.arch_rows:
                    if box.collidepoint(event.pos):      # у заблокированной строки всегда False
                        self.session.prefs.toggle(key)
                        self._refresh_arch_rows()
                        break
            elif event.type == pygame.MOUSEMOTION:
                self._drag_to(event.pos[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self._drag is not None:
                    self._drag = None
                    if self._size_dirty:
                        self._size_dirty = False
                        self._rebuild_preview()

        key = self.list.selected_key
        if key is not None and key != self._picked:
            self._pick(key)

    def draw(self, screen):
        screen.fill(BG)
        title = get_text(texts.NEWGAME_TITLE, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        self.map_header.draw(screen, mouse)
        self.minimap.draw(screen, mouse)
        self.seed_button.draw(screen, mouse)
        if self._map is None:
            text, color = texts.NEWGAME_SEED.format(seed=self.session.map_seed), TEXT_COLOR
        else:
            text, color = texts.NEWGAME_SEED.format(seed="—"), TEXT_DIM       # у файла сид ни на что не влияет
        label = get_text(text, FONT_SIZE_LABEL, color)
        screen.blit(label, label.get_rect(midleft=self._seed_pos))
        self.list.draw(screen, mouse)

        for item in self._size_items():
            item.draw(screen, mouse)
        self.arch_header.draw(screen, mouse)
        for _, box in self.arch_rows:
            box.draw(screen, mouse)
        self.arch_hint.draw(screen, mouse)

        self.tank_header.draw(screen, mouse)
        screen.blit(self.icon, self.icon_rect)
        pygame.draw.rect(screen, LINE_COLOR, self.icon_rect, 1, border_radius=4)
        self.constructor_button.draw(screen, mouse)
        self.stats.draw(screen, mouse)

        self.play_button.draw(screen, mouse, font_size=BUTTON_FONT, colors=ACTIVE_BUTTON_COLORS)
        self.back_button.draw(screen, mouse, font_size=BUTTON_FONT)