"""ui/widgets.py — базовые виджеты и элементы содержимого панели."""
import pygame

from engine import FONT_SIZE_HEADER, FONT_SIZE_LABEL, get_font, get_text, wrap_text
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