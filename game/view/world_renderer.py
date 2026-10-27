"""game/view/world_renderer.py — порядок слоёв: земля, местность, эффекты, стены, танки, прицел."""
from engine import PX_PER_M
from world import GroundRenderer, TerrainRenderer, WorldBoundsRenderer
from vehicles import RENDERERS
from structures import WallRenderer
from combat import AimRenderer

class Renderer:
    def __init__(self, world_generator, ctx):
        self.terrain = ctx.terrain
        self.fleet = ctx.fleet
        self.walls = ctx.walls
        self.effects = ctx.effects

        self._zoom = None                   # зум, под который сейчас построены кэши
        self._ppm = 0.0                     # пикселей экрана на метр эталонного спрайта (= PX_PER_M * zoom)

        self.ground_renderer = GroundRenderer(world_generator)
        self.bounds_renderer = WorldBoundsRenderer()
        self.terrain_renderer = TerrainRenderer()
        self.vehicle_renderers = {key: cls() for key, cls in RENDERERS.items()}
        self.wall_renderer = WallRenderer()
        self.aim_renderer = AimRenderer()

    def draw(self, screen, camera, build_preview=None, aim=None):
        self._sync_zoom(camera)
        self.ground_renderer.draw(screen, camera)
        self.terrain_renderer.draw(screen, camera, self.terrain)
        self.effects.draw_ground(screen, camera)         # пятна от взрывов лежат под танками и стенами
        self.wall_renderer.draw_all(screen, camera, self.walls)
        for vehicle in self.fleet.vehicles:
            if vehicle.alive and self._on_screen(screen, camera, vehicle):
                self.vehicle_renderers[vehicle.renderer_key].draw(screen, camera, vehicle)
        if build_preview is not None:                    # призрак стены поверх танков, чтобы красное было видно
            self.wall_renderer.draw_preview(screen, camera, *build_preview)
        if aim is not None:                              # линия выстрела под снарядами и вспышкой
            self.aim_renderer.draw(screen, camera, aim)
        self.effects.draw(screen, camera)
        self.bounds_renderer.draw(screen, camera)        # темнота за краем мира накрывает всё, что туда залетело

    @staticmethod
    def _on_screen(screen, camera, tank):
        """Попадает ли танк (с запасом на ствол) в окно."""
        sx, sy = camera.world_to_screen(tank.x, tank.y)
        r = tank.reach_px() * camera.zoom
        return -r <= sx <= screen.get_width() + r and -r <= sy <= screen.get_height() + r

    def _sync_zoom(self, camera):
        """При смене зума сбрасываем всё, что зависит от масштаба."""
        zoom = camera.zoom
        if zoom == self._zoom:
            return
        self._zoom = zoom
        self._ppm = PX_PER_M * zoom
        self.ground_renderer.set_zoom()
        moving = camera.is_zooming
        for renderer in self.vehicle_renderers.values():
            renderer.set_view_zoom(self._ppm, moving)

    def preload_iter(self, camera):
        """Земля (70% работы) и вода (30%) по кусочкам: доля готовности 0..1."""
        size = (camera.view_w, camera.view_h)
        for part in self.ground_renderer.preload_iter(camera, size):
            yield part * 0.7
        for part in self.terrain_renderer.preload_iter(camera, size, self.terrain):
            yield 0.7 + part * 0.3

    def preload(self, camera):
        """Заранее строит землю и воду вокруг стартовой точки, чтобы на экране не было подгрузки."""
        for _ in self.preload_iter(camera):
            pass