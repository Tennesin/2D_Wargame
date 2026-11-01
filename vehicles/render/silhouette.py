"""vehicles/render/silhouette.py — прозрачный силуэт техники для панели танка: спрайты рендерера
собираются без поворота, обрезаются по рамке, вписываются в квадрат, окрашиваются в светлый
голубовато-серый тон, делаются полупрозрачными и обводятся контуром."""
from dataclasses import dataclass

import pygame

BUILD_PPM = 20.0                  # масштаб, в котором строятся спрайты (px на метр)
FIT_MAX_K = 1.5                   # сильнее увеличивать силуэт не нужно
FIT_SHRINK = 0.70                 # силуэт занимает эту долю области: запас по краям, чтобы влезал ствол
FILL_TINT = (150, 175, 200)       # умножение цвета: уводит палитру корпуса в холодный серый
FILL_LIFT = (40, 50, 60)          # затем осветляем
FILL_ALPHA = 125                  # общая прозрачность заливки (0..255)
OUTLINE_COLOR = (200, 225, 245, 210)

@dataclass(frozen=True)
class Silhouette:
    surface: pygame.Surface       # готовый прозрачный силуэт
    axis: tuple                   # ось орудия (башни) на поверхности, px
    px_per_m: float               # пикселей силуэта на метр корпуса
    axis_fwd_m: float             # ось впереди центра корпуса, м

    def hull_point(self, u, v):
        """Точка корпуса (метры корпуса: u вправо, v назад, центр корпуса = (0, 0)) -> px на surface.
        Нужна, чтобы рисовать модули (гусеницы) поверх силуэта."""
        return (self.axis[0] + u * self.px_per_m,
                self.axis[1] + (v + self.axis_fwd_m) * self.px_per_m)

def build_silhouette(renderer, vehicle, box):
    """renderer: ОТДЕЛЬНЫЙ экземпляр рендерера этой техники (его масштаб меняется и кэши сбрасываются).
    box: (ширина, высота) области, в которую вписывается силуэт."""
    renderer.set_zoom(BUILD_PPM)
    sprite = renderer.panel_sprite(vehicle)
    cx, cy = sprite.get_width() / 2.0, sprite.get_height() / 2.0       # ось орудия на холсте

    bb = sprite.get_bounding_rect()
    k = min(box[0] / bb.w, box[1] / bb.h, FIT_MAX_K) * FIT_SHRINK
    size = (max(1, round(bb.w * k)), max(1, round(bb.h * k)))
    surf = pygame.transform.smoothscale(sprite.subsurface(bb).copy(), size)
    axis = ((cx - bb.x) * k, (cy - bb.y) * k)

    outline = pygame.mask.from_surface(surf).outline()                 # контур считаем до прозрачности
    surf.fill(FILL_TINT, special_flags=pygame.BLEND_RGB_MULT)
    surf.fill(FILL_LIFT, special_flags=pygame.BLEND_RGB_ADD)
    surf.fill((255, 255, 255, FILL_ALPHA), special_flags=pygame.BLEND_RGBA_MULT)   # альфа каждого пикселя * FILL_ALPHA
    if len(outline) > 2:
        pygame.draw.lines(surf, OUTLINE_COLOR, True, outline, 1)

    spec = vehicle.spec
    return Silhouette(surf, axis, BUILD_PPM * spec.HULL_SCALE * k, spec.layout.axis_fwd_m)