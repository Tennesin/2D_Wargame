"""gfx.py — общие помощники рисования: шрифты, кэш текста, прозрачный буфер."""
import pygame

from common import LRUCache

FONT_NAME = "arial"          # SysFont; на Windows поддерживает кириллицу
FONT_SIZE_TITLE = 22
FONT_SIZE_HEADER = 18
FONT_SIZE_LABEL = 16

_font_cache = {}
_text_cache = LRUCache(512)

def get_font(size, name=FONT_NAME):
    """Общий кэш шрифтов, чтобы не создавать Font на каждый кадр."""
    key = (name, size)
    font = _font_cache.get(key)
    if font is None:
        font = pygame.font.SysFont(name, size)
        _font_cache[key] = font
    return font

def get_text(text, size, color):
    """Готовая поверхность с текстом. Кэшируется по (текст, размер, цвет).
    Полученную поверхность нельзя менять: она общая. color должен быть кортежем."""
    key = (text, size, color)
    surf = _text_cache.get(key)
    if surf is None:
        surf = get_font(size).render(text, True, color)
        _text_cache.put(key, surf)
    return surf


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

class AlphaLayer:
    """Один переиспользуемый прозрачный буфер для полупрозрачных фигур.
    begin(size) возвращает ЧИСТУЮ поверхность нужного размера; нарисуй на ней и сделай screen.blit(...).
    Новая поверхность в память не выделяется, пока размер не превысил прежний максимум."""

    def __init__(self):
        self._buf = None

    def begin(self, size):
        w, h = size
        buf = self._buf
        if buf is None or buf.get_width() < w or buf.get_height() < h:
            bw = w if buf is None else max(w, buf.get_width())
            bh = h if buf is None else max(h, buf.get_height())
            bw, bh = (bw + 63) // 64 * 64, (bh + 63) // 64 * 64   # запас, чтобы не пересоздавать каждый кадр
            buf = self._buf = pygame.Surface((bw, bh), pygame.SRCALPHA)
        layer = buf.subsurface((0, 0, w, h))
        layer.fill((0, 0, 0, 0))
        return layer