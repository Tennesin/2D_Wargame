"""ui/guide_blocks.py — элементы страницы инструкции: «иконка + текст», «клавиши + текст»
и маленькие процедурные иконки. Интерфейс как у элементов панели (layout / height / rect / draw),
поэтому они работают с ScrollArea. О танках и клавишах не знают: всё приходит снаружи готовым."""
import pygame

from engine import get_font, get_text, wrap_text, FONT_SIZE_HEADER, FONT_SIZE_LABEL
from .theme import SLIDER_BG_COLOR, LINE_COLOR, TEXT_COLOR, TEXT_DIM

ROW_BG = SLIDER_BG_COLOR
ROW_BORDER = LINE_COLOR
ROW_PAD = 10                 # внутренний отступ строки
COL_GAP = 14                 # зазор между левой колонкой (иконка, клавиши) и текстом
LINE_H = 20                  # высота строки описания
TITLE_H = 26                 # высота строки названия в IconRow
MIN_TEXT_W = 80              # на очень узком окне текст не сжимается меньше этого

KEY_H = 30
KEY_GAP = 6
KEY_PAD = 9
KEY_MIN_W = 32
KEY_FACE = (74, 80, 92)
KEY_EDGE = (24, 27, 32)
KEY_SHADOW = (40, 44, 52)

def _draw_row_bg(surface, rect):
    pygame.draw.rect(surface, ROW_BG, rect, border_radius=6)
    pygame.draw.rect(surface, ROW_BORDER, rect, 1, border_radius=6)

# ==========================================
# СТРОКА «ИКОНКА + НАЗВАНИЕ + ОПИСАНИЕ»
# ==========================================
class IconRow:
    """Слева иконка (поверхность), справа название и описание с переносом по словам.
    col_w — ширина левой колонки: у строк одной страницы лучше задавать одинаковую,
    тогда тексты выровнены."""

    def __init__(self, icon, title, text, col_w=None):
        self.icon = icon
        self.title = title
        self.text = text
        self.col_w = col_w if col_w is not None else max(64, icon.get_width())
        self.lines = []
        self.height = 2 * ROW_PAD + TITLE_H
        self.rect = pygame.Rect(0, 0, 0, self.height)

    def layout(self, x, y, w):
        text_w = max(MIN_TEXT_W, w - 2 * ROW_PAD - self.col_w - COL_GAP)
        self.lines = wrap_text(get_font(FONT_SIZE_LABEL), self.text, text_w)
        text_h = TITLE_H + LINE_H * len(self.lines)
        self.height = 2 * ROW_PAD + max(text_h, self.icon.get_height())
        self.rect = pygame.Rect(x, y, w, self.height)

    def draw(self, surface, mouse_pos):
        _draw_row_bg(surface, self.rect)
        icon_rect = self.icon.get_rect(
            center=(self.rect.x + ROW_PAD + self.col_w // 2, self.rect.centery))
        surface.blit(self.icon, icon_rect)

        x = self.rect.x + ROW_PAD + self.col_w + COL_GAP
        y = self.rect.centery - (TITLE_H + LINE_H * len(self.lines)) // 2
        surface.blit(get_text(self.title, FONT_SIZE_HEADER, TEXT_COLOR), (x, y))
        y += TITLE_H
        for line in self.lines:
            surface.blit(get_text(line, FONT_SIZE_LABEL, TEXT_DIM), (x, y))
            y += LINE_H

# ==========================================
# СТРОКА «КЛАВИШИ + ОПИСАНИЕ»
# ==========================================
class KeyRow:
    """Слева ряд «клавиш»: строка рисуется как кнопка клавиатуры, Surface вставляется как есть
    (например, иконка мыши). Справа описание. key_col — ширина левой колонки."""

    def __init__(self, keys, text, key_col=170):
        self.keys = list(keys)
        self.text = text
        self.key_col = key_col
        self.lines = []
        self.height = 2 * ROW_PAD + KEY_H
        self.rect = pygame.Rect(0, 0, 0, self.height)

    @staticmethod
    def _key_w(key):
        if isinstance(key, str):
            return max(KEY_MIN_W, get_text(key, FONT_SIZE_LABEL, TEXT_COLOR).get_width() + 2 * KEY_PAD)
        return key.get_width()

    @staticmethod
    def _key_h(key):
        return KEY_H if isinstance(key, str) else key.get_height()

    def layout(self, x, y, w):
        text_w = max(MIN_TEXT_W, w - 2 * ROW_PAD - self.key_col - COL_GAP)
        self.lines = wrap_text(get_font(FONT_SIZE_LABEL), self.text, text_w)
        keys_h = max((self._key_h(k) for k in self.keys), default=KEY_H)
        self.height = 2 * ROW_PAD + max(keys_h, LINE_H * len(self.lines))
        self.rect = pygame.Rect(x, y, w, self.height)

    def draw(self, surface, mouse_pos):
        _draw_row_bg(surface, self.rect)

        x = self.rect.x + ROW_PAD
        for key in self.keys:
            w = self._key_w(key)
            if isinstance(key, str):
                face = pygame.Rect(x, self.rect.centery - KEY_H // 2, w, KEY_H - 3)
                pygame.draw.rect(surface, KEY_SHADOW, face.move(0, 3), border_radius=5)
                pygame.draw.rect(surface, KEY_FACE, face, border_radius=5)
                pygame.draw.rect(surface, KEY_EDGE, face, 1, border_radius=5)
                label = get_text(key, FONT_SIZE_LABEL, TEXT_COLOR)
                surface.blit(label, label.get_rect(center=face.center))
            else:
                surface.blit(key, key.get_rect(midleft=(x, self.rect.centery)))
            x += w + KEY_GAP

        tx = self.rect.x + ROW_PAD + self.key_col + COL_GAP
        y = self.rect.centery - LINE_H * len(self.lines) // 2
        for line in self.lines:
            surface.blit(get_text(line, FONT_SIZE_LABEL, TEXT_DIM), (tx, y))
            y += LINE_H

# ==========================================
# МАЛЕНЬКИЕ ИКОНКИ
# ==========================================
def make_mouse_icon(button=None, size=(26, 38)):
    """Иконка мыши. button: "left", "right", "wheel" подсвечивает нужную часть; None — без подсветки."""
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    body = pygame.Rect(1, 1, w - 2, h - 2)
    light = (200, 204, 212)
    hot = (230, 170, 60)
    edge = (30, 33, 38)
    split = int(h * 0.42)
    half = w // 2

    pygame.draw.rect(surf, light, body, border_radius=half)
    if button == "left":
        pygame.draw.rect(surf, hot, (1, 1, half - 1, split), border_top_left_radius=half)
    elif button == "right":
        pygame.draw.rect(surf, hot, (half, 1, half - 1, split), border_top_right_radius=half)
    pygame.draw.line(surf, edge, (1, split), (w - 2, split), 1)
    pygame.draw.line(surf, edge, (half, 1), (half, split), 1)
    if button == "wheel":
        pygame.draw.rect(surf, hot, (half - 2, 5, 4, 11), border_radius=2)
    pygame.draw.rect(surf, edge, body, 2, border_radius=half)
    return surf

def make_swatch_icon(color, size=(28, 28)):
    """Цветная плашка (образец цвета подписи, полоски и т.п.)."""
    surf = pygame.Surface(size, pygame.SRCALPHA)
    rect = surf.get_rect()
    pygame.draw.rect(surf, color, rect, border_radius=6)
    pygame.draw.rect(surf, (20, 22, 26), rect, 2, border_radius=6)
    return surf