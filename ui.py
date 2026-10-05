"""ui.py — интерфейс конструктора техники: правая панель с открытием/закрытием.

Виджеты (get_font, wrap_text, Button, Slider, ScrollArea) адаптированы
из widgets.txt: убраны зависимости от settings и ImageManager.
"""
import pygame

from tank import TankSpec, PARAMS
from wall import WALL_PARAMS

# ==========================================
# 1. НАСТРОЙКИ ВНЕШНЕГО ВИДА
# ==========================================
FONT_NAME = "arial"          # SysFont; на Windows поддерживает кириллицу
FONT_SIZE_TITLE = 22
FONT_SIZE_HEADER = 18
FONT_SIZE_LABEL = 16

PANEL_WIDTH = 340
PANEL_PADDING = 14
HEADER_HEIGHT = 56           # высота шапки панели (под заголовок и красную кнопку)
SCROLLBAR_GAP = 12           # место справа от контента под полосу прокрутки
TOGGLE_SIZE = 36
TOGGLE_MARGIN = 6
DEFAULT_SCROLL_SPEED = 30

PANEL_BG = (28, 31, 36, 235)         # RGBA, чуть прозрачный фон
PANEL_BORDER = (70, 76, 86)
TEXT_COLOR = (230, 230, 230)
TEXT_DIM = (150, 156, 166)
LINE_COLOR = (62, 68, 78)

BUTTON_COLORS = {
    "normal": (60, 66, 76), "hover": (80, 88, 100),
    "disabled": (40, 42, 46), "text": (235, 235, 235),
}
TOGGLE_COLORS = {                    # красный прямоугольник-переключатель
    "normal": (200, 40, 40), "hover": (235, 70, 70),
    "disabled": (90, 40, 40), "text": (255, 255, 255),
}
SLIDER_FILL_COLOR = (200, 140, 60)
SLIDER_BG_COLOR = (45, 49, 56)
SLIDER_BORDER_COLOR = (90, 96, 106)

TOOLBAR_MARGIN = 6
TOOLBAR_BUTTON_SIZE = (150, 36)
ACTIVE_BUTTON_COLORS = {             # кнопка «Создать стену», пока включён режим стройки
    "normal": (200, 140, 60), "hover": (225, 165, 85),
    "disabled": (90, 70, 40), "text": (30, 30, 30),
}
PANEL_TITLES = {"tank": "Конструктор техники", "wall": "Настройки стены"}

# ==========================================
# 2. ОБЩИЕ ПОМОЩНИКИ (из widgets.txt)
# ==========================================
_font_cache = {}


def get_font(size, name=FONT_NAME):
    """Общий кэш шрифтов, чтобы не создавать Font на каждый кадр."""
    key = (name, size)
    font = _font_cache.get(key)
    if font is None:
        font = pygame.font.SysFont(name, size)
        _font_cache[key] = font
    return font


def wrap_text(font, text, max_width):
    """Разбивает текст на строки по словам так, чтобы каждая влезала в max_width."""
    lines = []
    line = ""
    for word in text.split(" "):
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] > max_width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


# ==========================================
# 3. БАЗОВЫЕ ВИДЖЕТЫ (из widgets.txt)
# ==========================================
class Button:
    def __init__(self, rect, label, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.enabled = enabled

    def draw(self, surface, mouse_pos, font_size=FONT_SIZE_LABEL, colors=None):
        colors = colors or BUTTON_COLORS
        if not self.enabled:
            bg = colors["disabled"]
        elif self.rect.collidepoint(mouse_pos):
            bg = colors["hover"]
        else:
            bg = colors["normal"]
        pygame.draw.rect(surface, bg, self.rect, border_radius=4)
        txt = get_font(font_size).render(self.label, True, colors["text"])
        surface.blit(txt, txt.get_rect(center=self.rect.center))

    def collidepoint(self, *args):
        return self.enabled and self.rect.collidepoint(*args)


class Slider:
    def __init__(self, rect, value=0.5, min_value=0.0, max_value=1.0, step=0.05):
        self.rect = pygame.Rect(rect)
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.value = max(min_value, min(max_value, value))

    def set_from_mouse(self, mouse_x):
        """Возвращает True, если значение изменилось."""
        if self.rect.width <= 0:
            return False
        ratio = (mouse_x - self.rect.x) / self.rect.width
        ratio = max(0.0, min(1.0, ratio))
        raw = self.min_value + ratio * (self.max_value - self.min_value)
        steps = round((raw - self.min_value) / self.step)
        value = self.min_value + steps * self.step
        value = round(max(self.min_value, min(self.max_value, value)), 3)
        changed = value != self.value
        self.value = value
        return changed

    def draw(self, surface, fill_color=SLIDER_FILL_COLOR, bg_color=SLIDER_BG_COLOR,
             border_color=SLIDER_BORDER_COLOR):
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=4)
        span = self.max_value - self.min_value
        ratio = (self.value - self.min_value) / span if span > 0 else 0.0
        fill_w = max(4, int(self.rect.width * ratio))
        fill_rect = pygame.Rect(self.rect.x, self.rect.y, fill_w, self.rect.height)
        pygame.draw.rect(surface, fill_color, fill_rect, border_radius=4)
        pygame.draw.rect(surface, border_color, self.rect, 1, border_radius=4)

        handle = pygame.Rect(0, 0, 4, self.rect.height + 6)
        handle.center = (self.rect.x + fill_w, self.rect.centery)
        pygame.draw.rect(surface, (240, 240, 240), handle, border_radius=2)


