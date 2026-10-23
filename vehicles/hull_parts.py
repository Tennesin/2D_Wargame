"""vehicles/hull_parts.py — детали корпуса: бортовые экраны, швы, накладная броня, носы, лобовые экраны,
выхлоп, моторная крышка. Миксин для GunVehicleRenderer, состояния не хранит."""
import math

from engine import lerp_color, shrink_polygon
from .hulls import NOSE_PIKE
from .hull_noses import screen_pieces, SCREEN_OFFSET_M, SCREEN_THICK_M, PIKE_BAND_M
from .sprite_pen import (
    OUTLINE, OUTLINE_W, SKIRT_MAIN, SCREEN_MAIN, SCREEN_MESH,
    HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK, GRILL, GRILL_LINE,
    apply_paint, outline_x_at,
)

SEAM_FRACS = (0.30, 0.62)    # где на палубе идут поперечные швы (доли длины палубы)
SEAM_W_M = 0.05              # толщина шва, м
RIVET_R_M = 0.04             # радиус заклёпки, м
RIVET_STEP_M = 0.5           # примерный шаг заклёпок вдоль шва, м

class HullPartsMixin:

    PIKE_KIT_INSET = 0.78       # во сколько раз пластина меньше полосы ската (остаётся рамка вокруг)
    PIKE_KIT_LIGHTEN = 0.25     # насколько пластина светлее своей полосы

    @staticmethod
    def _draw_skirts(pen, level, paint, layout):
        """Бортовые экраны поверх гусениц. Не выходят за габарит гусениц, хитбокс не меняется."""
        if level <= 0:
            return
        color = apply_paint(SKIRT_MAIN, paint)
        y0, y1, width = layout.skirt_levels[min(level, len(layout.skirt_levels)) - 1]
        n = max(1, round((y1 - y0) / layout.skirt_pitch_m))   # плиты с зазором
        step = (y1 - y0) / n
        outer = layout.skirt_outer_x
        for x in (outer - width, -outer):
            for i in range(n):
                pen.rect(color, x, y0 + i * step + 0.03, width, step - 0.06)

    @staticmethod
    def _draw_seams(pen, layout, color):
        """Поперечные швы листов палубы от борта до борта, с рядом заклёпок.
        Шов доходит до самого контура корпуса, поэтому пересекает палубу и стыкуется с бортами:
        это «сшивает» части корпуса. Рисовать ПОСЛЕ палубы и ДО решёток, люков и башни."""
        dx, dy, dw, dh = layout.deck_rect
        for t in SEAM_FRACS:
            y = dy + dh * t
            lo, hi = outline_x_at(layout.outline, y)
            if lo is None:
                continue
            x0, x1 = lo + 0.06, hi - 0.06
            pen.line(color, x0, y, x1, y, SEAM_W_M)
            n = max(2, round((x1 - x0) / RIVET_STEP_M))
            for i in range(1, n):
                pen.ellipse(color, x0 + (x1 - x0) * i / n, y + 0.11,
                            RIVET_R_M, RIVET_R_M, outline=None)

    @staticmethod
    def _draw_front_kit(pen, level, paint, layout):
        """Накладная броня на лбу. Плоский лоб: один многоугольник (+ планка и клинья на уровне 2).
        Щучий нос: отдельные пластины на скатах (см. _draw_pike_kit)."""
        if level <= 0:
            return
        if layout.nose == NOSE_PIKE:
            HullPartsMixin._draw_pike_kit(pen, paint, layout)
            return

        color = apply_paint(lerp_color(HULL_LIGHT, HULL_MAIN, 0.5), paint)
        edge = apply_paint(HULL_DARK, paint)

        poly = layout.front_kit_poly
        pen.poly(color, poly, outline=edge)
        cx = sum(x for x, _ in poly) / len(poly)
        cy = sum(y for _, y in poly) / len(poly)
        for x, y in poly:                                   # заклёпка в 0.14 м от каждого угла к центру
            dx, dy = cx - x, cy - y
            ln = math.hypot(dx, dy) or 1.0
            pen.ellipse(edge, x + dx / ln * 0.14, y + dy / ln * 0.14,
                        RIVET_R_M, RIVET_R_M, outline=None)

        if level >= 2:
            bx, by, bw, bh = layout.front_kit_bar
            pen.rect(color, bx, by, bw, bh, outline=edge, r=0.05)
            for sx in (-1, 1):                              # в раскладке задан правый клин
                pen.poly(color, [(sx * x, y) for x, y in layout.front_kit_wedge], outline=edge)

    @staticmethod
    def _draw_pike_kit(pen, paint, layout):
        """Накладка щучьего носа: по одной пластине на каждый скат. Пластина лежит внутри своей
        полосы (те же четыре угла, что в _draw_pike_plate), поэтому гребень по оси и V-шов остаются
        видны. Цвет = цвет полосы, чуть светлее: сохраняется свет слева."""
        left, tip, right = layout.front_plate
        b = PIKE_BAND_M
        apex = (0.0, tip[1] + b)
        bands = (
            ([left, tip, apex, (left[0], left[1] + b)], lerp_color(HULL_MAIN, HULL_LIGHT, 0.45)),
            ([tip, right, (right[0], right[1] + b), apex], lerp_color(HULL_MAIN, DECK, 0.30)),
        )
        edge = apply_paint(HULL_DARK, paint)
        for band, band_color in bands:
            cx = sum(x for x, _ in band) / 4.0
            cy = sum(y for _, y in band) / 4.0
            plate = shrink_polygon(band, cx, cy, HullPartsMixin.PIKE_KIT_INSET)
            color = apply_paint(lerp_color(band_color, HULL_LIGHT, HullPartsMixin.PIKE_KIT_LIGHTEN), paint)
            pen.poly(color, plate, outline=edge)
            px = sum(x for x, _ in plate) / 4.0
            py = sum(y for _, y in plate) / 4.0
            for x, y in plate:                              # заклёпка в 0.10 м от угла к центру пластины
                dx, dy = px - x, py - y
                ln = math.hypot(dx, dy) or 1.0
                pen.ellipse(edge, x + dx / ln * 0.10, y + dy / ln * 0.10,
                            RIVET_R_M, RIVET_R_M, outline=None)

    @staticmethod
    def _draw_front_screen(pen, level, paint, layout):
        """Четыре тонких листа перед лбом на стойках. level только включает показ:
        число и толщина листов от ползунка не зависят."""
        if level <= 0:
            return
        color = apply_paint(SCREEN_MAIN, paint)
        off = SCREEN_OFFSET_M
        for (ax, ay), (bx, by), (nx, ny) in screen_pieces(layout):
            p0 = (ax + nx * off, ay + ny * off)
            p1 = (bx + nx * off, by + ny * off)
            pen.line(SCREEN_MESH, ax, ay, p0[0], p0[1], 0.04)                  # стойки
            pen.line(SCREEN_MESH, bx, by, p1[0], p1[1], 0.04)
            pen.line(OUTLINE, p0[0], p0[1], p1[0], p1[1], SCREEN_THICK_M + 0.04)   # контур листа
            pen.line(color, p0[0], p0[1], p1[0], p1[1], SCREEN_THICK_M)            # сам лист

    @staticmethod
    def _draw_exhaust(pen, level, layout):
        """Выхлопные патрубки на кормовой плите."""
        if level <= 0:
            return
        r = 0.13 if level == 1 else 0.17
        for x in layout.exhaust_xs:
            pen.ellipse(GRILL, x, layout.exhaust_y, r, r)

    @staticmethod
    def _draw_deck(pen, y_end, hull_dark, deck_top, half_w=1.05, lead=0.45, min_free=0.9):
        """Моторная крышка на палубе между носом и башней."""
        y0 = deck_top + lead
        free = y_end - 0.15 - y0
        if free < min_free:
            return
        gw = half_w - 0.15
        pen.rect(hull_dark, -half_w, y0, 2.0 * half_w, free, r=0.05)        # рама крышки
        pen.rect(GRILL, -gw, y0 + 0.12, 2.0 * gw, free - 0.24)              # решётка
        ly = y0 + 0.32
        while ly < y0 + free - 0.2:                                         # жалюзи
            pen.line(GRILL_LINE, -(gw - 0.14), ly, gw - 0.14, ly, 0.05)
            ly += 0.26
        if free >= 2.2:                                                     # длинная палуба: два люка
            pen.rect(hull_dark, -gw, y0 + free / 2.0 - 0.05, 2.0 * gw, 0.10, outline=None)

    @staticmethod
    def _draw_pike_plate(pen, layout, paint):
        """Щучий нос: две полосы вдоль скатов (близкие тона) и клин палубы с V-образным передним краем.
        Рисовать ПОСЛЕ прямоугольника палубы: клин и полосы перекрывают его верхний контур."""
        left, tip, right = layout.front_plate
        hw = right[0]
        sh_y, tip_y = left[1], tip[1]
        b = PIKE_BAND_M
        apex = (0.0, tip_y + b)                    # вершина V
        lo_l, lo_r = (-hw, sh_y + b), (hw, sh_y + b)

        c_left = apply_paint(lerp_color(HULL_MAIN, HULL_LIGHT, 0.45), paint)
        c_right = apply_paint(lerp_color(HULL_MAIN, DECK, 0.30), paint)
        c_deck = apply_paint(DECK, paint)
        seam = apply_paint(HULL_DARK, paint)

        pen.poly(c_left, [left, tip, apex, lo_l], outline=None)
        pen.poly(c_right, [tip, right, lo_r, apex], outline=None)
        pen.poly(c_deck, [lo_l, apex, lo_r], outline=None)

        # наружный контур скатов (полосы перекрыли внутреннюю половину обводки корпуса)
        ow = OUTLINE_W / pen.k
        pen.line(OUTLINE, left[0], left[1], tip[0], tip[1], ow)
        pen.line(OUTLINE, tip[0], tip[1], right[0], right[1], ow)

        # гребень: от острия по оси, продолжается на клин палубы
        pen.line(seam, 0.0, tip_y + 0.06, 0.0, tip_y + b + 0.7, 0.05)

        # V-шов и заклёпки вдоль него
        for a, c in ((lo_l, apex), (apex, lo_r)):
            pen.line(seam, a[0], a[1], c[0], c[1], 0.05)
            n = max(2, round(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.45))
            for i in range(1, n):
                t = i / n
                pen.ellipse(seam, a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t - 0.10,
                            RIVET_R_M, RIVET_R_M, outline=None)

    @staticmethod
    def _draw_wedge_plate(pen, layout, paint):
        """Клин: центральная плоская плита и два боковых скоса (слева светлее, справа темнее,
        как у щучьего носа). Рисовать ПОСЛЕ прямоугольника палубы."""
        left, face_l, face_r, right = layout.front_plate
        sh_y = left[1]                                   # линия плеч
        c_face = apply_paint(HULL_LIGHT, paint)
        c_left = apply_paint(lerp_color(HULL_MAIN, HULL_LIGHT, 0.45), paint)
        c_right = apply_paint(lerp_color(HULL_MAIN, DECK, 0.30), paint)
        seam = apply_paint(HULL_DARK, paint)

        pen.poly(c_left, [left, face_l, (face_l[0], sh_y)], outline=None)
        pen.poly(c_right, [face_r, right, (face_r[0], sh_y)], outline=None)
        pen.poly(c_face, [face_l, face_r, (face_r[0], sh_y), (face_l[0], sh_y)], outline=None)

        ow = OUTLINE_W / pen.k                           # наружный контур носа
        for a, b in ((left, face_l), (face_l, face_r), (face_r, right)):
            pen.line(OUTLINE, a[0], a[1], b[0], b[1], ow)

        for x in (face_l[0], face_r[0]):                 # швы между плитами и стык с палубой
            pen.line(seam, x, face_l[1] + 0.04, x, sh_y, 0.05)
        pen.line(seam, left[0] + 0.04, sh_y, right[0] - 0.04, sh_y, 0.05)

        n = max(2, round((face_r[0] - face_l[0]) / 0.45))   # заклёпки вдоль лобового края
        for i in range(1, n):
            x = face_l[0] + (face_r[0] - face_l[0]) * i / n
            pen.ellipse(seam, x, face_l[1] + 0.14, RIVET_R_M, RIVET_R_M, outline=None)