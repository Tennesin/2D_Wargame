"""td/sprites.py — отрисовка ПТ-САУ: корпус с деталями, рубка/опора позади оси орудия,
амбразура, лафет с маской. Орудие смотрит из передней грани рубки, а не из её середины."""
import math

import pygame

from ..tank.sprites import (
    TankRenderer, _Pen, _paint, SS, TRACK_X, HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK,
    GRILL, GRILL_LINE, TURRET_MAIN, TURRET_LIGHT, TURRET_DARK, APPLIQUE,
)
from .params import TD_HULL_HALF_M, TD_TURRET_HALF_M

SUPPORT_MAIN = (128, 120, 104)
SUPPORT_DARK = (96, 90, 78)
LAMP = (236, 222, 160)
CABLE = (66, 60, 52)
TOOLBOX = (132, 124, 106)

# Рубка/опора: сколько метров корпуса лежит ПОЗАДИ оси орудия, по уровням опоры
CASEMATE_REACH = (1.9, 2.3, 2.8)
CASEMATE_AHEAD = 0.45            # передняя грань рубки впереди оси орудия
HULL_FRONT_LIMIT = -2.55
HULL_REAR_LIMIT = 2.8


class TDRenderer(TankRenderer):
    HULL_HALF_M = TD_HULL_HALF_M

    def __init__(self):
        super().__init__()
        self._hull_cache.limit = 600       # вариантов корпуса больше: сдвиг оси × опора × фазы гусениц

    # ==========================================
    # КОРПУС
    # ==========================================
    def _build_hull(self, lp, rp, paint, look, spec):
        ppm = self._ppm
        size = 2 * math.ceil(self.HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        mount = spec.MOUNT_FWD_M
        axis = -mount                                  # ось орудия в координатах корпуса (перед = -y)
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
        tool = _paint(TOOLBOX, paint)

        # --- границы рубки: передняя грань чуть впереди оси, всё остальное позади неё ---
        front = max(axis - CASEMATE_AHEAD, HULL_FRONT_LIMIT)
        rear = min(axis + CASEMATE_REACH[support], HULL_REAR_LIMIT)
        rear = max(rear, front + 1.3)
        wf = 0.95                                       # полуширина передней грани
        wr = 1.15 + (0.10 if support >= 2 else 0.0)     # полуширина основной части

        # 1. Гусеницы
        self._draw_track(pen, -TRACK_X, lp)
        self._draw_track(pen, TRACK_X, rp)

        # 2. Корпус и подкрылки
        pen.poly(hull_main, [(-1.15, -2.9), (1.15, -2.9), (1.35, -2.3), (1.35, 2.65),
                             (1.15, 2.9), (-1.15, 2.9), (-1.35, 2.65), (-1.35, -2.3)])
        pen.rect(hull_dark, 1.35, -2.1, 0.22, 4.75)
        pen.rect(hull_dark, -1.57, -2.1, 0.22, 4.75)

        # 2а. Детали на крыльях: ящики ЗИП слева, буксирный трос справа
        pen.rect(tool, -1.57, 0.45, 0.22, 0.95, r=0.04)
        pen.rect(tool, -1.57, -1.75, 0.22, 0.55, r=0.04)
        pen.line(GRILL_LINE, -1.46, 0.60, -1.46, 1.30, 0.04)
        pen.line(CABLE, 1.46, -1.85, 1.46, 2.35, 0.07)
        for cy in (-1.3, 0.2, 1.7):
            pen.rect(GRILL, 1.40, cy, 0.12, 0.14, outline=None)

        self._draw_skirts(pen, look.side, paint)

        # 3. Лобовая плита, палуба, накладная броня
        pen.poly(hull_light, [(-1.15, -2.9), (1.15, -2.9), (1.35, -2.3), (-1.35, -2.3)])
        pen.rect(deck, -1.25, -2.25, 2.50, 4.60)
        self._draw_front_kit(pen, look.front, paint)

        # 3а. Детали лба: фары, перископ и люк механика-водителя
        for sx in (-1, 1):
            pen.ellipse(LAMP, sx * 1.0, -2.68, 0.11, 0.11)
        pen.rect(hull_dark, -0.95, -2.58, 0.50, 0.14, r=0.03)
        pen.ellipse(hull_dark, 0.78, -2.52, 0.20, 0.20)

        # 4. Моторная часть позади рубки (только когда орудие на лбу)
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

        # 5. Опора (уровни 1 и 2): цоколь шире рубки + косынки перед амбразурой
        if support >= 1:
            slab_w = min(wr + 0.10, 1.34)
            pen.poly(sup_dark, [(-wf - 0.10, front - 0.10), (wf + 0.10, front - 0.10),
                                (slab_w, front + 0.55), (slab_w, rear + 0.08),
                                (-slab_w, rear + 0.08), (-slab_w, front + 0.55)])
            for sx in (-1, 1):                          # раскосы перед передней гранью
                pen.poly(sup_main, [(sx * (wf - 0.40), front), (sx * (wf + 0.05), front),
                                    (sx * (wf + 0.05), front - 0.55)])
            if support >= 2:                            # кормовой короб с жалюзи
                by0 = max(front + 1.0, rear - 0.80)
                pen.rect(sup_main, -1.05, by0, 2.10, rear + 0.08 - by0, r=0.05)
                ry = by0 + 0.18
                while ry < rear - 0.05:
                    pen.line(GRILL_LINE, -0.90, ry, 0.90, ry, 0.05)
                    ry += 0.22
            # упор для ствола в походном положении (ствол лежит на носу над корпусом)
            pen.rect(GRILL, -0.50, -2.55, 1.00, 0.20, r=0.05)

        # 6. Рубка: передняя грань чуть впереди оси, тело уходит назад
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

        # 7. Амбразура: орудие смотрит из передней грани, а не стоит на круглой основе
        pen.poly(case_dark, [(-0.70, front), (0.70, front), (0.50, front + 0.55), (-0.50, front + 0.55)],
                 outline=None)

        # 8. Детали крыши рубки (позади орудия, чтобы не пересекаться с казёнником)
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

        self._draw_exhaust(pen, look.speed)
        return pygame.transform.smoothscale(big, (size, size))

    # ==========================================
    # ЛАФЕТ ОРУДИЯ
    # ==========================================
    def _build_turret(self, team_color, paint, look, emblem, spec):
        """Лафет вращается вокруг оси орудия: прямоугольный блок цапф, трапециевидная маска спереди,
        казённик сзади. Никаких кругов: орудие качается в амбразуре, а не на поворотном кольце."""
        ppm = self._ppm
        size = 2 * math.ceil(TD_TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)

        dark = _paint(TURRET_DARK, paint)
        main = _paint(TURRET_MAIN, paint)
        light = _paint(TURRET_LIGHT, paint)
        k = 1.0 + 0.12 * look.front                     # накладная броня расширяет маску
        front = spec.GUN_FRONT_M

        # казённик (сзади оси)
        pen.rect(dark, -0.30, 0.14, 0.60, 0.80, r=0.08)
        pen.rect(main, -0.20, 0.30, 0.40, 0.14, outline=None)
        pen.rect(light, -0.14, 0.58, 0.28, 0.10, outline=None)
        # блок цапф (прямоугольный)
        pen.rect(main, -0.66 * k, -0.28, 1.32 * k, 0.44, r=0.06)
        pen.rect(light, -0.40 * k, -0.20, 0.80 * k, 0.12, outline=None)
        # маска: трапеция, сужается к дульному срезу
        pen.poly(team_color, [(-0.40 * k, -front), (0.40 * k, -front),
                              (0.62 * k, -0.25), (-0.62 * k, -0.25)])
        return pygame.transform.smoothscale(big, (size, size))


OUTLINE_ANT = (38, 33, 28)