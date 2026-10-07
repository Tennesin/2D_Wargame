"""gfx.py — общие помощники рисования (позже сюда переедут и шрифты)."""
import pygame

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