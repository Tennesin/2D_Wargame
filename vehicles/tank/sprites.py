"""tank/sprites.py — отрисовка ОБТ: корпус и башня строятся из раскладки (vehicles/hulls.py).
Общая часть (гусеницы, ствол, тень, кэши) лежит в vehicles/sprite_base.py."""
import math
import pygame

from engine import clamp, lerp_color
from ..hulls import max_canvas_half_m, NOSE_PIKE, NOSE_WEDGE, HULL_STYLE_FRONT_ENGINE
from ..hull_noses import PIKE_BAND_M
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
# Плитчатая башня тяжёлого корпуса (ось башни = (0, 0), перёд = -y), метры эталонного спрайта
SLAB_HALF_W = 1.30                  # полуширина
SLAB_FRONT = 1.55                   # передняя грань впереди оси (маска торчит ещё на 0.30)
SLAB_REAR = 1.45                    # задняя грань позади оси
SLAB_FRONT_CHAMFER = (0.55, 0.60)   # передняя фаска: (по x, по y)
SLAB_REAR_CHAMFER = (0.30, 0.30)    # задняя фаска
SLAB_RIM = 0.20                     # ширина боковых граней (рамка вокруг верхней плиты)
SLAB_LIGHT_DIR = (-0.55, -0.83)     # откуда падает свет: слева-сверху

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
        elif layout.nose == NOSE_WEDGE:
            pen.rect(deck, *layout.deck_rect)
            self._draw_wedge_plate(pen, layout, paint)
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
        """Моторная крышка на носу тяжёлого корпуса: от начала палубы до передней кромки башни."""
        reach = layout.turret_front_m * layout.turret_k * layout.turret_scale_range[1]
        y_end = -layout.axis_fwd_m - reach
        if layout.nose == NOSE_PIKE:
            lead = PIKE_BAND_M + 0.10
        elif layout.nose == NOSE_WEDGE:
            lead = 0.20
        else:
            lead = 0.25
        half_w = layout.deck_rect[2] / 2.0 - 0.30
        self._draw_deck(pen, y_end, hull_dark, layout.deck_rect[1],
                        half_w=half_w, lead=lead, min_free=0.6)

    @staticmethod
    def _draw_stowage(pen, layout, paint):
        """Ящики ЗИП слева и трос справа лежат на бортовых экранах."""
        tool = _paint(TOOLBOX, paint)
        y0, y1, w = layout.skirt_levels[0]
        cx = layout.skirt_outer_x - w / 2.0              # середина полосы экрана
        span = y1 - y0
        pen.rect(tool, -cx - 0.15, y0 + span * 0.50, 0.30, 0.95, r=0.04)
        pen.rect(tool, -cx - 0.15, y0 + span * 0.20, 0.30, 0.60, r=0.04)
        pen.line(CABLE, cx, y0 + 0.5, cx, y1 - 0.5, 0.07)

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
        elif style == "slab":
            self._turret_slab(pen, team_color, look, emblem, spec, *colors)
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

    @staticmethod
    def _slab_points(inset=0.0, front_extra=0.0):
        """Контур плитчатой башни: плоский лоб, срезанные передние углы, параллельные борта,
        плоская корма. inset сжимает контур внутрь (для верхней плиты), front_extra утолщает лоб."""
        w = SLAB_HALF_W - inset
        f = SLAB_FRONT - inset - front_extra
        r = SLAB_REAR - inset
        fcx, fcy = SLAB_FRONT_CHAMFER
        rcx, rcy = SLAB_REAR_CHAMFER
        return [(-(w - fcx), -f), (w - fcx, -f), (w, -f + fcy), (w, r - rcy),
                (w - rcx, r), (-(w - rcx), r), (-w, r - rcy), (-w, -f + fcy)]

    def _turret_slab(self, pen, team, look, emblem, spec, main, light, dark):
        """Тяжёлый корпус: башня-«плита» (ориентир: башня Мауса в плане)."""
        outer = self._slab_points()
        inner = self._slab_points(SLAB_RIM, 0.07 * look.front)   # броня: толще лобовая грань
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

        for sy in (0.0, 1.0):                                    # швы листов крыши
            pen.line(dark, -0.95, sy, 0.95, sy, 0.04)
        if emblem == "chevron":
            self._chevrons(pen, 0.9, -0.05)

        pen.rect(team, -0.55, -spec.GUN_FRONT_M, 1.10, 0.50, r=0.08)   # маска уже передней грани
        pen.ellipse(dark, 0.62, 0.45, 0.36, 0.36)                      # люк командира
        pen.ellipse(team, 0.62, 0.45, 0.26, 0.26)
        pen.ellipse(dark, -0.62, 0.62, 0.26, 0.26)                     # люк заряжающего
        if look.speed > 0:                                             # антенна
            pen.line(OUTLINE, -0.80, 0.85, -0.92, 1.30, 0.04)
            pen.ellipse(dark, -0.80, 0.85, 0.09, 0.09)