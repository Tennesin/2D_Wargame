"""td/sprites.py — отрисовка ПТ-САУ: низкий корпус, рубка на оси орудия, задняя опора, лафет.
Рубка следует за осью орудия, поэтому при росте калибра орудие «переезжает» на корму."""
import math

import pygame

from ..tank.sprites import (
    TankRenderer, _Pen, _paint, SS, TRACK_X, HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK,
    GRILL, GRILL_LINE, TURRET_MAIN, TURRET_LIGHT, TURRET_DARK, APPLIQUE,
)
from .params import TD_HULL_HALF_M, TD_TURRET_HALF_M

SUPPORT_MAIN = (128, 120, 104)
SUPPORT_DARK = (96, 90, 78)

class TDRenderer(TankRenderer):
    HULL_HALF_M = TD_HULL_HALF_M

    def __init__(self):
        super().__init__()
        self._hull_cache.limit = 600       # вариантов корпуса больше: сдвиг оси × опора × фазы гусениц

    def _build_hull(self, lp, rp, paint, look, spec):
        ppm = self._ppm
        size = 2 * math.ceil(self.HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        mount = spec.MOUNT_FWD_M
        axis = -mount                                  # ось орудия в координатах корпуса
        support = spec.SUPPORT
        pen = _Pen(big, ppm * SS, 0.0, mount)          # центр спрайта = ось орудия

        hull_main = _paint(HULL_MAIN, paint)
        hull_light = _paint(HULL_LIGHT, paint)
        hull_dark = _paint(HULL_DARK, paint)
        deck = _paint(DECK, paint)
        case_main = _paint(TURRET_MAIN, paint)
        case_light = _paint(TURRET_LIGHT, paint)
        case_dark = _paint(TURRET_DARK, paint)
        sup_main = _paint(SUPPORT_MAIN, paint)
        sup_dark = _paint(SUPPORT_DARK, paint)

        # 1. Гусеницы
        self._draw_track(pen, -TRACK_X, lp)
        self._draw_track(pen, TRACK_X, rp)

        # 2. Низкий широкий корпус, подкрылки, экраны
        pen.poly(hull_main, [(-1.15, -2.9), (1.15, -2.9), (1.35, -2.3), (1.35, 2.65),
                             (1.15, 2.9), (-1.15, 2.9), (-1.35, 2.65), (-1.35, -2.3)])
        pen.rect(hull_dark, 1.35, -2.1, 0.22, 4.75)
        pen.rect(hull_dark, -1.57, -2.1, 0.22, 4.75)
        self._draw_skirts(pen, look.side, paint)

        # 3. Лобовая плита, палуба, накладная броня
        pen.poly(hull_light, [(-1.15, -2.9), (1.15, -2.9), (1.35, -2.3), (-1.35, -2.3)])
        pen.rect(deck, -1.25, -2.25, 2.50, 4.60)
        self._draw_front_kit(pen, look.front, paint)

        # 4. Границы рубки: следует за осью орудия
        front = max(axis - 1.35, -2.55)
        rear = min(axis + 1.35, 2.35)

        # 5. Свободная от рубки часть палубы
        if front > -1.4:                               # рубка далеко от носа: люк механика-водителя
            pen.ellipse(hull_dark, 0.65, -1.9, 0.24, 0.24)
        if support == 0 and rear < 1.6:                # орудие на лбу: сзади моторная часть
            gy = rear + 0.25
            pen.rect(GRILL, -0.95, gy, 1.90, 2.75 - gy)
            ly = gy + 0.25
            while ly < 2.65:
                pen.line(GRILL_LINE, -0.80, ly, 0.80, ly, 0.05)
                ly += 0.25

        # 6. Задняя опора: плита под казённой частью, раскосы, на уровне 2 ещё и кормовой короб
        if support >= 1:
            y0 = axis + 0.2
            y1 = 2.88
            if y1 - y0 > 0.2:
                pen.rect(sup_main, -1.12, y0, 2.24, y1 - y0)
                for sx in (-1, 1):                     # косынки по бокам
                    g = min(0.8, y1 - y0)
                    pen.poly(sup_dark, [(sx * 1.12, y0), (sx * 1.12, y0 + g), (sx * 0.72, y0)])
                if support >= 2:
                    pen.rect(sup_dark, -0.95, max(y0, y1 - 0.60), 1.90, min(0.60, y1 - y0), r=0.05)
                    ry = y0 + 0.35
                    while ry < y1 - 0.65:
                        pen.line(GRILL_LINE, -0.95, ry, 0.95, ry, 0.05)
                        ry += 0.30
            # упор для ствола в походном положении (ствол лежит на носу над корпусом)
            pen.rect(GRILL, -0.50, -2.55, 1.00, 0.20, r=0.05)

        # 7. Рубка вокруг оси орудия
        wf, wr = 0.90, 1.15
        pen.poly(case_main, [(-wf, front), (wf, front), (wr, front + 0.5), (wr, rear),
                             (-wr, rear), (-wr, front + 0.5)])
        pen.poly(case_light, [(-wf + 0.25, front + 0.25), (wf - 0.25, front + 0.25),
                              (wr - 0.30, front + 0.70), (wr - 0.30, rear - 0.25),
                              (-wr + 0.30, rear - 0.25), (-wr + 0.30, front + 0.70)],
                 outline=case_dark)
        pen.ellipse(case_dark, 0.65, axis + 0.75, 0.22, 0.22)    # люк командира
        pen.ellipse(case_dark, 0.0, axis, 0.58, 0.58)            # гнездо орудия

        self._draw_exhaust(pen, look.speed)
        return pygame.transform.smoothscale(big, (size, size))

    def _build_turret(self, team_color, paint, look, emblem, spec):
        """Лафет орудия: люлька, казённая часть и маска цвета команды. Вращается вокруг оси орудия."""
        ppm = self._ppm
        size = 2 * math.ceil(TD_TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)

        dark = _paint(TURRET_DARK, paint)
        main = _paint(TURRET_MAIN, paint)
        light = _paint(TURRET_LIGHT, paint)
        w = 1.0 + 0.12 * look.front                     # накладная броня расширяет маску
        front = spec.GUN_FRONT_M

        pen.rect(dark, -0.30, -0.10, 0.60, 0.85, r=0.08)         # казённая часть
        pen.ellipse(main, 0.0, 0.0, 0.55, 0.55)                  # люлька
        pen.ellipse(light, 0.0, 0.0, 0.34, 0.34, outline=dark)
        pen.rect(team_color, -w / 2.0, -front, w, 0.70, r=0.10)  # маска
        return pygame.transform.smoothscale(big, (size, size))