class ScrollArea:
    def __init__(self):
        self.offset = 0
        self.max_scroll = 0

    def update_bounds(self, content_height, visible_height):
        self.max_scroll = max(0, content_height - visible_height)
        self.offset = max(0, min(self.offset, self.max_scroll))

    def scroll_by_wheel(self, wheel_y, speed=DEFAULT_SCROLL_SPEED):
        self.offset -= wheel_y * speed
        self.offset = max(0, min(self.offset, self.max_scroll))

    def draw_scrollbar(self, surface, rect):
        if self.max_scroll <= 0:
            return
        track = pygame.Rect(rect.right - 4, rect.y, 4, rect.height)
        pygame.draw.rect(surface, (30, 30, 30), track)
        content_height = rect.height + self.max_scroll
        thumb_h = max(20, int(rect.height * rect.height / content_height))
        thumb_y = rect.y + int((rect.height - thumb_h) * (self.offset / self.max_scroll))
        pygame.draw.rect(surface, (150, 150, 150), (track.x, thumb_y, 4, thumb_h))


# ==========================================
# 4. ЭЛЕМЕНТЫ СОДЕРЖИМОГО ПАНЕЛИ
#    У каждого: height, layout(x, y, w), draw(surface)
# ==========================================
class SectionHeader:
    height = 36

    def __init__(self, text):
        self.text = text
        self.rect = pygame.Rect(0, 0, 0, self.height)

    def layout(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.height)

    def draw(self, surface):
        label = get_font(FONT_SIZE_HEADER).render(self.text, True, TEXT_COLOR)
        surface.blit(label, (self.rect.x, self.rect.y + 8))
        y = self.rect.bottom - 4
        pygame.draw.line(surface, LINE_COLOR, (self.rect.x, y), (self.rect.right, y), 1)


class ParamRow:
    """Строка параметра: подпись слева, значение справа, под ними ползунок."""
    height = 54

    def __init__(self, key, label, unit, min_v, max_v, value, step, decimals=0):
        self.key = key
        self.label = label
        self.unit = unit
        self.decimals = decimals
        self.slider = Slider((0, 0, 10, 12), value, min_v, max_v, step)
        self.rect = pygame.Rect(0, 0, 0, self.height)

    @property
    def value(self):
        return self.slider.value

    def set_value(self, v):
        """Поставить значение ползунка извне (без вызова on_change)."""
        self.slider.value = max(self.slider.min_value, min(self.slider.max_value, v))

    def layout(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.height)
        self.slider.rect = pygame.Rect(x, y + 28, w, 12)

    def hit_rect(self):
        """Область, по которой можно «схватить» ползунок (чуть шире самой полоски)."""
        return self.slider.rect.inflate(0, 18)

    def draw(self, surface):
        font = get_font(FONT_SIZE_LABEL)
        name = font.render(self.label, True, TEXT_COLOR)
        value_text = f"{self.value:.{self.decimals}f} {self.unit}".strip()
        val = font.render(value_text, True, TEXT_DIM)
        surface.blit(name, (self.rect.x, self.rect.y + 4))
        surface.blit(val, val.get_rect(topright=(self.rect.right, self.rect.y + 4)))
        self.slider.draw(surface)


class StatsBlock:
    """Блок «название ... значение». Значения пока прочерки — их потом заполнят формулы."""
    ROW_H = 24

    def __init__(self, names):
        self.values = {name: "—" for name in names}
        self.height = self.ROW_H * len(names) + 8
        self.rect = pygame.Rect(0, 0, 0, self.height)

    def layout(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.height)

    def draw(self, surface):
        font = get_font(FONT_SIZE_LABEL)
        y = self.rect.y + 4
        for name, value in self.values.items():
            n = font.render(name, True, TEXT_DIM)
            v = font.render(str(value), True, TEXT_COLOR)
            surface.blit(n, (self.rect.x, y))
            surface.blit(v, v.get_rect(topright=(self.rect.right, y)))
            y += self.ROW_H


