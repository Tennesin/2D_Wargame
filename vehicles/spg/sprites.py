"""vehicles/spg/sprites.py — отрисовка САУ."""
import math
import pygame

from engine import shade_color
from vehicles.render.pen import (
    Pen as _Pen, apply_paint as _paint, SS,
    HULL_DARK, GRILL, TURRET_MAIN, TURRET_LIGHT, TURRET_DARK,
)
from vehicles.td.params import TD_TURRET_HALF_M
from vehicles.td.sprites import TDRenderer
from .case import spg_case_box, CASE_INSET_M

SHIELD_DEPTH_M = 1.0            # глубина щита орудия вдоль ствола (больше BARREL_HIDDEN_M + откат)
BARREL_THICK_K = 1.3            # САУ рисуется с более толстым стволом, чем остальная техника
SPADE_DEPTH_M = (0.30, 0.55)    # вынос сошника за корму для уровней опоры 1 и 2
SPADE_HALF_W_M = 0.95

class SPGRenderer(TDRenderer):
    DESIGN_KIND = "spg"

    # ==========================================
    # СТВОЛ
    # ==========================================

    def _build_barrel(self, bl, bt, look):
        """Тот же ствол, но толще: ключ кэша остаётся прежним (bl, bt), меняется только рисунок."""
        return super()._build_barrel(bl, max(bt, round(bt * BARREL_THICK_K)), look)

    # ==========================================
    # КОРПУС (общий шаблон в TDRenderer._build_hull)
    # ==========================================

    def _draw_hull_back(self, pen, paint, look, spec):
        """Сошник за кормой: рисуем первым, корпус перекроет его начало."""
        layout = spec.layout
        hull_dark = _paint(HULL_DARK, paint)
        tail = max(y for _, y in layout.outline)         # корма корпуса
        depth = SPADE_DEPTH_M[0] if spec.SUPPORT <= 1 else SPADE_DEPTH_M[1]
        sw = SPADE_HALF_W_M
        pen.poly(hull_dark, [(-sw, tail - 0.05), (sw, tail - 0.05),
                             (sw - 0.15, tail + depth), (-(sw - 0.15), tail + depth)])
        if spec.SUPPORT >= 2:                            # большой сошник: две гидроопоры
            for sx in (-1, 1):
                pen.line(GRILL, sx * 0.62, tail - 0.10, sx * 0.48, tail + depth * 0.8, 0.12)

    def _draw_superstructure(self, pen, paint, look, spec):
        """САУ: открытое боевое отделение (структура)."""
        axis, front, rear, wf, wr = spg_case_box(spec)
        case_main = _paint(TURRET_MAIN, paint)
        case_light = _paint(TURRET_LIGHT, paint)
        case_dark = _paint(TURRET_DARK, paint)

        # открытое боевое отделение: светлые кромки стенок и тёмный пол
        outer = [(-wf, front), (wf, front), (wr, front + 0.45), (wr, rear - 0.25),
                 (wr - 0.30, rear), (-(wr - 0.30), rear), (-wr, rear - 0.25), (-wr, front + 0.45)]
        pen.poly(case_light, outer)
        inset = CASE_INSET_M
        inner = [(-wf + inset, front + inset), (wf - inset, front + inset),
                 (wr - inset, front + 0.45 + inset * 0.4), (wr - inset, rear - 0.25 - inset * 0.4),
                 (wr - 0.30 - inset, rear - inset), (-(wr - 0.30 - inset), rear - inset),
                 (-(wr - inset), rear - 0.25 - inset * 0.4), (-(wr - inset), front + 0.45 + inset * 0.4)]
        pen.poly(case_dark, inner, outline=case_main)

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