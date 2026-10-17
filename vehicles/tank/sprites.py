"""tank/sprites.py — отрисовка ОБТ: корпус и башня строятся из раскладки (vehicles/hulls.py).
Общая часть (гусеницы, ствол, тень, кэши) лежит в vehicles/sprite_base.py."""
import math

import pygame

from ..hulls import max_canvas_half_m, NOSE_PIKE
from ..sprite_base import (
    GunVehicleRenderer, Pen as _Pen, apply_paint as _paint, layout_of, SS, OUTLINE,
    HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK, RING, GRILL, GRILL_LINE,
    TURRET_MAIN, TURRET_LIGHT, TURRET_DARK, EMBLEM_COLOR,
)

HULL_HALF_M = max_canvas_half_m()   # один холст на все раскладки
TURRET_HALF_M = 2.4                 # заготовка башни (без ствола): по самому крупному стилю

# Шестиугольная башня (средний корпус)
HEX_POINTS = [(-0.70, -1.55), (0.70, -1.55), (1.30, 0.00), (0.70, 1.65), (-0.70, 1.65), (-1.30, 0.00)]
HEX_INNER = [(-0.48, -1.05), (0.48, -1.05), (0.88, 0.00), (0.48, 1.12), (-0.48, 1.12), (-0.88, 0.00)]

# Литая каплевидная башня (тяжёлый корпус): узкая спереди, широкая сзади
CAST_POINTS = [(-0.60, -1.70), (0.60, -1.70), (1.05, -1.10), (1.45, 0.20), (1.30, 1.35),
               (0.75, 1.90), (-0.75, 1.90), (-1.30, 1.35), (-1.45, 0.20), (-1.05, -1.10)]
CAST_INNER = [(-0.40, -1.25), (0.40, -1.25), (0.70, -0.75), (1.00, 0.20), (0.90, 1.00),
              (0.50, 1.40), (-0.50, 1.40), (-0.90, 1.00), (-1.00, 0.20), (-0.70, -0.75)]

CHEVRON = [(0.00, -0.95), (0.40, -0.55), (0.40, -0.38), (0.00, -0.78), (-0.40, -0.38), (-0.40, -0.55)]


