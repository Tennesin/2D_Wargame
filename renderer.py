"""renderer.py — порядок слоёв: земля, местность, эффекты, стены, танк, прицел, отладка."""
import pygame

from engine import PX_PER_M
from world import GroundRenderer, TerrainRenderer
from vehicles import TankRenderer
from structures import WallRenderer
from combat import AimRenderer

class Renderer:
    def __init__(self, world_generator, terrain=None):
        self.font = pygame.font.Font(None, 22)

        self._zoom = None                   # зум, под который сейчас построены кэши
        self._ppm = 0.0                     # пикселей экрана на метр эталонного спрайта (= PX_PER_M * zoom)

        self.ground_renderer = GroundRenderer(world_generator)
        self.tank_renderer = TankRenderer()
        self.wall_renderer = WallRenderer()
        self.aim_renderer = AimRenderer()

        self.terrain = terrain
        self.terrain_renderer = TerrainRenderer()

    # ==========================================
    # ГЛАВНЫЙ МЕТОД
    # ==========================================
    def draw(self, screen, camera, tank, debug_lines=None, effects=None, walls=None,
             build_preview=None, aim=None):
        self._sync_zoom(camera.zoom)
        self.ground_renderer.draw(screen, camera)
        if self.terrain is not None:
            self.terrain_renderer.draw(screen, camera, self.terrain)
        if effects is not None:
            effects.draw_ground(screen, camera)      # пятна от взрывов лежат под танком и стенами
        if walls is not None:
            self.wall_renderer.draw_all(screen, camera, walls)
        self.tank_renderer.draw(screen, camera, tank)
        if build_preview is not None:                # призрак стены поверх танка, чтобы красное было видно
            self.wall_renderer.draw_preview(screen, camera, *build_preview)
        if aim is not None:                          # линия выстрела под снарядами и вспышкой
            self.aim_renderer.draw(screen, camera, aim)
        if effects is not None:
            effects.draw(screen, camera)
        if debug_lines:
            self._draw_debug(screen, debug_lines)

    def _sync_zoom(self, zoom):
        """При смене зума сбрасываем всё, что зависит от масштаба (базовые чанки земли остаются)."""
        if zoom == self._zoom:
            return
        self._zoom = zoom
        self._ppm = PX_PER_M * zoom
        self.ground_renderer.set_zoom()
        self.tank_renderer.set_zoom(self._ppm)

    # ==========================================
    # ОТЛАДКА
    # ==========================================
    def _draw_debug(self, screen, lines):
        y = 52
        for text in lines:
            shadow = self.font.render(text, True, (0, 0, 0))
            label = self.font.render(text, True, (255, 255, 255))
            screen.blit(shadow, (11, y + 1))
            screen.blit(label, (10, y))
            y += 20