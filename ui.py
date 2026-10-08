"""ui.py — виджеты и панели интерфейса.
О танке и стене ничего не знает: состав панелей приходит снаружи."""
import pygame

from gfx import FONT_SIZE_TITLE, FONT_SIZE_HEADER, FONT_SIZE_LABEL, get_font, get_text, wrap_text

# ==========================================
# 1. НАСТРОЙКИ ВНЕШНЕГО ВИДА
# ==========================================

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
DELETE_BUTTON_COLORS = {             # красная кнопка «Удалить стену»
    "normal": (190, 45, 45), "hover": (225, 75, 75),
    "disabled": (80, 40, 40), "text": (255, 255, 255),
}
PANEL_TITLES = {"tank": "Конструктор техники", "wall": "Настройки стены"}

# ==========================================
# 2. БАЗОВЫЕ ВИДЖЕТЫ
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
        txt = get_text(self.label, font_size, colors["text"])
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
# 3. ЭЛЕМЕНТЫ СОДЕРЖИМОГО ПАНЕЛИ
# ==========================================

class SectionHeader:
    height = 36

    def __init__(self, text):
        self.text = text
        self.rect = pygame.Rect(0, 0, 0, self.height)

    def layout(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.height)

    def draw(self, surface, mouse_pos):
        label = get_text(self.text, FONT_SIZE_HEADER, TEXT_COLOR)
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

    def draw(self, surface, mouse_pos):
        name = get_text(self.label, FONT_SIZE_LABEL, TEXT_COLOR)
        value_text = f"{self.value:.{self.decimals}f} {self.unit}".strip()
        val = get_text(value_text, FONT_SIZE_LABEL, TEXT_DIM)
        surface.blit(name, (self.rect.x, self.rect.y + 4))
        surface.blit(val, val.get_rect(topright=(self.rect.right, self.rect.y + 4)))
        self.slider.draw(surface)

def make_param_row(params, key):
    """Строка-ползунок по описанию параметра params[key] (Param)."""
    p = params[key]
    return ParamRow(key, p.label, p.unit, p.min, p.max, p.default, p.step, p.decimals)

class StatsBlock:
    """Блок «название ... значение»."""
    ROW_H = 24

    def __init__(self, names):
        self.values = {name: "—" for name in names}
        self.height = self.ROW_H * len(names) + 8
        self.rect = pygame.Rect(0, 0, 0, self.height)

    def layout(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.height)

    def draw(self, surface, mouse_pos):
        y = self.rect.y + 4
        for name, value in self.values.items():
            n = get_text(name, FONT_SIZE_LABEL, TEXT_DIM)
            v = get_text(str(value), FONT_SIZE_LABEL, TEXT_COLOR)
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

    def draw(self, surface, mouse_pos):
        y = self.rect.y + 4
        for line in self.lines:
            surface.blit(get_text(line, FONT_SIZE_LABEL, self.color), (self.rect.x, y))
            y += self.LINE_H

class ActionButton:
    """Кнопка-действие внутри прокручиваемой панели (например, «Удалить стену»)."""
    height = 56

    def __init__(self, label, colors, callback=None):
        self.colors = colors
        self.callback = callback             # функция без аргументов
        self.button = Button((0, 0, 10, 36), label)
        self.rect = pygame.Rect(0, 0, 0, self.height)

    def layout(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.height)
        self.button.rect = pygame.Rect(x, y + 12, w, 36)

    def hit(self, pos):
        return self.button.collidepoint(pos)

    def click(self):
        if self.callback:
            self.callback()

    def draw(self, surface, mouse_pos):
        self.button.draw(surface, mouse_pos, colors=self.colors)

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

    def covers(self, pos):
        """Лежит ли точка экрана на кнопке панели инструментов."""
        return self.wall_button.rect.collidepoint(pos)

    def cancel_drag(self):
        """У кнопки нет перетаскивания; метод нужен ради общего интерфейса слоёв."""
        pass

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and self.wall_button.collidepoint(event.pos):
            if event.button == 1 and self.on_create_wall:
                self.on_create_wall()
            return True                      # любые клики по кнопке поглощаем
        return False

    def draw(self, screen, mouse_pos):
        colors = ACTIVE_BUTTON_COLORS if self.active else BUTTON_COLORS
        self.wall_button.draw(screen, mouse_pos, colors=colors)

# ==========================================
# 4. ПАНЕЛЬ КОНСТРУКТОРА
# ==========================================

class Panel:
    """Содержимое одной панели: заголовок, элементы и колбэк «ползунок сдвинут»."""

    def __init__(self, title, items, on_change=None):
        self.title = title
        self.items = items
        self.on_change = on_change       # функция(values: dict) или None

    def get_values(self):
        """Текущие значения всех ползунков панели: {ключ: число}."""
        return {it.key: it.value for it in self.items if isinstance(it, ParamRow)}

    def set_values(self, values):
        """Поставить значения ползунков извне (без вызова on_change)."""
        for it in self.items:
            if isinstance(it, ParamRow) and it.key in values:
                it.set_value(values[it.key])

