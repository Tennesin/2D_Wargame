"""tank/sprites.py — отрисовка ОБТ: корпус и башня. Общая часть (гусеницы, ствол, тень, кэши)
лежит в vehicles/sprite_base.py."""
import math

import pygame

from ..gun_params import TURRET_FRONT_M
from ..sprite_base import (
    GunVehicleRenderer, Pen as _Pen, apply_paint as _paint, SS, OUTLINE,
    HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK, RING, GRILL, GRILL_LINE,
    TURRET_MAIN, TURRET_LIGHT, TURRET_DARK, EMBLEM_COLOR,
)

HULL_SHIFT_M = 0.3          # корпус сдвинут назад: ось башни = центр спрайта = центр танка
HULL_HALF_M = 3.7           # половина стороны квадратной заготовки корпуса, м
TURRET_HALF_M = 2.1         # половина стороны заготовки башни (без ствола), м


class TankRenderer(GunVehicleRenderer):
    HULL_HALF_M = HULL_HALF_M

    # ---------- построение спрайтов ----------

    def _hull_shift_m(self, spec):
        return HULL_SHIFT_M

    def _build_hull(self, paint, look, spec):
        ppm = self._ppm
        size = 2 * math.ceil(HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS, 0.0, HULL_SHIFT_M)     # координаты корпуса: центр корпуса = (0, 0)

        hull_main = _paint(HULL_MAIN, paint)
        hull_light = _paint(HULL_LIGHT, paint)
        hull_dark = _paint(HULL_DARK, paint)
        deck = _paint(DECK, paint)

        # Корпус: короткий клин спереди, скошенные углы сзади
        pen.poly(hull_main, [(-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (1.35, 2.65),
                             (1.15, 2.9), (-1.15, 2.9), (-1.35, 2.65), (-1.35, -2.1)])

        # Подкрылки (полки над гусеницами)
        pen.rect(hull_dark, 1.35, -2.1, 0.22, 4.75)
        pen.rect(hull_dark, -1.57, -2.1, 0.22, 4.75)

        self._draw_skirts(pen, look.side, paint)

        # Лобовая плита (светлее: обращена к свету) и палуба
        pen.poly(hull_light, [(-1.00, -2.9), (1.00, -2.9), (1.35, -2.1), (-1.35, -2.1)])
        pen.rect(deck, -1.25, -2.05, 2.50, 4.40)

        self._draw_front_kit(pen, look.front, paint)
        self._draw_front_screen(pen, look.screen, paint)

        # Погон башни: тёмное кольцо вокруг оси (контактная тень под башней)
        pen.ellipse(_paint(RING, paint), 0.0, -HULL_SHIFT_M, 1.35, 1.35, outline=None)

        # Люк механика-водителя
        pen.ellipse(hull_dark, 0.65, -1.65, 0.24, 0.24)

        # МТО: решётка и жалюзи
        pen.rect(GRILL, -0.95, 1.00, 1.90, 1.20)
        for ly in (1.30, 1.55, 1.80, 2.05):
            pen.line(GRILL_LINE, -0.80, ly, 0.80, ly, 0.05)

        # Кормовая плита
        pen.rect(hull_dark, -1.15, 2.40, 2.30, 0.50)

        self._draw_exhaust(pen, look.speed)

        return pygame.transform.smoothscale(big, (size, size))

    def _build_turret(self, team_color, paint, look, emblem, spec):
        ppm = self._ppm
        size = 2 * math.ceil(TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)                        # центр спрайта = ось башни

        turret_main = _paint(TURRET_MAIN, paint)
        turret_light = _paint(TURRET_LIGHT, paint)
        turret_dark = _paint(TURRET_DARK, paint)

        hexa = [(-0.70, -1.55), (0.70, -1.55), (1.30, 0.00), (0.70, 1.65), (-0.70, 1.65), (-1.30, 0.00)]
        if look.front > 0:                  # утолщённая броня башни: тёмный «обод» вокруг
            k = 1.0 + 0.10 * look.front     # максимум 1.2: помещается в заготовку (полуразмер 2.1 м)
            pen.poly(turret_dark, [(x * k, y * k) for x, y in hexa])

        # 1. Шестиугольный корпус башни + светлая вставка поверх
        pen.poly(turret_main, [(-0.70, -1.55), (0.70, -1.55), (1.30, 0.00),
                               (0.70, 1.65), (-0.70, 1.65), (-1.30, 0.00)])
        pen.poly(turret_light, [(-0.48, -1.05), (0.48, -1.05), (0.88, 0.00),
                                (0.48, 1.12), (-0.48, 1.12), (-0.88, 0.00)], outline=turret_dark)
        if emblem == "chevron":            # двойной шеврон острием вперёд (Уничтожитель)
            for k in (0.0, 0.25):
                pen.poly(EMBLEM_COLOR,
                         [(0.00, -0.95 + k), (0.40, -0.55 + k), (0.40, -0.38 + k),
                          (0.00, -0.78 + k), (-0.40, -0.38 + k), (-0.40, -0.55 + k)],
                         outline=None)

        # 2. Маска орудия: выступает вперёд из башни, ствол выходит из её торца
        pen.rect(team_color, -0.55, -TURRET_FRONT_M, 1.10, 0.60, r=0.08)

        # 3. Люк командира
        pen.ellipse(turret_dark, 0.42, 0.30, 0.42, 0.42)
        pen.ellipse(team_color, 0.42, 0.30, 0.32, 0.32)

        if look.speed > 0:                  # антенна
            pen.line(OUTLINE, -0.75, 1.0, -0.95, 1.95, 0.04)
            pen.ellipse(turret_dark, -0.75, 1.0, 0.10, 0.10)

        return pygame.transform.smoothscale(big, (size, size))