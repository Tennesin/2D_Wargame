"""td/sprites.py — отрисовка ПТ-САУ: корпус с деталями, рубка/опора позади оси орудия,
амбразура, лафет с маской. Орудие смотрит из передней грани рубки, а не из её середины."""
import math
import pygame

from ..hulls import NOSE_PIKE
from ..hull_noses import PIKE_BAND_M
from ..sprite_base import GunVehicleRenderer
from ..sprite_pen import (
    Pen as _Pen, apply_paint as _paint, SS,
    HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK, GRILL, GRILL_LINE,
    TURRET_MAIN, TURRET_LIGHT, TURRET_DARK,
)
from .params import TD_HULL_HALF_M, TD_TURRET_HALF_M, TD_MASK_DEPTH_M, TD_CASEMATE_AHEAD_M

SUPPORT_MAIN = (128, 120, 104)
SUPPORT_DARK = (96, 90, 78)
CABLE = (66, 60, 52)
TOOLBOX = (132, 124, 106)

# Рубка/опора: сколько метров корпуса лежит ПОЗАДИ оси орудия, по уровням опоры
CASEMATE_REACH = (1.9, 2.3, 2.8)
HULL_FRONT_MARGIN = 0.35   # рубка не заходит на лобовую плиту: её край + этот отступ
HULL_REAR_MARGIN = 0.10    # и не выходит за корму корпуса
OUTLINE_ANT = (38, 33, 28)