class ConstructorUI:
    def __init__(self, screen_size, panels, start_mode):
        """panels — {режим: Panel}; start_mode — какая панель показана вначале."""
        self.screen_size = screen_size
        self.is_open = False             # при запуске панель свёрнута
        self._auto_opened = False        # панель раскрылась сама (при выборе стены), а не по кнопке
        self.panels = panels
        self.mode = start_mode

        self.toggle_button = Button((0, 0, TOGGLE_SIZE, TOGGLE_SIZE), "<")
        self.scroll = ScrollArea()
        self.panel_rect = pygame.Rect(0, 0, PANEL_WIDTH, 0)
        self.content_rect = pygame.Rect(0, 0, 0, 0)
        self._bg_surface = None
        self._active_row = None          # строка, ползунок которой сейчас тянут

        self._stat_blocks = {}           # название характеристики -> StatsBlock, где она показана
        self._index_stats()
        self._layout()

    @property
    def items(self):
        """Элементы показанной сейчас панели."""
        return self.panels[self.mode].items

    # ---------- публичный интерфейс ----------
    def set_on_change(self, mode, callback):
        """Колбэк «ползунок панели mode сдвинут»: функция(values: dict)."""
        self.panels[mode].on_change = callback

    def get_values(self, mode=None):
        """Значения ползунков панели mode (по умолчанию показанной): {ключ: число}."""
        return self.panels[self.mode if mode is None else mode].get_values()

    def set_values(self, mode, values):
        self.panels[mode].set_values(values)

    def _index_stats(self):
        """Один раз связывает названия характеристик с блоками, чтобы не искать их при каждой записи."""
        for panel in self.panels.values():
            for it in panel.items:
                if isinstance(it, StatsBlock):
                    for name in it.values:
                        self._stat_blocks[name] = it

    def set_stat(self, name, value):
        """Записать рассчитанную характеристику в блок статистики."""
        block = self._stat_blocks.get(name)
        if block is not None:
            block.values[name] = value

    def show(self, mode, values=None, auto_open=False):
        """Показать панель mode. values — стартовые значения ползунков (необязательно).
        auto_open=True: закрытая панель раскрывается сама и закрывается обратно, когда
        игрок вернётся к другой панели. Без него открытое/закрытое состояние не трогаем,
        кроме случая, когда уходим с панели, которая раскрылась сама."""
        if values is not None:
            self.set_values(mode, values)
        if auto_open:
            was_closed = not self.is_open
            self._switch(mode)
            if was_closed:
                self.toggle()
                self._auto_opened = True         # после toggle(), иначе он сбросит флаг
        elif self.mode != mode:
            auto = self._auto_opened
            self._switch(mode)
            if auto and self.is_open:            # панель раскрыла сама игра, а не игрок
                self.toggle()

    def _switch(self, mode):
        self.mode = mode
        self._active_row = None
        self.scroll.offset = 0
        self._layout()

    def toggle(self):
        self.is_open = not self.is_open
        self.toggle_button.label = ">" if self.is_open else "<"
        self._active_row = None
        self._auto_opened = False            # ручное переключение отменяет «автозакрытие»

    def update(self, screen_size):
        """Вызывать каждый кадр, но раскладка пересчитывается только при смене размера окна.
        Остальные поводы (прокрутка, смена панели) вызывают _layout() сами."""
        if screen_size != self.screen_size:
            self.screen_size = screen_size
            self._layout()

    def covers(self, pos):
        """Лежит ли точка экрана на красной кнопке или на открытой панели."""
        if self.toggle_button.rect.collidepoint(pos):
            return True
        return self.is_open and self.panel_rect.collidepoint(pos)

    def cancel_drag(self):
        """Бросить перетаскивание ползунка (кнопку отпустили, а событие до нас не дошло)."""
        self._active_row = None

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
    def handle_event(self, event, mouse_pos):
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
                        if isinstance(it, ActionButton) and it.hit(event.pos):
                            it.click()       # колбэк может сменить панель, поэтому сразу выходим
                            break
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self._active_row is not None:
                self._drag_slider(event.pos[0])
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._active_row is not None:
                self._active_row = None
                return True

        elif event.type == pygame.MOUSEWHEEL:
            if self.is_open and self.panel_rect.collidepoint(mouse_pos):
                self.scroll.scroll_by_wheel(event.y)
                self._layout()
                return True

        return False

    def _drag_slider(self, mouse_x):
        if self._active_row.slider.set_from_mouse(mouse_x):
            panel = self.panels[self.mode]
            if panel.on_change:
                panel.on_change(panel.get_values())

    # ---------- отрисовка ----------
    def draw(self, screen, mouse_pos):
        if self.is_open:
            self._draw_panel(screen, mouse_pos)
        self.toggle_button.draw(screen, mouse_pos, font_size=20, colors=TOGGLE_COLORS)

    def _draw_panel(self, screen, mouse_pos):
        rect = self.panel_rect
        if self._bg_surface is None or self._bg_surface.get_size() != rect.size:
            self._bg_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
            self._bg_surface.fill(PANEL_BG)
        screen.blit(self._bg_surface, rect.topleft)
        pygame.draw.line(screen, PANEL_BORDER, rect.topleft, rect.bottomleft, 2)

        title = get_text(self.panels[self.mode].title, FONT_SIZE_TITLE, TEXT_COLOR)
        screen.blit(title, (rect.x + PANEL_PADDING, 16))

        # содержимое рисуем с обрезкой, чтобы при прокрутке оно не вылезало за панель
        screen.set_clip(self.content_rect)
        for it in self.items:
            if it.rect.colliderect(self.content_rect):
                it.draw(screen, mouse_pos)
        screen.set_clip(None)

        self.scroll.draw_scrollbar(screen, self.content_rect)