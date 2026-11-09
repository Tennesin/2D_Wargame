"""vehicles/td/sprites.py — отрисовка ПТ-САУ"""
import math
import pygame

from vehicles.chassis.hulls import NOSE_PIKE
from vehicles.render.base import GunVehicleRenderer
from vehicles.render.pen import (
    Pen as _Pen, apply_paint as _paint, SS,
    HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK,
    TURRET_MAIN, TURRET_LIGHT, TURRET_DARK,
)
from vehicles.parts import (
    parts_for, draw_parts, PartCtx, SURFACE_HULL,
    BAND_FENDER, BAND_DECK, BAND_COVER, BAND_TOP
)
from .casemate import casemate_box, CASEMATE_INSET
from .params import TD_HULL_HALF_M, TD_TURRET_HALF_M, TD_MASK_DEPTH_M

SUPPORT_MAIN = (128, 120, 104)
SUPPORT_DARK = (96, 90, 78)

class TDRenderer(GunVehicleRenderer):
    HULL_HALF_M = TD_HULL_HALF_M
    HAS_TURRET_SPRITE = False
    DESIGN_KIND = "td"                                   # ключ авто-набора деталей

    # ==========================================
    # КОРПУС
    # ==========================================

    def _hull_shift_m(self, spec):
        return spec.layout.axis_fwd_m

    def _build_hull(self, paint, look, spec):
        """Шаблон корпуса безбашенной техники (ПТ-САУ и САУ). Наследник меняет только хуки:
        _draw_hull_back и _draw_superstructure (структура). Детали берутся из vehicles/parts."""
        ppm = self._ppm
        layout = spec.layout
        size = 2 * math.ceil(self.HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS, 0.0, layout.axis_fwd_m)       # центр спрайта = ось орудия
        parts = parts_for(self.DESIGN_KIND, spec, SURFACE_HULL, look)
        ctx = PartCtx(paint=paint, look=look, layout=layout)

        self._draw_hull_back(pen, paint, look, spec)
        self._draw_hull_base(pen, paint, look, spec, parts, ctx)
        draw_parts(pen, parts, BAND_COVER, ctx)                 # моторная часть и крышка: до рубки
        self._draw_superstructure(pen, paint, look, spec)
        draw_parts(pen, parts, BAND_TOP, ctx)                   # крыша рубки, антенна, выхлоп
        return self._finish(pygame.transform.smoothscale(big, (size, size)))

    # ---------- хук ----------

    def _draw_hull_back(self, pen, paint, look, spec):
        """Хук: то, что лежит позади корпуса и перекрывается им (сошник САУ). По умолчанию ничего."""

    # ---------- общая часть ----------

    def _draw_hull_base(self, pen, paint, look, spec, parts, ctx):
        """Корпус, подкрылки с деталями, бортовые экраны, лоб, палуба с швами, накладная броня и лобовые экраны."""
        layout = spec.layout
        hull_main = _paint(HULL_MAIN, paint)
        hull_light = _paint(HULL_LIGHT, paint)
        hull_dark = _paint(HULL_DARK, paint)
        deck = _paint(DECK, paint)

        pen.poly(hull_main, layout.outline)
        for fx, fy, fw, fh in layout.fender_rects:
            pen.rect(hull_dark, fx, fy, fw, fh)
        draw_parts(pen, parts, BAND_FENDER, ctx)                # ящики ЗИП и трос на крыльях
        self._draw_skirts(pen, look.side + layout.base_skirt, paint, layout)

        if layout.nose == NOSE_PIKE:
            pen.rect(deck, *layout.deck_rect)
            self._draw_pike_plate(pen, layout, paint)
        else:
            pen.poly(hull_light, layout.front_plate)
            pen.rect(deck, *layout.deck_rect)
        draw_parts(pen, parts, BAND_DECK, ctx)                  # швы палубы
        self._draw_front_kit(pen, look.front, paint, layout)
        self._draw_front_screen(pen, look.screen, paint, layout)

    # ---------- рубка (структура) ----------

    def _draw_superstructure(self, pen, paint, look, spec):
        """ПТ-САУ: опора и рубка. Моторная часть, крышка и детали крыши: см. defaults.py (_td_hull)."""
        axis, front, rear, wf, wr = casemate_box(spec)
        support = spec.SUPPORT

        case_main = _paint(TURRET_MAIN, paint)
        case_light = _paint(TURRET_LIGHT, paint)
        case_dark = _paint(TURRET_DARK, paint)
        sup_main = _paint(SUPPORT_MAIN, paint)
        sup_dark = _paint(SUPPORT_DARK, paint)

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
        inset = CASEMATE_INSET
        pen.poly(case_light, [(-wf + inset, front + inset), (wf - inset, front + inset),
                              (wr - inset, front + 0.55 + inset * 0.4),
                              (wr - inset, rear - 0.35 - inset * 0.4),
                              (wr - 0.30 - inset, rear - inset),
                              (-wr + 0.30 + inset, rear - inset),
                              (-wr + inset, rear - 0.35 - inset * 0.4),
                              (-wr + inset, front + 0.55 + inset * 0.4)],
                 outline=case_dark)

    # ==========================================
    # ЛАФЕТ ОРУДИЯ (без изменений)
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