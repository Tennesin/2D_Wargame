"""tank/sprites.py — отрисовка ОБТ: корпус и башня строятся из раскладки (vehicles/hulls.py).
Общая часть (гусеницы, ствол, тень, кэши) лежит в vehicles/sprite_base.py."""
import math

import pygame

from ..hulls import max_canvas_half_m, NOSE_PIKE, HULL_STYLE_FRONT_ENGINE, PIKE_BAND_M
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
TOOLBOX = (132, 124, 106)    # ящики ЗИП на крыльях
CABLE = (66, 60, 52)

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
        front_engine = layout.hull_style == HULL_STYLE_FRONT_ENGINE

        pen.poly(hull_main, layout.outline)

        for fx, fy, fw, fh in layout.fender_rects:           # подкрылки (полки над гусеницами)
            pen.rect(hull_dark, fx, fy, fw, fh)

        self._draw_skirts(pen, look.side + layout.base_skirt, paint, layout)

        if layout.nose == NOSE_PIKE:
            pen.rect(deck, *layout.deck_rect)
            self._draw_pike_plate(pen, layout, paint)
        else:
            pen.poly(hull_light, layout.front_plate)
            pen.rect(deck, *layout.deck_rect)
        self._draw_seams(pen, layout, hull_dark)

        self._draw_front_kit(pen, look.front, paint, layout)
        self._draw_front_screen(pen, look.screen, paint, layout)

        if front_engine:
            self._draw_front_engine(pen, layout, hull_dark)   # до погона: башня и погон перекроют лишнее

        # Погон башни: тёмное кольцо вокруг оси
        pen.ellipse(_paint(RING, paint), 0.0, -layout.axis_fwd_m,
                    layout.ring_r_m, layout.ring_r_m, outline=None)

        if front_engine:
            self._draw_stowage(pen, layout, paint)            # ЗИП и трос вместо кормовой решётки
        else:
            hx, hy, hr = layout.hatch                         # люк механика-водителя
            hy = max(hy, layout.deck_rect[1] + hr + 0.12)
            pen.ellipse(hull_dark, hx, hy, hr, hr)

            gx, gy, gw, gh = layout.grill_rect                # МТО: решётка и жалюзи
            pen.rect(GRILL, gx, gy, gw, gh)
            ly = gy + 0.30
            while ly < gy + gh - 0.10:
                pen.line(GRILL_LINE, gx + 0.15, ly, gx + gw - 0.15, ly, 0.05)
                ly += 0.25

        pen.rect(hull_dark, *layout.rear_plate)               # кормовая плита
        self._draw_exhaust(pen, look.speed, layout)

        return self._finish(pygame.transform.smoothscale(big, (size, size)))

    def _draw_front_engine(self, pen, layout, hull_dark):
        """Моторная крышка на носу тяжёлого корпуса: от начала палубы до переднего края погона.
        Места зависит от положения башни: чем дальше она уехала назад, тем длиннее крышка."""
        y_end = -layout.axis_fwd_m - layout.ring_r_m
        lead = PIKE_BAND_M + 0.10 if layout.nose == NOSE_PIKE else 0.25
        half_w = layout.deck_rect[2] / 2.0 - 0.30
        self._draw_deck(pen, y_end, hull_dark, layout.deck_rect[1],
                        half_w=half_w, lead=lead, min_free=0.6)

    @staticmethod
    def _draw_stowage(pen, layout, paint):
        """Ящики ЗИП на левом крыле и трос на правом (как у ПТ-САУ)."""
        (rfx, rfy, rfw, rfh), (lfx, lfy, lfw, lfh) = layout.fender_rects
        tool = _paint(TOOLBOX, paint)
        pen.rect(tool, lfx, lfy + lfh * 0.45, lfw, 0.95, r=0.04)
        pen.rect(tool, lfx, lfy + lfh * 0.20, lfw, 0.60, r=0.04)
        pen.line(CABLE, rfx + rfw / 2.0, rfy + 0.4, rfx + rfw / 2.0, rfy + rfh - 0.4, 0.07)

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

        return self._finish(pygame.transform.smoothscale(big, (size, size)), (41, 67))

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
        """Лёгкий корпус: широкая башня со скруглёнными углами, ширина одинакова по всей длине.
        Тело: x от -1.0 до 1.0, y от -1.15 до 1.55 (центр по y = 0.20)."""
        if look.front > 0:                              # утолщённая броня: тёмный «обод»
            k = 1.0 + 0.08 * look.front
            pen.rect(dark, -1.00 * k, 0.20 - 1.35 * k, 2.00 * k, 2.70 * k, r=0.45)
        pen.rect(main, -1.00, -1.15, 2.00, 2.70, r=0.45)
        pen.rect(light, -0.70, -0.85, 1.40, 2.10, outline=dark, r=0.30)
        if emblem == "chevron":
            self._chevrons(pen, 0.85, 0.25)
        pen.rect(team, -0.50, -spec.GUN_FRONT_M, 1.00, 0.50, r=0.08)    # маска орудия
        pen.ellipse(dark, 0.45, 0.55, 0.32, 0.32)                       # люк командира
        pen.ellipse(team, 0.45, 0.55, 0.23, 0.23)
        if look.speed > 0:                                              # антенна
            pen.line(OUTLINE, -0.75, 0.90, -0.90, 1.75, 0.04)
            pen.ellipse(dark, -0.75, 0.90, 0.09, 0.09)

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