"""game/renderer.py — порядок слоёв: земля, местность, эффекты, стены, танк, прицел."""
from engine import PX_PER_M
from world import GroundRenderer, TerrainRenderer, WorldBoundsRenderer
from vehicles import TankRenderer
from structures import WallRenderer
from combat import AimRenderer

class Renderer:
    def __init__(self, world_generator, terrain, tank, walls, effects):
        self.terrain = terrain
        self.tank = tank
        self.walls = walls
        self.effects = effects

        self._zoom = None                   # зум, под который сейчас построены кэши
        self._ppm = 0.0                     # пикселей экрана на метр эталонного спрайта (= PX_PER_M * zoom)

        self.ground_renderer = GroundRenderer(world_generator)
        self.bounds_renderer = WorldBoundsRenderer()
        self.terrain_renderer = TerrainRenderer()
        self.tank_renderer = TankRenderer()
        self.wall_renderer = WallRenderer()
        self.aim_renderer = AimRenderer()

    def draw(self, screen, camera, build_preview=None, aim=None):
        self._sync_zoom(camera.zoom)
        self.ground_renderer.draw(screen, camera)
        self.terrain_renderer.draw(screen, camera, self.terrain)
        self.effects.draw_ground(screen, camera)         # пятна от взрывов лежат под танком и стенами
        self.wall_renderer.draw_all(screen, camera, self.walls)
        self.tank_renderer.draw(screen, camera, self.tank)
        if build_preview is not None:                    # призрак стены поверх танка, чтобы красное было видно
            self.wall_renderer.draw_preview(screen, camera, *build_preview)
        if aim is not None:                              # линия выстрела под снарядами и вспышкой
            self.aim_renderer.draw(screen, camera, aim)
        self.effects.draw(screen, camera)
        self.bounds_renderer.draw(screen, camera)        # темнота за краем мира накрывает всё, что туда залетело

    def _sync_zoom(self, zoom):
        """При смене зума сбрасываем всё, что зависит от масштаба (базовые чанки земли остаются)."""
        if zoom == self._zoom:
            return
        self._zoom = zoom
        self._ppm = PX_PER_M * zoom
        self.ground_renderer.set_zoom()
        self.tank_renderer.set_zoom(self._ppm)