"""vehicles/render/silhouette.py — прозрачный силуэт техники для панели танка: спрайты рендерера
собираются без поворота, обрезаются по рамке, вписываются в область, окрашиваются в светлый
голубовато-серый тон, делаются полупрозрачными и обводятся контуром."""
from dataclasses import dataclass
import pygame

BUILD_PPM = 20.0                  # масштаб, в котором строятся спрайты (px на метр)
FIT_MAX_K = 1.5                   # сильнее увеличивать силуэт не нужно
EDGE_PAD = 2                      # прозрачная рамка вокруг силуэта: контур не упирается в край картинки
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
    box: (ширина, высота) области, в которую вписывается силуэт вместе с запасом EDGE_PAD."""
    renderer.set_zoom(BUILD_PPM)
    sprite = renderer.panel_sprite(vehicle)
    cx, cy = sprite.get_width() / 2.0, sprite.get_height() / 2.0       # ось орудия на холсте

    bb = sprite.get_bounding_rect()
    avail_w, avail_h = box[0] - 2 * EDGE_PAD, box[1] - 2 * EDGE_PAD
    k = min(avail_w / bb.w, avail_h / bb.h, FIT_MAX_K)
    size = (max(1, round(bb.w * k)), max(1, round(bb.h * k)))
    body = pygame.transform.smoothscale(sprite.subsurface(bb).copy(), size)

    mask = pygame.mask.from_surface(body)                              # контур считаем до прозрачности
    outlines = [c.outline() for c in mask.connected_components()]
    body.fill(FILL_TINT, special_flags=pygame.BLEND_RGB_MULT)
    body.fill(FILL_LIFT, special_flags=pygame.BLEND_RGB_ADD)
    body.fill((255, 255, 255, FILL_ALPHA), special_flags=pygame.BLEND_RGBA_MULT)

    surf = pygame.Surface((size[0] + 2 * EDGE_PAD, size[1] + 2 * EDGE_PAD), pygame.SRCALPHA)
    surf.blit(body, (EDGE_PAD, EDGE_PAD))
    for pts in outlines:
        if len(pts) > 2:
            pygame.draw.lines(surf, OUTLINE_COLOR, True,
                              [(x + EDGE_PAD, y + EDGE_PAD) for x, y in pts], 1)

    axis = ((cx - bb.x) * k + EDGE_PAD, (cy - bb.y) * k + EDGE_PAD)
    spec = vehicle.spec
    return Silhouette(surf, axis, BUILD_PPM * spec.HULL_SCALE * k, spec.layout.axis_fwd_m)