class TankRenderer(GunVehicleRenderer):
    HULL_HALF_M = HULL_HALF_M

    # ---------- корпус ----------

    def _hull_shift_m(self, spec):
        return layout_of(spec).axis_fwd_m

    def _build_hull(self, paint, look, spec):
        ppm = self._ppm
        layout = layout_of(spec)
        size = 2 * math.ceil(HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS, 0.0, layout.axis_fwd_m)   # координаты корпуса: центр корпуса = (0, 0)

        hull_main = _paint(HULL_MAIN, paint)
        hull_light = _paint(HULL_LIGHT, paint)
        hull_dark = _paint(HULL_DARK, paint)
        deck = _paint(DECK, paint)

        pen.poly(hull_main, layout.outline)

        for fx, fy, fw, fh in layout.fender_rects:           # подкрылки (полки над гусеницами)
            pen.rect(hull_dark, fx, fy, fw, fh)

        self._draw_skirts(pen, look.side + layout.base_skirt, paint, layout)

        if layout.nose == NOSE_PIKE:
            self._draw_pike_plate(pen, layout, hull_light, hull_main)
        else:
            pen.poly(hull_light, layout.front_plate)
        pen.rect(deck, *layout.deck_rect)

        self._draw_front_kit(pen, look.front, paint, layout)
        self._draw_front_screen(pen, look.screen, paint, layout)

        # Погон башни: тёмное кольцо вокруг оси
        pen.ellipse(_paint(RING, paint), 0.0, -layout.axis_fwd_m,
                    layout.ring_r_m, layout.ring_r_m, outline=None)

        hx, hy, hr = layout.hatch                            # люк механика-водителя
        hy = max(hy, layout.deck_rect[1] + hr + 0.12)        # не заходит на лобовую плиту и скаты носа
        pen.ellipse(hull_dark, hx, hy, hr, hr)

        gx, gy, gw, gh = layout.grill_rect                   # МТО: решётка и жалюзи
        pen.rect(GRILL, gx, gy, gw, gh)
        ly = gy + 0.30
        while ly < gy + gh - 0.10:
            pen.line(GRILL_LINE, gx + 0.15, ly, gx + gw - 0.15, ly, 0.05)
            ly += 0.25

        pen.rect(hull_dark, *layout.rear_plate)              # кормовая плита
        self._draw_exhaust(pen, look.speed, layout)

        return pygame.transform.smoothscale(big, (size, size))

    @staticmethod
    def _draw_pike_plate(pen, layout, light, main):
        """Щучий нос: два ската от острия к плечам, левый светлее правого."""
        left, tip, right = layout.front_plate
        mid = (0.0, left[1])
        pen.poly(light, [left, tip, mid])
        pen.poly(main, [tip, right, mid])

    # ---------- башня ----------

    def _build_turret(self, team_color, paint, look, emblem, spec):
        ppm = self._ppm
        style = layout_of(spec).turret_style
        size = 2 * math.ceil(TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)                            # центр спрайта = ось башни

        colors = (_paint(TURRET_MAIN, paint), _paint(TURRET_LIGHT, paint), _paint(TURRET_DARK, paint))
        if style == "oval":
            self._turret_oval(pen, team_color, look, emblem, spec, *colors)
        elif style == "cast":
            self._turret_cast(pen, team_color, look, emblem, spec, *colors)
        else:
            self._turret_hex(pen, team_color, look, emblem, spec, *colors)

        return pygame.transform.smoothscale(big, (size, size))

    @staticmethod
    def _chevrons(pen, s, dy):
        """Двойной шеврон острием вперёд (Уничтожитель); s — масштаб, dy — сдвиг по y."""
        for k in (0.0, 0.25 * s):
            pen.poly(EMBLEM_COLOR, [(x * s, y * s + dy + k) for x, y in CHEVRON], outline=None)

    def _turret_hex(self, pen, team, look, emblem, spec, main, light, dark):
        if look.front > 0:                  # утолщённая броня: тёмный «обод»
            k = 1.0 + 0.10 * look.front
            pen.poly(dark, [(x * k, y * k) for x, y in HEX_POINTS])
        pen.poly(main, HEX_POINTS)
        pen.poly(light, HEX_INNER, outline=dark)
        if emblem == "chevron":
            self._chevrons(pen, 1.0, 0.0)
        pen.rect(team, -0.55, -spec.GUN_FRONT_M, 1.10, 0.60, r=0.08)    # маска орудия
        pen.ellipse(dark, 0.42, 0.30, 0.42, 0.42)                       # люк командира
        pen.ellipse(team, 0.42, 0.30, 0.32, 0.32)
        if look.speed > 0:                  # антенна
            pen.line(OUTLINE, -0.75, 1.0, -0.95, 1.95, 0.04)
            pen.ellipse(dark, -0.75, 1.0, 0.10, 0.10)

    def _turret_oval(self, pen, team, look, emblem, spec, main, light, dark):
        """Лёгкий корпус: небольшая овальная башня по центру."""
        if look.front > 0:
            k = 1.0 + 0.10 * look.front
            pen.ellipse(dark, 0.0, 0.10, 0.85 * k, 1.15 * k)
        pen.ellipse(main, 0.0, 0.10, 0.85, 1.15)
        pen.ellipse(light, 0.0, 0.05, 0.55, 0.78, outline=dark)
        if emblem == "chevron":
            self._chevrons(pen, 0.7, 0.20)
        pen.rect(team, -0.40, -spec.GUN_FRONT_M, 0.80, 0.50, r=0.08)
        pen.ellipse(dark, 0.32, 0.45, 0.28, 0.28)
        pen.ellipse(team, 0.32, 0.45, 0.20, 0.20)
        if look.speed > 0:
            pen.line(OUTLINE, -0.50, 0.55, -0.65, 1.35, 0.04)
            pen.ellipse(dark, -0.50, 0.55, 0.09, 0.09)

    def _turret_cast(self, pen, team, look, emblem, spec, main, light, dark):
        """Тяжёлый корпус: крупная литая башня каплей, широкая маска."""
        if look.front > 0:
            k = 1.0 + 0.07 * look.front     # максимум 1.14: помещается в заготовку
            pen.poly(dark, [(x * k, y * k) for x, y in CAST_POINTS])
        pen.poly(main, CAST_POINTS)
        pen.poly(light, CAST_INNER, outline=dark)
        if emblem == "chevron":
            self._chevrons(pen, 1.0, 0.0)
        pen.rect(team, -0.65, -spec.GUN_FRONT_M, 1.30, 0.60, r=0.08)
        pen.ellipse(dark, 0.55, 0.50, 0.38, 0.38)                       # люк командира
        pen.ellipse(team, 0.55, 0.50, 0.28, 0.28)
        pen.ellipse(dark, -0.60, 0.90, 0.26, 0.26)                      # люк заряжающего
        if look.speed > 0:
            pen.line(OUTLINE, -0.90, 1.0, -1.05, 1.95, 0.04)
            pen.ellipse(dark, -0.90, 1.0, 0.10, 0.10)