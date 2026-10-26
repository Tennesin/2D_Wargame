"""ui/widgets.py — базовые виджеты и элементы содержимого панели."""
import pygame

from engine import FONT_SIZE_HEADER, FONT_SIZE_LABEL, get_font, get_text, wrap_text, COLOR_GOOD
from .theme import (BUTTON_COLORS, SLIDER_FILL_COLOR, SLIDER_BG_COLOR, SLIDER_BORDER_COLOR,
                    TEXT_COLOR, TEXT_DIM, LINE_COLOR, DEFAULT_SCROLL_SPEED)

# ==========================================
# БАЗОВЫЕ ВИДЖЕТЫ
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

class Checkbox:
    """Строка-переключатель: [галочка] [цветной квадратик] подпись ........ примечание.
    Недоступная строка (enabled=False) не реагирует на мышь и рисуется приглушённо."""
    BOX = 22
    PAD = 10
    SWATCH = 16
    CHECK_COLOR = COLOR_GOOD
    CHECK_DIM = (80, 120, 80)

    def __init__(self, rect, label, checked=True, enabled=True, note="", swatch=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.checked = checked
        self.enabled = enabled
        self.note = note
        self.swatch = swatch             # цвет маленького квадратика или None

    def collidepoint(self, *args):
        return self.enabled and self.rect.collidepoint(*args)

    def draw(self, surface, mouse_pos, font_size=FONT_SIZE_LABEL):
        if not self.enabled:
            bg = BUTTON_COLORS["disabled"]
        elif self.rect.collidepoint(mouse_pos):
            bg = BUTTON_COLORS["hover"]
        else:
            bg = BUTTON_COLORS["normal"]
        pygame.draw.rect(surface, bg, self.rect, border_radius=4)

        box = pygame.Rect(self.rect.x + self.PAD, 0, self.BOX, self.BOX)
        box.centery = self.rect.centery
        pygame.draw.rect(surface, SLIDER_BG_COLOR, box, border_radius=3)
        pygame.draw.rect(surface, SLIDER_BORDER_COLOR, box, 1, border_radius=3)
        if self.checked:
            color = self.CHECK_COLOR if self.enabled else self.CHECK_DIM
            pts = [(box.x + 5, box.y + 11), (box.x + 9, box.y + 16), (box.x + 17, box.y + 6)]
            pygame.draw.lines(surface, color, False, pts, 3)

        x = box.right + self.PAD
        if self.swatch is not None:
            sw = pygame.Rect(x, 0, self.SWATCH, self.SWATCH)
            sw.centery = self.rect.centery
            pygame.draw.rect(surface, self.swatch, sw, border_radius=3)
            pygame.draw.rect(surface, (20, 22, 26), sw, 1, border_radius=3)
            x = sw.right + self.PAD

        text_color = TEXT_COLOR if self.enabled else TEXT_DIM
        label = get_text(self.label, font_size, text_color)
        surface.blit(label, label.get_rect(midleft=(x, self.rect.centery)))

        if self.note:
            note = get_text(self.note, font_size, TEXT_DIM)
            surface.blit(note, note.get_rect(midright=(self.rect.right - self.PAD, self.rect.centery)))

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
# ЭЛЕМЕНТЫ СОДЕРЖИМОГО ПАНЕЛИ
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

    def set_range(self, min_v, max_v):
        """Сменить границы ползунка (например, коридор урона при смене калибра).
        Текущее значение подрезается под новые границы, on_change не вызывается."""
        self.slider.min_value = min_v
        self.slider.max_value = max_v
        self.set_value(self.slider.value)

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

class ChoiceRow:
    """Строка выбора из нескольких вариантов: подпись и ряд кнопок. Значение: первый элемент пары."""
    height = 62

    def __init__(self, key, label, options, value, note=""):
        self.key = key
        self.label = label
        self.options = options              # [(значение, подпись), ...]
        self.value = value
        self.enabled = True
        self.note = note                    # показывается, пока строка недоступна
        self.rect = pygame.Rect(0, 0, 0, self.height)
        self._rects = []

    def set_value(self, value):
        """Поставить значение извне (без вызова on_change)."""
        if any(value == v for v, _ in self.options):
            self.value = value

    def set_options(self, options):
        """Сменить набор вариантов. Если выбранного значения в новом наборе нет, берётся первое.
        Возвращает True, если набор изменился (тогда панель должна пересчитать раскладку)."""
        options = list(options)
        if options == self.options:
            return False
        self.options = options
        if not any(self.value == v for v, _ in options):
            self.value = options[0][0]
        return True

    def layout(self, x, y, w):
        self.rect = pygame.Rect(x, y, w, self.height)
        gap = 6
        n = len(self.options)
        bw = (w - gap * (n - 1)) // n
        self._rects = [pygame.Rect(x + i * (bw + gap), y + 26, bw, 30) for i in range(n)]

    def hit(self, pos):
        """Значение кнопки под точкой или None."""
        if not self.enabled:
            return None
        for (value, _), rect in zip(self.options, self._rects):
            if rect.collidepoint(pos):
                return value
        return None

    def draw(self, surface, mouse_pos):
        text_color = TEXT_COLOR if self.enabled else TEXT_DIM
        name = get_text(self.label, FONT_SIZE_LABEL, text_color)
        surface.blit(name, (self.rect.x, self.rect.y + 4))
        if self.note and not self.enabled:
            note = get_text(self.note, FONT_SIZE_LABEL, TEXT_DIM)
            surface.blit(note, note.get_rect(topright=(self.rect.right, self.rect.y + 4)))
        for (value, label), rect in zip(self.options, self._rects):
            selected = value == self.value
            if not self.enabled:
                bg = BUTTON_COLORS["disabled"]
            elif selected:
                bg = SLIDER_FILL_COLOR
            elif rect.collidepoint(mouse_pos):
                bg = BUTTON_COLORS["hover"]
            else:
                bg = BUTTON_COLORS["normal"]
            pygame.draw.rect(surface, bg, rect, border_radius=4)
            color = (30, 30, 30) if selected and self.enabled else text_color
            txt = get_text(label, FONT_SIZE_LABEL, color)
            surface.blit(txt, txt.get_rect(center=rect.center))

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
# СПИСОК И ПОЛЕ ВВОДА
# ==========================================
class ListBox:
    """Список с выбором строки и прокруткой. items: [(ключ, заголовок, пояснение), ...].
    handle_event возвращает "select", "activate" (двойной клик) или None."""
    ROW_H = 50
    DOUBLE_CLICK_MS = 400

    def __init__(self, rect, empty_text="Список пуст"):
        self.rect = pygame.Rect(rect)
        self.empty_text = empty_text
        self.items = []
        self.selected = None              # индекс выбранной строки
        self.scroll = ScrollArea()
        self._last_click = (None, 0)

    @property
    def selected_key(self):
        return None if self.selected is None else self.items[self.selected][0]

    def set_items(self, items, select_key=None):
        self.items = list(items)
        self.selected = None
        if select_key is not None:
            for i, item in enumerate(self.items):
                if item[0] == select_key:
                    self.selected = i
                    break
        self._last_click = (None, 0)
        self._bounds()

    def layout(self, rect):
        self.rect = pygame.Rect(rect)
        self._bounds()

    def _bounds(self):
        self.scroll.update_bounds(len(self.items) * self.ROW_H, self.rect.height)

    def move(self, step):
        """Сдвинуть выбор на step строк (клавиши вверх и вниз) и прокрутить так, чтобы строка была видна."""
        if not self.items:
            return
        i = 0 if self.selected is None else max(0, min(len(self.items) - 1, self.selected + step))
        self.selected = i
        top = i * self.ROW_H
        if top < self.scroll.offset:
            self.scroll.offset = top
        elif top + self.ROW_H > self.scroll.offset + self.rect.height:
            self.scroll.offset = top + self.ROW_H - self.rect.height

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll.scroll_by_wheel(event.y)
            return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            i = (event.pos[1] - self.rect.y + self.scroll.offset) // self.ROW_H
            if 0 <= i < len(self.items):
                now = pygame.time.get_ticks()
                double = self._last_click[0] == i and now - self._last_click[1] <= self.DOUBLE_CLICK_MS
                self.selected = i
                self._last_click = (i, now)
                return "activate" if double else "select"
        return None

    def draw(self, surface, mouse_pos):
        pygame.draw.rect(surface, SLIDER_BG_COLOR, self.rect, border_radius=6)
        old_clip = surface.get_clip()
        surface.set_clip(self.rect)
        if not self.items:
            txt = get_text(self.empty_text, FONT_SIZE_LABEL, TEXT_DIM)
            surface.blit(txt, txt.get_rect(center=self.rect.center))
        inside = self.rect.collidepoint(mouse_pos)
        for i, (_, title, note) in enumerate(self.items):
            row = pygame.Rect(self.rect.x + 4, self.rect.y + i * self.ROW_H - self.scroll.offset + 2,
                              self.rect.width - 14, self.ROW_H - 4)
            if row.bottom < self.rect.top or row.top > self.rect.bottom:
                continue
            if i == self.selected:
                bg, c_title, c_note = SLIDER_FILL_COLOR, (30, 30, 30), (70, 56, 30)
            elif inside and row.collidepoint(mouse_pos):
                bg, c_title, c_note = BUTTON_COLORS["hover"], TEXT_COLOR, TEXT_DIM
            else:
                bg, c_title, c_note = BUTTON_COLORS["normal"], TEXT_COLOR, TEXT_DIM
            pygame.draw.rect(surface, bg, row, border_radius=4)
            surface.blit(get_text(title, FONT_SIZE_LABEL, c_title), (row.x + 10, row.y + 4))
            surface.blit(get_text(note, FONT_SIZE_LABEL, c_note), (row.x + 10, row.y + 24))
        surface.set_clip(old_clip)
        pygame.draw.rect(surface, SLIDER_BORDER_COLOR, self.rect, 1, border_radius=6)
        self.scroll.draw_scrollbar(surface, self.rect)

class TextInput:
    """Однострочное поле ввода. Клавиши приходят через handle_key(event) из KEYDOWN
    (event.unicode даёт и кириллицу). Вставки из буфера обмена нет."""

    def __init__(self, rect, text="", max_len=40, placeholder=""):
        self.rect = pygame.Rect(rect)
        self.text = text[:max_len]
        self.pos = len(self.text)         # положение курсора
        self.max_len = max_len
        self.placeholder = placeholder

    def handle_key(self, event):
        k = event.key
        if k == pygame.K_BACKSPACE:
            if self.pos > 0:
                self.text = self.text[:self.pos - 1] + self.text[self.pos:]
                self.pos -= 1
        elif k == pygame.K_DELETE:
            self.text = self.text[:self.pos] + self.text[self.pos + 1:]
        elif k == pygame.K_LEFT:
            self.pos = max(0, self.pos - 1)
        elif k == pygame.K_RIGHT:
            self.pos = min(len(self.text), self.pos + 1)
        elif k == pygame.K_HOME:
            self.pos = 0
        elif k == pygame.K_END:
            self.pos = len(self.text)
        else:
            ch = event.unicode
            if ch and ch.isprintable() and len(self.text) < self.max_len:
                self.text = self.text[:self.pos] + ch + self.text[self.pos:]
                self.pos += 1

    def draw(self, surface, mouse_pos, focused=True):
        pygame.draw.rect(surface, SLIDER_BG_COLOR, self.rect, border_radius=4)
        pygame.draw.rect(surface, SLIDER_FILL_COLOR if focused else SLIDER_BORDER_COLOR,
                         self.rect, 1, border_radius=4)
        inner = self.rect.inflate(-16, -6)
        caret_x = get_text(self.text[:self.pos], FONT_SIZE_LABEL, TEXT_COLOR).get_width() if self.pos else 0
        shift = max(0, caret_x - inner.width + 4)          # длинный текст едет влево, курсор остаётся видим
        old_clip = surface.get_clip()
        surface.set_clip(inner)
        if self.text:
            label = get_text(self.text, FONT_SIZE_LABEL, TEXT_COLOR)
            surface.blit(label, label.get_rect(midleft=(inner.x - shift, inner.centery)))
        elif self.placeholder:
            label = get_text(self.placeholder, FONT_SIZE_LABEL, TEXT_DIM)
            surface.blit(label, label.get_rect(midleft=(inner.x, inner.centery)))
        if focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            x = inner.x - shift + caret_x
            pygame.draw.line(surface, TEXT_COLOR, (x, inner.y + 2), (x, inner.bottom - 2), 2)
        surface.set_clip(old_clip)