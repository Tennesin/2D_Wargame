"""game/editor/parts_overlay.py — подсказки поверх превью на вкладке «Детали»: зелёная область «сюда можно»,
рамки деталей, призрак новой детали и рукоятка выбранной."""
import math
from dataclasses import replace

import pygame

from engine import AlphaLayer
from vehicles.parts import PART_TYPES, PartCtx, fit_polygons, corners, center, extent_m
from vehicles.parts.frame import PartPen
from vehicles.render.pen import Pen
from . import gizmo

GOOD = (110, 220, 110)
SOFT = (150, 180, 220)
YELLOW = (255, 220, 80)
RED = (240, 80, 70)

class PartsOverlay:
    def __init__(self):
        self._alpha = AlphaLayer()

    def draw(self, screen, tool):
        if not tool.active or tool.vehicle is None:
            return
        fr = tool.frame()
        self._region(screen, tool, fr)
        self._outlines(screen, tool, fr)
        self._ghost(screen, tool, fr)
        self._gizmo(screen, tool)

    # ---------- допустимая область ----------
    def _region(self, screen, tool, fr):
        polys = [[fr.to_screen(u, v) for u, v in poly] for poly in fit_polygons(tool.spec, tool.surface)]
        pts = [p for poly in polys for p in poly]
        x0, y0 = math.floor(min(p[0] for p in pts)) - 2, math.floor(min(p[1] for p in pts)) - 2
        x1, y1 = math.ceil(max(p[0] for p in pts)) + 2, math.ceil(max(p[1] for p in pts)) + 2
        area = pygame.Rect(x0, y0, x1 - x0, y1 - y0).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        busy = tool.armed is not None or tool.drag_mode is not None
        fill = 70 if busy else (34 if tool.is_manual else 16)
        line = 170 if busy else 90
        layer = self._alpha.begin(area.size)
        for poly in polys:
            local = [(x - area.x, y - area.y) for x, y in poly]
            pygame.draw.polygon(layer, (*GOOD, fill), local)
            pygame.draw.polygon(layer, (*GOOD, line), local, 1)
        screen.blit(layer, area.topleft)

    # ---------- рамки деталей ----------
    def _outlines(self, screen, tool, fr):
        for i, p in tool.entries():
            pts = [fr.to_screen(u, v) for u, v in corners(p)]
            if i == tool.selected:
                color, width = YELLOW, 2
            elif not tool.is_fit(p):
                color, width = RED, 2                     # не помещается: не рисуется в игре, но данные целы
            else:
                color, width = SOFT, 1
            pygame.draw.polygon(screen, color, pts, width)

    # ---------- призрак ----------
    def _ghost(self, screen, tool, fr):
        g = tool.ghost()
        if g is None:
            return
        part, ok = g
        ptype = PART_TYPES[part.kind]
        p0 = replace(part, x=0.0, y=0.0)
        cu, cv = center(p0)                               # где центр габарита относительно начала детали
        side = int(2 * extent_m(part) * fr.k) + 14
        layer = pygame.Surface((side, side), pygame.SRCALPHA)
        pen = Pen(layer, fr.k, -cu, -cv)                  # центр габарита встаёт в центр слоя
        spec = tool.spec
        ctx = PartCtx(paint=None, look=spec.LOOK, layout=spec.layout, team=tool.vehicle.team_color)
        ptype.draw(PartPen(pen, p0), p0, ctx)
        if not ok:
            layer.fill((140, 0, 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        layer.set_alpha(170 if ok else 120)
        sx, sy = fr.to_screen(*center(part))
        screen.blit(layer, layer.get_rect(center=(round(sx), round(sy))))

    # ---------- рукоятка ----------
    def _gizmo(self, screen, tool):
        geom = tool.gizmo_geom()
        if geom is None:
            return
        hover = None
        if tool.drag_mode is None and tool.input.pointer_in_world:
            hover = gizmo.hit(*geom, tool.input.mouse_pos)
        gizmo.draw(screen, *geom, hover=hover, active=tool.drag_mode)