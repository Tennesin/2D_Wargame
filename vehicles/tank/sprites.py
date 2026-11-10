"""vehicles/tank/sprites.py — отрисовка ОБТ."""
import math
import pygame

from engine import clamp, lerp_color
from vehicles.chassis.hulls import max_canvas_half_m, NOSE_PIKE, NOSE_WEDGE
from vehicles.render.base import GunVehicleRenderer
from vehicles.render.pen import (
    Pen as _Pen, apply_paint as _paint, SS,
    HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK, RING,
    TURRET_MAIN, TURRET_LIGHT, TURRET_DARK,
)
from vehicles.parts import (
    parts_for, draw_parts, PartCtx, SURFACE_HULL, SURFACE_TURRET,
    BAND_FENDER, BAND_DECK, BAND_COVER, BAND_TOP
)
from vehicles.parts.shapes import HEX_POINTS, HEX_INNER, OVAL_RECT, slab_points

HULL_HALF_M = max_canvas_half_m()   # один холст на все раскладки
TURRET_HALF_M = 2.4                 # заготовка башни (без ствола): по самому крупному стилю
SLAB_RIM = 0.20                     # ширина боковых граней (рамка вокруг верхней плиты)
SLAB_LIGHT_DIR = (-0.55, -0.83)     # откуда падает свет: слева-сверху

class TankRenderer(GunVehicleRenderer):
    HULL_HALF_M = HULL_HALF_M
    DESIGN_KIND = "mbt"  # ключ авто-набора деталей

    # ---------- корпус ----------

    def _hull_shift_m(self, spec):
        return spec.layout.axis_fwd_m

    def _build_hull(self, paint, look, spec):
        ppm = self._ppm
        layout = spec.layout
        size = 2 * math.ceil(HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS, 0.0, layout.axis_fwd_m)   # координаты корпуса: центр корпуса = (0, 0)

        hull_main = _paint(HULL_MAIN, paint)
        hull_light = _paint(HULL_LIGHT, paint)
        hull_dark = _paint(HULL_DARK, paint)
        deck = _paint(DECK, paint)

        parts = parts_for(self.DESIGN_KIND, spec, SURFACE_HULL, look)
        ctx = PartCtx(paint=paint, look=look, layout=layout)

        pen.poly(hull_main, layout.outline)

        for fx, fy, fw, fh in layout.fender_rects:           # подкрылки (полки над гусеницами)
            pen.rect(hull_dark, fx, fy, fw, fh)
        draw_parts(pen, parts, BAND_FENDER, ctx)

        self._draw_skirts(pen, look.side + layout.base_skirt, paint, layout)

        if layout.nose == NOSE_PIKE:
            pen.rect(deck, *layout.deck_rect)
            self._draw_pike_plate(pen, layout, paint)
        elif layout.nose == NOSE_WEDGE:
            pen.rect(deck, *layout.deck_rect)
            self._draw_wedge_plate(pen, layout, paint)
        else:
            pen.poly(hull_light, layout.front_plate)
            pen.rect(deck, *layout.deck_rect)
        draw_parts(pen, parts, BAND_DECK, ctx)               # швы палубы

        self._draw_front_kit(pen, look.front, paint, layout)
        draw_parts(pen, parts, BAND_COVER, ctx)              # моторная крышка носа (до погона: погон и башня её перекроют)

        # Погон башни: тёмное кольцо вокруг оси
        pen.ellipse(_paint(RING, paint), 0.0, -layout.axis_fwd_m,
                    layout.ring_r_m, layout.ring_r_m, outline=None)

        draw_parts(pen, parts, BAND_TOP, ctx)                # люк, решётка, ЗИП, трос, кормовая плита, выхлоп

        return self._finish(pygame.transform.smoothscale(big, (size, size)))

    # ---------- башня ----------

    def _build_turret(self, team_color, paint, look, emblem, spec):
        ppm = self._ppm
        style = spec.layout.turret_style
        size = 2 * math.ceil(TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)                            # центр спрайта = ось башни

        parts = parts_for(self.DESIGN_KIND, spec, SURFACE_TURRET, look, emblem)
        ctx = PartCtx(paint=paint, look=look, layout=spec.layout, team=team_color, screen_mm=spec.screen_mm)

        colors = (_paint(TURRET_MAIN, paint), _paint(TURRET_LIGHT, paint), _paint(TURRET_DARK, paint))
        if style == "oval":
            self._turret_oval(pen, team_color, look, spec, parts, ctx, *colors)
        elif style == "slab":
            self._turret_slab(pen, team_color, look, spec, parts, ctx, *colors)
        else:
            self._turret_hex(pen, team_color, look, spec, parts, ctx, *colors)

        return self._finish(pygame.transform.smoothscale(big, (size, size)), (41, 67))

    def _turret_hex(self, pen, team, look, spec, parts, ctx, main, light, dark):
        if look.front > 0:
            k = 1.0 + 0.10 * look.front
            pen.poly(dark, [(x * k, y * k) for x, y in HEX_POINTS])
        pen.poly(main, HEX_POINTS)
        pen.poly(light, HEX_INNER, outline=dark)
        draw_parts(pen, parts, BAND_DECK, ctx)                          # шеврон
        pen.rect(team, -0.55, -spec.GUN_FRONT_M, 1.10, 0.60, r=0.08)    # маска орудия
        draw_parts(pen, parts, BAND_TOP, ctx)                           # люк командира, антенна

    def _turret_oval(self, pen, team, look, spec, parts, ctx, main, light, dark):
        """Лёгкий корпус: широкая башня со скруглёнными углами, ширина одинакова по всей длине."""
        if look.front > 0:
            k = 1.0 + 0.08 * look.front
            pen.rect(dark, -1.00 * k, 0.20 - 1.35 * k, 2.00 * k, 2.70 * k, r=0.45)
        pen.rect(main, *OVAL_RECT, r=0.45)
        pen.rect(light, -0.70, -0.85, 1.40, 2.10, outline=dark, r=0.30)
        draw_parts(pen, parts, BAND_DECK, ctx)                          # шеврон
        pen.rect(team, -0.50, -spec.GUN_FRONT_M, 1.00, 0.50, r=0.08)    # маска орудия
        draw_parts(pen, parts, BAND_TOP, ctx)                           # люк командира, антенна

    def _turret_slab(self, pen, team, look, spec, parts, ctx, main, light, dark):
        """Тяжёлый корпус: башня-«плита»."""
        outer = slab_points()
        inner = slab_points(SLAB_RIM, 0.07 * look.front)   # броня: толще лобовая грань
        pen.poly(main, outer)

        lx, ly = SLAB_LIGHT_DIR
        n = len(outer)
        for i in range(n):                                       # боковые грани: тон по освещению
            a, b = outer[i], outer[(i + 1) % n]
            ia, ib = inner[i], inner[(i + 1) % n]
            ex, ey = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(ex, ey)
            nx, ny = ey / ln, -ex / ln                           # наружная нормаль грани
            t = clamp(0.5 + 0.5 * (nx * lx + ny * ly), 0.0, 1.0)
            pen.poly(lerp_color(dark, light, t), [a, b, ib, ia], outline=None)
        pen.poly(light, inner, outline=dark)                     # верхняя плита

        draw_parts(pen, parts, BAND_DECK, ctx)                          # швы листов крыши, шеврон
        pen.rect(team, -0.55, -spec.GUN_FRONT_M, 1.10, 0.50, r=0.08)    # маска уже передней грани
        draw_parts(pen, parts, BAND_TOP, ctx)                           # люки, антенна