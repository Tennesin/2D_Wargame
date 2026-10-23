"""game/scenes/newgame.py — подготовка новой партии: размер карты и сводка по технике игрока.
Как и меню, сцена сама читает события (у неё нет InputHandler)."""
import pygame

from ai import ARCHETYPES
from engine import PX_PER_M, WORLD_MIN_M, WORLD_MAX_M, Param, get_text
from ui import (Button, Checkbox, SectionHeader, InfoText, StatsBlock,
                make_param_row, ACTIVE_BUTTON_COLORS)
from ui.theme import BG_COLOR, LINE_COLOR
from vehicles import VEHICLE_TYPES, RENDERERS, make_vehicle
from world import Camera
from .base import Scene
from ..content import texts

BG = BG_COLOR
TITLE_COLOR = (230, 230, 230)
TITLE_SIZE = 40
TITLE_BLOCK_H = 70

LEFT_W = 420                 # левая колонка: карта
RIGHT_W = 360                # правая колонка: техника
COL_GAP = 60
GAP = 12

MAP_STEP = 50.0              # шаг ползунков размера карты, м
ARCH_ROW_H = 34              # высота строки архетипа (в настройках было 44)
ARCH_GAP = 6                 # зазор между строками архетипов
SECTION_GAP = 16             # зазор между блоком карты и блоком врагов

ICON_SIZE = (200, 230)
ICON_ZOOM_LEVEL = 6          # ступень зума камеры иконки (подбирается на глаз)
ICON_CENTER_Y = -180.0       # камера чуть выше центра: ствол смотрит вверх
ICON_BG = (36, 40, 46)
CONSTRUCTOR_H = 40

BTN_W, BTN_H = 220, 52
BTN_GAP = 16
BOTTOM_GAP = 24
BUTTON_FONT = 24

# Какие строки берём из полной таблицы техники (main_stats) для упрощённой сводки
STAT_KEYS = ("Стоимость", "HP", "Масса", "Макс. скорость", "Урон", "Пробитие", "Перезарядка")

def _map_row(key, label, value):
    param = Param(label, "м", WORLD_MIN_M, WORLD_MAX_M, value, MAP_STEP)
    return make_param_row({key: param}, key)

class NewGameScene(Scene):
    def __init__(self, session, on_play, on_constructor, on_back, on_quit):
        self.session = session
        self.on_play = on_play                  # начать бой
        self.on_constructor = on_constructor    # открыть конструктор
        self.on_back = on_back                  # назад в меню
        self.on_quit = on_quit

        # --- карта ---
        self.row_w = _map_row("w", texts.NEWGAME_WIDTH, session.map_w_m)
        self.row_h = _map_row("h", texts.NEWGAME_LENGTH, session.map_h_m)
        self.rows = (self.row_w, self.row_h)
        self.left_items = [SectionHeader(texts.NEWGAME_MAP), self.row_w, self.row_h,
                           InfoText(texts.NEWGAME_MAP_HINT)]
        self._drag = None                       # ползунок, который сейчас тянут

        # --- враги: допустимые архетипы (хранятся в session.prefs) ---
        self.arch_header = SectionHeader(texts.NEWGAME_ENEMIES)
        self.arch_rows = []                      # [(ключ архетипа, Checkbox)]
        for key, arch in ARCHETYPES.items():
            box = Checkbox((0, 0, LEFT_W, ARCH_ROW_H), arch.name, swatch=arch.color)
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
        self._size = None
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

    # ---------- раскладка ----------

    def _layout_left(self, x, top):
        """Раскладывает левую колонку (карта и враги). Возвращает её высоту."""
        y = top
        for item in self.left_items:
            item.layout(x, y, LEFT_W)
            y += item.height
        y += SECTION_GAP

        self.arch_header.layout(x, y, LEFT_W)
        y += self.arch_header.height
        for _, box in self.arch_rows:
            box.rect.topleft = (x, y)
            y += ARCH_ROW_H + ARCH_GAP
        y -= ARCH_GAP                             # после последней строки зазор не нужен

        self.arch_hint.layout(x, y, LEFT_W)
        return y + self.arch_hint.height - top

    def _layout(self, size):
        """Две колонки по центру: слева карта, справа техника; снизу «В бой» и «Назад»."""
        self._size = size
        w, h = size
        left_h = self._layout_left(0, 0)          # пробная раскладка: нужна только высота колонки
        right_h = (SectionHeader.height + 4 + ICON_SIZE[1] + GAP
                   + CONSTRUCTOR_H + GAP + self.stats.height)
        content_h = max(left_h, right_h)
        total = TITLE_BLOCK_H + content_h + BOTTOM_GAP + BTN_H
        y0 = max(20, (h - total) // 2)

        self._title_pos = (w // 2, y0 + TITLE_BLOCK_H // 2)
        top = y0 + TITLE_BLOCK_H
        x_left = (w - (LEFT_W + COL_GAP + RIGHT_W)) // 2
        x_right = x_left + LEFT_W + COL_GAP

        self._layout_left(x_left, top)            # окончательная раскладка левой колонки

        y = top
        for item in self.left_items:
            item.layout(x_left, y, LEFT_W)
            y += item.height

        self.tank_header.layout(x_right, top, RIGHT_W)
        y = top + self.tank_header.height + 4
        self.icon_rect.midtop = (x_right + RIGHT_W // 2, y)
        y = self.icon_rect.bottom + GAP
        self.constructor_button.rect.midtop = (self.icon_rect.centerx, y)
        y += CONSTRUCTOR_H + GAP
        self.stats.layout(x_right, y, RIGHT_W)

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
        """Размер карты живёт в сессии: PlayScene прочитает его при создании партии."""
        self.session.map_w_m = self.row_w.value
        self.session.map_h_m = self.row_h.value

    def _drag_to(self, mouse_x):
        if self._drag is not None and self._drag.slider.set_from_mouse(mouse_x):
            self._save()

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
                    self._save()
                    self.on_play()
                    return
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.play_button.collidepoint(event.pos):
                    self._save()
                    self.on_play()
                    return
                if self.back_button.collidepoint(event.pos):
                    self.on_back()
                    return
                if self.constructor_button.collidepoint(event.pos):
                    self._save()                      # настройки карты не теряются при заходе в конструктор
                    self.on_constructor()
                    return
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
                self._drag = None

    def draw(self, screen):
        screen.fill(BG)
        title = get_text(texts.NEWGAME_TITLE, TITLE_SIZE, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=self._title_pos))

        mouse = pygame.mouse.get_pos()
        for item in self.left_items:
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