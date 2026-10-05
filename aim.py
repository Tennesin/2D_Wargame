"""aim.py — линия траектории выстрела и подпись пробития.
compute_aim считает, куда полетит снаряд (те же формулы, что у Shell), AimRenderer рисует."""
import math
from dataclasses import dataclass
from typing import Optional

import pygame

from ui import get_font, FONT_SIZE_LABEL

LINE_COLOR = (255, 40, 40, 110)      # красный, полупрозрачный
LINE_WIDTH = 2
LABEL_BG = (0, 0, 0, 175)
LABEL_PAD = 6
LABEL_OFFSET = 16

C_TEXT = (235, 235, 235)
C_YES = (90, 220, 90)
C_NO = (240, 80, 80)
C_CHANCE = (240, 210, 70)


@dataclass
class AimInfo:
    start: tuple                      # дульный срез (мировые px)
    end: tuple                        # точка попадания в стену или конец дальности
    wall: Optional[object] = None     # стена на пути (None, если линия свободна)
    armor: float = 0.0                # исходная броня, мм
    eff_armor: Optional[float] = None # приведённая броня, мм (None = рикошет)
    chance: float = 0.0               # шанс пробития 0..1


def compute_aim(tank, walls):
    """Траектория от дульного среза вдоль башни. Отрезок для проверки начинается в центре танка,
    как и у настоящего снаряда (Shell), поэтому результат совпадает с реальным выстрелом."""
    spec = tank.spec
    rad = math.radians(tank.turret_angle)
    dx, dy = math.sin(rad), -math.cos(rad)
    start = (tank.x + dx * spec.MUZZLE_DIST_PX, tank.y + dy * spec.MUZZLE_DIST_PX)
    end = (start[0] + dx * spec.SHELL_RANGE_PX, start[1] + dy * spec.SHELL_RANGE_PX)

    hit = walls.raycast(tank.x, tank.y, end[0], end[1])
    if hit is None:
        return AimInfo(start, end)

    wall, t, normal = hit
    point = (tank.x + (end[0] - tank.x) * t, tank.y + (end[1] - tank.y) * t)
    cos_impact = 1.0 if normal is None else abs(dx * normal[0] + dy * normal[1])
    eff, chance = wall.pierce_check(spec.penetration, cos_impact)
    return AimInfo(start, point, wall, wall.armor_mm, eff, chance)


class AimRenderer:
    def draw(self, screen, camera, info):
        a = camera.world_to_screen(*info.start)
        b = camera.world_to_screen(*info.end)
        self._draw_line(screen, a, b, marker=info.wall is not None)
        if info.wall is not None:
            self._draw_label(screen, b, info)

    @staticmethod
    def _draw_line(screen, a, b, marker):
        x0, y0 = int(min(a[0], b[0])) - 8, int(min(a[1], b[1])) - 8
        x1, y1 = int(max(a[0], b[0])) + 8, int(max(a[1], b[1])) + 8
        area = pygame.Rect(x0, y0, x1 - x0, y1 - y0).clip(screen.get_rect())
        if area.w <= 0 or area.h <= 0:
            return
        layer = pygame.Surface(area.size, pygame.SRCALPHA)
        pa = (a[0] - area.x, a[1] - area.y)
        pb = (b[0] - area.x, b[1] - area.y)
        pygame.draw.line(layer, LINE_COLOR, pa, pb, LINE_WIDTH)
        if marker:
            pygame.draw.circle(layer, LINE_COLOR, (round(pb[0]), round(pb[1])), 5)
        screen.blit(layer, area.topleft)

    @staticmethod
    def _draw_label(screen, point, info):
        if info.eff_armor is None:
            eff_text = "Приведённая броня: —"
            result, color = "Пробитие: Нет (рикошет)", C_NO
        else:
            eff_text = f"Приведённая броня: {info.eff_armor:.0f} мм"
            if info.chance >= 1.0:
                result, color = "Пробитие: Да", C_YES
            elif info.chance <= 0.0:
                result, color = "Пробитие: Нет", C_NO
            else:
                pct = max(1, min(99, round(info.chance * 100)))
                result, color = f"Пробитие: с шансом {pct}%", C_CHANCE

        rows = [(f"Исходная броня: {info.armor:.0f} мм", C_TEXT), (eff_text, C_TEXT), (result, color)]
        font = get_font(FONT_SIZE_LABEL)
        surfaces = [font.render(text, True, col) for text, col in rows]

        w = max(s.get_width() for s in surfaces) + 2 * LABEL_PAD
        h = sum(s.get_height() for s in surfaces) + 2 * LABEL_PAD
        rect = pygame.Rect(round(point[0]) + LABEL_OFFSET, round(point[1]) + LABEL_OFFSET, w, h)
        rect.clamp_ip(screen.get_rect())

        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(layer, LABEL_BG, layer.get_rect(), border_radius=5)
        y = LABEL_PAD
        for s in surfaces:
            layer.blit(s, (LABEL_PAD, y))
            y += s.get_height()
        screen.blit(layer, rect.topleft)