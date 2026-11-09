"""vehicles/parts/frame.py — PartPen: рисование в системе координат детали (начало в её точке, поворот, зеркало).
Функции рисования деталей пишутся в ЛОКАЛЬНЫХ метрах, а перенос и поворот делает эта обёртка."""
import math

from vehicles.render.pen import OUTLINE

ELLIPSE_SEGS = 24               # число вершин у повёрнутого эллипса

class PartPen:
    def __init__(self, pen, part):
        self.pen = pen
        self.k = pen.k
        self.ox, self.oy = part.x, part.y
        self.mirror = part.mirror
        self.unrotated = part.angle == 0.0
        rad = math.radians(part.angle)
        self._c, self._s = math.cos(rad), math.sin(rad)

    def _pt(self, x, y):
        """Локальная точка -> метры поверхности. Поворот по часовой на экране (ось y вниз)."""
        if self.mirror:
            x = -x
        if self.unrotated:
            return self.ox + x, self.oy + y
        return (self.ox + x * self._c - y * self._s,
                self.oy + x * self._s + y * self._c)

    def rect(self, color, x, y, w, h, outline=OUTLINE, r=0.0):
        if self.unrotated:
            x0 = -(x + w) if self.mirror else x
            self.pen.rect(color, self.ox + x0, self.oy + y, w, h, outline, r)
            return
        corners = [self._pt(x, y), self._pt(x + w, y), self._pt(x + w, y + h), self._pt(x, y + h)]
        self.pen.poly(color, corners, outline)          # повёрнутый прямоугольник: скругление не рисуется

    def ellipse(self, color, cx, cy, rx, ry, outline=OUTLINE):
        if self.unrotated or abs(rx - ry) < 1e-9:       # круг от поворота не меняется
            X, Y = self._pt(cx, cy)
            self.pen.ellipse(color, X, Y, rx, ry, outline)
            return
        pts = []
        for i in range(ELLIPSE_SEGS):
            a = 2.0 * math.pi * i / ELLIPSE_SEGS
            pts.append(self._pt(cx + rx * math.cos(a), cy + ry * math.sin(a)))
        self.pen.poly(color, pts, outline)

    def poly(self, color, pts, outline=OUTLINE):
        self.pen.poly(color, [self._pt(x, y) for x, y in pts], outline)

    def line(self, color, x1, y1, x2, y2, w):
        ax, ay = self._pt(x1, y1)
        bx, by = self._pt(x2, y2)
        self.pen.line(color, ax, ay, bx, by, w)