class TDRenderer(GunVehicleRenderer):
    HULL_HALF_M = TD_HULL_HALF_M
    HAS_TURRET_SPRITE = False

    # ==========================================
    # КОРПУС
    # ==========================================

    def _hull_shift_m(self, spec):
        return spec.layout.axis_fwd_m

    def _build_hull(self, paint, look, spec):
        ppm = self._ppm
        layout = spec.layout
        size = 2 * math.ceil(self.HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        mount = layout.axis_fwd_m
        axis = -mount                                  # ось орудия в координатах корпуса (перед = -y)
        support = spec.SUPPORT
        g = spec.CASE_K
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
        tool = _paint(TOOLBOX, paint)

        # --- границы рубки: выводятся из раскладки (для TD_LAYOUT это -2.55 и 2.8, как раньше) ---
        front_limit = min(y for _, y in layout.front_plate) + HULL_FRONT_MARGIN
        rear_limit = max(y for _, y in layout.outline) - HULL_REAR_MARGIN
        front = max(axis - TD_CASEMATE_AHEAD_M, front_limit)
        rear = min(axis + CASEMATE_REACH[support] * g, rear_limit)
        rear = max(rear, front + 1.3)
        wf = 0.65 + 0.30 * g
        wr = 0.80 + 0.35 * g + (0.10 if support >= 2 else 0.0)

        # Корпус и подкрылки
        pen.poly(hull_main, layout.outline)
        for fx, fy, fw, fh in layout.fender_rects:
            pen.rect(hull_dark, fx, fy, fw, fh)

        # Детали на крыльях: ящики ЗИП слева, буксирный трос справа (от положения подкрылков)
        (rfx, _, rfw, _), (lfx, _, lfw, _) = layout.fender_rects
        pen.rect(tool, lfx, 0.45, lfw, 0.95, r=0.04)
        pen.rect(tool, lfx, -1.75, lfw, 0.55, r=0.04)
        pen.line(GRILL_LINE, lfx + lfw / 2, 0.60, lfx + lfw / 2, 1.30, 0.04)
        pen.line(CABLE, rfx + rfw / 2, -1.85, rfx + rfw / 2, 2.35, 0.07)
        for cy in (-1.3, 0.2, 1.7):
            pen.rect(GRILL, rfx + 0.05, cy, 0.12, 0.14, outline=None)

        self._draw_skirts(pen, look.side + layout.base_skirt, paint, layout)

        # Лобовая плита, палуба, накладная броня и экраны
        if layout.nose == NOSE_PIKE:
            pen.rect(deck, *layout.deck_rect)
            self._draw_pike_plate(pen, layout, paint)
        else:
            pen.poly(hull_light, layout.front_plate)
            pen.rect(deck, *layout.deck_rect)
        self._draw_seams(pen, layout, hull_dark)
        self._draw_front_kit(pen, look.front, paint, layout)
        self._draw_front_screen(pen, look.screen, paint, layout)

        # Моторная часть позади рубки (только когда орудие на лбу)
        if support == 0 and rear < 2.0:
            gy = rear + 0.2
            gh = 2.75 - gy
            pen.rect(GRILL, -0.95, gy, 1.90, gh)
            ly = gy + 0.2
            if gh >= 1.7:                               # места хватает: два вентилятора
                for fx in (-0.48, 0.48):
                    pen.ellipse(GRILL_LINE, fx, gy + 0.62, 0.34, 0.34)
                    pen.ellipse(GRILL, fx, gy + 0.62, 0.20, 0.20)
                ly = gy + 1.15
            while ly < 2.65:
                pen.line(GRILL_LINE, -0.80, ly, 0.80, ly, 0.05)
                ly += 0.25
            pen.rect(hull_dark, -0.95, 2.50, 1.90, 0.25)  # кормовая планка
        lead = PIKE_BAND_M + 0.10 if layout.nose == NOSE_PIKE else 0.45
        self._draw_deck(pen, front, hull_dark, layout.deck_rect[1], lead=lead)

        # Опора (уровни 1 и 2): цоколь под рубкой; на уровне 2 ещё гладкий кормовой короб
        if support >= 1:
            slab_w = min(wr + 0.10, 1.34)
            pen.poly(sup_dark, [(-slab_w, front + 0.20), (slab_w, front + 0.20),
                                (slab_w, rear + 0.08), (-slab_w, rear + 0.08)])
            if support >= 2:
                by0 = max(front + 1.0, rear - 0.80)
                pen.rect(sup_main, -1.05, by0, 2.10, rear + 0.08 - by0, r=0.05)

        # Рубка: передняя грань чуть впереди оси, тело уходит назад
        pen.poly(case_main, [(-wf, front), (wf, front), (wr, front + 0.55), (wr, rear - 0.35),
                             (wr - 0.30, rear), (-wr + 0.30, rear), (-wr, rear - 0.35),
                             (-wr, front + 0.55)])
        inset = 0.28
        pen.poly(case_light, [(-wf + inset, front + inset), (wf - inset, front + inset),
                              (wr - inset, front + 0.55 + inset * 0.4),
                              (wr - inset, rear - 0.35 - inset * 0.4),
                              (wr - 0.30 - inset, rear - inset),
                              (-wr + 0.30 + inset, rear - inset),
                              (-wr + inset, rear - 0.35 - inset * 0.4),
                              (-wr + inset, front + 0.55 + inset * 0.4)],
                 outline=case_dark)

        # Крыша: швы между листами и «лоток» хода казённика
        seam_in = wr - inset
        for sy in (front + 1.15, rear - 1.05):
            if front + 0.9 < sy < rear - 0.5:
                pen.line(case_dark, -seam_in, sy, seam_in, sy, 0.04)
        half = math.radians(spec.TURRET_ARC_DEG / 2.0)
        lb = min(1.0, rear - 0.25 - axis)                       # длина лотка назад от оси
        t = lb * math.tan(half)                                 # на сколько он расширяется к корме
        pen.poly(case_dark, [(-0.32, axis), (0.32, axis),
                             (0.32 + t, axis + lb), (-0.32 - t, axis + lb)], outline=None)

        # Амбразура: орудие смотрит из передней грани, а не стоит на круглой основе
        ew = 0.55 + 0.15 * g
        pen.poly(case_dark, [(-ew, front), (ew, front), (ew - 0.20, front + 0.55), (-(ew - 0.20), front + 0.55)],
                 outline=None)

        # Детали крыши рубки (позади орудия, чтобы не пересекаться с казёнником)
        for sx in (-1, 1):                              # перископы по углам передней части
            pen.rect(case_dark, sx * 0.62 - 0.15, front + 0.62, 0.30, 0.10, r=0.02)
        pen.ellipse(case_dark, 0.72, axis + 0.90, 0.26, 0.26)       # купол командира
        pen.ellipse(case_main, 0.72, axis + 0.90, 0.15, 0.15, outline=None)
        pen.rect(case_dark, -0.92, axis + 0.72, 0.42, 0.40, r=0.03)  # люк заряжающего
        if rear - 0.62 >= axis + 1.0:                   # вентрешётка (только если не под казёнником)
            pen.rect(GRILL, -0.35, rear - 0.62, 0.70, 0.34)
            for vy in (rear - 0.50, rear - 0.38):
                pen.line(GRILL_LINE, -0.28, vy, 0.28, vy, 0.04)
        if look.speed > 0:                              # антенна
            ay = axis + 0.95
            pen.line(OUTLINE_ANT, -0.80, ay, -0.95, min(ay + 0.6, rear - 0.1), 0.04)
            pen.ellipse(case_dark, -0.80, ay, 0.09, 0.09)

        self._draw_exhaust(pen, look.speed, layout)
        return self._finish(pygame.transform.smoothscale(big, (size, size)))

    # ==========================================
    # ЛАФЕТ ОРУДИЯ
    # ==========================================

    def _build_mantlet(self, team_color, paint, look, spec):
        """Простая одноцветная маска орудия без теней и черной полоски."""
        ppm = self._ppm
        size = 2 * math.ceil(TD_TURRET_HALF_M * ppm)

        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)

        g = spec.CASE_K
        k = 1.0 + 0.12 * look.front
        front = spec.GUN_FRONT_M                     # передний край, м вперёд от оси
        back = front - TD_MASK_DEPTH_M               # задний край (может уходить за ось, это нормально)

        wf = (0.50 * g + 0.10) * k
        wb = wf + 0.22 * g

        # Основная маска: один цвет, никаких теней и полосок.
        pen.poly(team_color, [
            (-(wf - 0.12), -front),
            (wf - 0.12, -front),
            (wf, -front + 0.12),
            (wb, -back),
            (-wb, -back),
            (-wf, -front + 0.12),
        ])

        return self._finish(pygame.transform.smoothscale(big, (size, size)), (41, 67))

    def _draw_front_layer(self, screen, tank, cx, cy, hull_k, hull_scale, team, paint, look):
        """Маска вращается вместе с корпусом (hull_k), а не с орудием, и лежит поверх ствола."""
        spec = tank.spec
        base_key = ("mantlet", team, paint, look.front, spec.CASE_K, spec.GUN_FRONT_M)
        sprite = self._rotated(
            "mantlet", base_key,
            lambda: self._turret_cache.get_or_build(
                base_key, lambda: self._build_mantlet(team, paint, look, spec)),
            hull_k, hull_scale)
        screen.blit(sprite, sprite.get_rect(center=(cx, cy)))