class InfoText:
    """Абзац текста с переносом по словам."""
    LINE_H = 20

    def __init__(self, text, color=TEXT_DIM):
        self.text = text
        self.color = color
        self.lines = []
        self.height = self.LINE_H
        self.rect = pygame.Rect(0, 0, 0, self.height)

    def layout(self, x, y, w):
        self.lines = wrap_text(get_font(FONT_SIZE_LABEL), self.text, w)
        self.height = self.LINE_H * max(1, len(self.lines)) + 10
        self.rect = pygame.Rect(x, y, w, self.height)

    def draw(self, surface):
        font = get_font(FONT_SIZE_LABEL)
        y = self.rect.y + 4
        for line in self.lines:
            surface.blit(font.render(line, True, self.color), (self.rect.x, y))
            y += self.LINE_H

# ==========================================
# ПАНЕЛЬ ИНСТРУМЕНТОВ (левый верхний угол)
# ==========================================
class ToolBar:
    def __init__(self):
        self.on_create_wall = None           # колбэк нажатия кнопки
        self.active = False
        self.wall_button = Button((TOOLBAR_MARGIN, TOOLBAR_MARGIN, *TOOLBAR_BUTTON_SIZE), "Создать стену")

    def set_active(self, active):
        self.active = active
        self.wall_button.label = "Отмена" if active else "Создать стену"

    def captures_mouse(self):
        return self.wall_button.rect.collidepoint(pygame.mouse.get_pos())

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.wall_button.collidepoint(event.pos):
            if event.button == 1 and self.on_create_wall:
                self.on_create_wall()
            return True                      # любые клики по кнопке поглощаем
        return False

    def draw(self, screen):
        colors = ACTIVE_BUTTON_COLORS if self.active else BUTTON_COLORS
        self.wall_button.draw(screen, pygame.mouse.get_pos(), colors=colors)

