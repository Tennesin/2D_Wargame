"""vehicles/spg/sprites.py — отрисовка САУ: моторная крышка спереди, открытое боевое отделение с ящиками
боекомплекта сзади, щит орудия цвета архетипа, толстый ствол и кормовой сошник.
Наследует TDRenderer: слой маски (_draw_front_layer), кэши и общий порядок слоёв те же."""
import math
import pygame

from engine import shade_color
from vehicles.render.pen import (
    Pen as _Pen, apply_paint as _paint, SS, OUTLINE,
    HULL_MAIN, HULL_LIGHT, HULL_DARK, DECK, GRILL,
    TURRET_MAIN, TURRET_LIGHT, TURRET_DARK,
)
from vehicles.td.params import TD_TURRET_HALF_M
from vehicles.td.sprites import TDRenderer

CRATE = (132, 124, 106)         # ящики боекомплекта
CASE_FRONT_M = 0.45             # передняя стенка отделения впереди оси орудия
CASE_REACH_M = 1.65             # на сколько метров назад от оси уходит отделение (до масштаба CASE_K)
REAR_MARGIN_M = 0.45            # отделение не доходит до кормы корпуса: там плита и выхлоп
SHIELD_DEPTH_M = 1.0            # глубина щита орудия вдоль ствола (больше BARREL_HIDDEN_M + откат)
BARREL_THICK_K = 1.3            # САУ рисуется с более толстым стволом, чем остальная техника
SPADE_DEPTH_M = (0.30, 0.55)    # вынос сошника за корму для уровней опоры 1 и 2
SPADE_HALF_W_M = 0.95

class SPGRenderer(TDRenderer):

    # ==========================================
    # СТВОЛ
    # ==========================================

    def _build_barrel(self, bl, bt, look):
        """Тот же ствол, но толще: ключ кэша остаётся прежним (bl, bt), меняется только рисунок."""
        return super()._build_barrel(bl, max(bt, round(bt * BARREL_THICK_K)), look)

    # ==========================================
    # КОРПУС
    # ==========================================

    def _build_hull(self, paint, look, spec):
        ppm = self._ppm
        layout = spec.layout
        size = 2 * math.ceil(self.HULL_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        mount = layout.axis_fwd_m
        axis = -mount                                   # ось орудия в координатах корпуса (перёд = -y)
        pen = _Pen(big, ppm * SS, 0.0, mount)           # центр спрайта = ось орудия
        g = spec.CASE_K

        hull_main = _paint(HULL_MAIN, paint)
        hull_light = _paint(HULL_LIGHT, paint)
        hull_dark = _paint(HULL_DARK, paint)
        deck = _paint(DECK, paint)
        case_main = _paint(TURRET_MAIN, paint)
        case_light = _paint(TURRET_LIGHT, paint)
        case_dark = _paint(TURRET_DARK, paint)
        crate = _paint(CRATE, paint)

        # --- геометрия боевого отделения ---
        tail = max(y for _, y in layout.outline)        # корма корпуса
        front = axis - CASE_FRONT_M
        rear = min(axis + CASE_REACH_M * g, tail - REAR_MARGIN_M)
        rear = max(rear, front + 1.6)
        wf = 0.80 + 0.30 * g                            # полуширина спереди
        wr = wf + 0.18                                  # и сзади (отделение расширяется к корме)

        # --- сошник за кормой (рисуем первым: корпус перекроет его начало) ---
        depth = SPADE_DEPTH_M[0] if spec.SUPPORT <= 1 else SPADE_DEPTH_M[1]
        sw = SPADE_HALF_W_M
        pen.poly(hull_dark, [(-sw, tail - 0.05), (sw, tail - 0.05),
                             (sw - 0.15, tail + depth), (-(sw - 0.15), tail + depth)])
        if spec.SUPPORT >= 2:                           # большой сошник: две гидроопоры
            for sx in (-1, 1):
                pen.line(GRILL, sx * 0.62, tail - 0.10, sx * 0.48, tail + depth * 0.8, 0.12)

        # --- корпус, подкрылки, экраны ---
        pen.poly(hull_main, layout.outline)
        for fx, fy, fw, fh in layout.fender_rects:
            pen.rect(hull_dark, fx, fy, fw, fh)
        self._draw_skirts(pen, look.side + layout.base_skirt, paint, layout)

        pen.poly(hull_light, layout.front_plate)
        pen.rect(deck, *layout.deck_rect)
        self._draw_seams(pen, layout, hull_dark)
        self._draw_front_kit(pen, look.front, paint, layout)

        # --- моторная крышка между носом и боевым отделением ---
        self._draw_deck(pen, front, hull_dark, layout.deck_rect[1], lead=0.45)

        # --- кормовая плита (под отделением и выхлопом) ---
        pen.rect(hull_dark, *layout.rear_plate)

        # --- открытое боевое отделение: светлые кромки стенок и тёмный пол ---
        outer = [(-wf, front), (wf, front), (wr, front + 0.45), (wr, rear - 0.25),
                 (wr - 0.30, rear), (-(wr - 0.30), rear), (-wr, rear - 0.25), (-wr, front + 0.45)]
        pen.poly(case_light, outer)
        inset = 0.24
        inner = [(-wf + inset, front + inset), (wf - inset, front + inset),
                 (wr - inset, front + 0.45 + inset * 0.4), (wr - inset, rear - 0.25 - inset * 0.4),
                 (wr - 0.30 - inset, rear - inset), (-(wr - 0.30 - inset), rear - inset),
                 (-(wr - inset), rear - 0.25 - inset * 0.4), (-(wr - inset), front + 0.45 + inset * 0.4)]
        pen.poly(case_dark, inner, outline=case_main)

        cy0 = rear - inset - 0.55                       # ящики боекомплекта у задней стенки
        for cx in (-0.62, 0.02):
            pen.rect(crate, cx, cy0, 0.58, 0.45, r=0.04)

        if look.speed > 0:                              # антенна
            pen.line(OUTLINE, -wr + 0.12, rear - 0.9, -wr + 0.05, rear - 0.2, 0.04)
            pen.ellipse(case_dark, -wr + 0.12, rear - 0.9, 0.08, 0.08)

        self._draw_exhaust(pen, look.speed, layout)
        return self._finish(pygame.transform.smoothscale(big, (size, size)))

    # ==========================================
    # ЩИТ ОРУДИЯ
    # ==========================================

    def _build_mantlet(self, team_color, paint, look, spec):
        """Щит орудия цвета архетипа: шире и глубже, чем у ПТ-САУ, с тёмной планкой на передней кромке."""
        ppm = self._ppm
        size = 2 * math.ceil(TD_TURRET_HALF_M * ppm)
        big = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
        pen = _Pen(big, ppm * SS)

        g = spec.CASE_K
        k = 1.0 + 0.12 * look.front
        front = spec.GUN_FRONT_M                        # передняя кромка, м вперёд от оси
        back = front - SHIELD_DEPTH_M                   # задняя кромка (за осью)
        wf = (0.55 * g + 0.10) * k
        wb = wf + 0.24 * g
        dark = shade_color(team_color, 0.65)

        pen.poly(team_color, [(-(wf - 0.12), -front), (wf - 0.12, -front), (wf, -front + 0.12),
                              (wb, -back), (-wb, -back), (-wf, -front + 0.12)])
        pen.rect(dark, -(wf - 0.12), -front, 2.0 * (wf - 0.12), 0.14, outline=None)   # планка у ствола

        return self._finish(pygame.transform.smoothscale(big, (size, size)), (41, 67))