# ==========================================
# 5. ПАНЕЛЬ КОНСТРУКТОРА
# ==========================================
class ConstructorUI:
    def __init__(self, screen_size):
        self.screen_size = screen_size
        self.is_open = True
        self.on_change = None            # колбэк танка: функция(values: dict), при изменении ползунка
        self.on_wall_change = None       # то же для панели стены
        self.mode = "tank"               # какое содержимое показано: "tank" или "wall"

        self.toggle_button = Button((0, 0, TOGGLE_SIZE, TOGGLE_SIZE), ">")
        self.scroll = ScrollArea()
        self.panel_rect = pygame.Rect(0, 0, PANEL_WIDTH, 0)
        self.content_rect = pygame.Rect(0, 0, 0, 0)
        self._bg_surface = None
        self._active_row = None          # строка, ползунок которой сейчас тянут

        self._tank_items = self._build_items()
        self._wall_items = self._build_wall_items()
        self.items = self._tank_items
        self._layout()

    # ---------- состав панели (сюда добавляем новые параметры) ----------
    def _build_items(self):
        spec0 = TankSpec.from_config()      # нужен только ради списка названий характеристик

        def row(key):
            p = PARAMS[key]
            return ParamRow(key, p.label, p.unit, p.min, p.max, p.default, p.step, p.decimals)

        return [
            SectionHeader("Вооружение"),
            row("gun_caliber_mm"),

            SectionHeader("Броня"),
            row("front_armor_mm"),
            row("side_armor_mm"),
            row("rear_armor_mm"),

            SectionHeader("Силовая установка"),
            row("engine_power_hp"),

            SectionHeader("Расчётные характеристики"),
            StatsBlock(list(spec0.main_stats())),

            SectionHeader("Внутренние показатели"),
            StatsBlock(list(spec0.internal_stats())),
        ]

    def _build_wall_items(self):
        def row(key):
            p = WALL_PARAMS[key]
            return ParamRow(key, p.label, p.unit, p.min, p.max, p.default, p.step, p.decimals)

        return [
            SectionHeader("Параметры"),
            row("wall_hp"),
            row("wall_width_m"),
            row("wall_length_m"),

            SectionHeader("Расчётные характеристики"),
            StatsBlock(["Текущее HP", "Толщина", "Эквивалент брони", "Угол"]),
            InfoText("Толщина — меньшая из сторон. Эквивалент брони растёт при косом попадании "
                     "(броня / cos угла), а при угле больше 70° снаряд рикошетит. "
                     "Белая точка в центре поворачивает стену; с Shift поворот идёт шагом 15°."),
        ]

    # ---------- публичный интерфейс ----------
    def get_values(self):
        """Текущие значения всех ползунков: {ключ: число}."""
        return {it.key: it.value for it in self.items if isinstance(it, ParamRow)}

    def set_stat(self, name, value):
        """Записать рассчитанную характеристику в блок статистики (ищет в обоих режимах панели)."""
        for it in self._tank_items + self._wall_items:
            if isinstance(it, StatsBlock) and name in it.values:
                it.values[name] = value

    def show_tank(self):
        if self.mode != "tank":
            self._switch("tank", self._tank_items)

    def show_wall(self, values):
        """Открыть настройки стены; values — {ключ: число}. Если панель была закрыта, раскрывает её."""
        self.set_wall_values(values)
        self._switch("wall", self._wall_items)
        if not self.is_open:
            self.toggle()

    def set_wall_values(self, values):
        for it in self._wall_items:
            if isinstance(it, ParamRow) and it.key in values:
                it.set_value(values[it.key])

    def _switch(self, mode, items):
        self.mode = mode
        self.items = items
        self._active_row = None
        self.scroll.offset = 0
        self._layout()

    def toggle(self):
        self.is_open = not self.is_open
        self.toggle_button.label = ">" if self.is_open else "<"
        self._active_row = None

    def update(self, screen_size):
        """Вызывать каждый кадр: учитывает изменение размера окна."""
        self.screen_size = screen_size
        self._layout()

    def captures_mouse(self):
        """True, если мышь «занята» интерфейсом (игра не должна реагировать на неё)."""
        if self._active_row is not None:
            return True
        pos = pygame.mouse.get_pos()
        if self.toggle_button.rect.collidepoint(pos):
            return True
        return self.is_open and self.panel_rect.collidepoint(pos)

    # ---------- раскладка ----------
    def _layout(self):
        w, h = self.screen_size
        self.toggle_button.rect.topright = (w - TOGGLE_MARGIN, TOGGLE_MARGIN)
        self.panel_rect = pygame.Rect(w - PANEL_WIDTH, 0, PANEL_WIDTH, h)
        self.content_rect = pygame.Rect(
            self.panel_rect.x + PANEL_PADDING,
            HEADER_HEIGHT,
            PANEL_WIDTH - 2 * PANEL_PADDING,
            max(0, h - HEADER_HEIGHT - PANEL_PADDING),
        )

        inner_w = self.content_rect.width - SCROLLBAR_GAP
        # высота некоторых элементов (InfoText) зависит от ширины — сначала layout, потом границы
        y = self.content_rect.y
        total = 0
        for it in self.items:
            it.layout(self.content_rect.x, y, inner_w)
            y += it.height
            total += it.height
        self.scroll.update_bounds(total, self.content_rect.height)

        y = self.content_rect.y - self.scroll.offset
        for it in self.items:
            it.layout(self.content_rect.x, y, inner_w)
            y += it.height

    # ---------- события ----------
    def handle_event(self, event):
        """Возвращает True, если событие поглощено интерфейсом."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.toggle_button.collidepoint(event.pos):
                if event.button == 1:
                    self.toggle()
                return True
            if self.is_open and self.panel_rect.collidepoint(event.pos):
                if event.button == 1 and self.content_rect.collidepoint(event.pos):
                    for it in self.items:
                        if isinstance(it, ParamRow) and it.hit_rect().collidepoint(event.pos):
                            self._active_row = it
                            self._drag_slider(event.pos[0])
                            break
                return True        # любые кнопки мыши на панели поглощаются (ПКМ не выбирает стену «сквозь» панель)

        elif event.type == pygame.MOUSEMOTION:
            if self._active_row is not None:
                self._drag_slider(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._active_row is not None:
                self._active_row = None
                return True

        elif event.type == pygame.MOUSEWHEEL:
            if self.is_open and self.panel_rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll.scroll_by_wheel(event.y)
                self._layout()
                return True

        return False

    def _drag_slider(self, mouse_x):
        if self._active_row.slider.set_from_mouse(mouse_x):
            callback = self.on_change if self.mode == "tank" else self.on_wall_change
            if callback:
                callback(self.get_values())

    # ---------- отрисовка ----------
    def draw(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        if self.is_open:
            self._draw_panel(screen)
        self.toggle_button.draw(screen, mouse_pos, font_size=20, colors=TOGGLE_COLORS)

    def _draw_panel(self, screen):
        rect = self.panel_rect
        if self._bg_surface is None or self._bg_surface.get_size() != rect.size:
            self._bg_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
            self._bg_surface.fill(PANEL_BG)
        screen.blit(self._bg_surface, rect.topleft)
        pygame.draw.line(screen, PANEL_BORDER, rect.topleft, rect.bottomleft, 2)

        title = get_font(FONT_SIZE_TITLE).render(PANEL_TITLES[self.mode], True, TEXT_COLOR)
        screen.blit(title, (rect.x + PANEL_PADDING, 16))

        # содержимое рисуем с обрезкой, чтобы при прокрутке оно не вылезало за панель
        screen.set_clip(self.content_rect)
        for it in self.items:
            if it.rect.colliderect(self.content_rect):
                it.draw(screen)
        screen.set_clip(None)

        self.scroll.draw_scrollbar(screen, self.content_rect)