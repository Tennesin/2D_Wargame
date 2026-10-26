"""game/hud/inspector.py — «Краткая сводка»: что под курсором. Данные о цели она берёт у самой цели.
Окно появляется при простой наводке мыши (без кликов)."""
from engine import obb_distance_to_point
from ui import InfoCard
from world import ROCK

class HoverInspector:
    def __init__(self, ctx, input_handler, modes):
        self.input = input_handler
        self.camera = ctx.camera
        self.modes = modes
        self.fleet = ctx.fleet
        self.walls = ctx.walls
        self.terrain = ctx.terrain
        self.card = InfoCard()

    def _target(self):
        """Танк, стена, камень или None. Сводка скрыта, если игрок мёртв, включён боевой режим
        (или стройка), либо курсор сейчас занят интерфейсом / вращением стены / перетаскиванием камеры."""
        if not self.fleet.player.alive:
            return None
        if self.modes.combat:
            return None
        if not self.input.pointer_in_world:
            return None

        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)

        # порядок как при рисовании: сверху танки (игрок самый верхний), потом стены, потом камни
        for tank in reversed(self.fleet.vehicles):
            if tank.alive and obb_distance_to_point(tank.hull_obb(), wx, wy) == 0.0:
                return tank
        wall = self.walls.pick(wx, wy)
        if wall is not None:
            return wall
        for patch in self.terrain.patches_near(wx, wy, 0.0):
            if patch.kind is ROCK and patch.contains(wx, wy):
                return patch
        return None                                    # вода и грязь не «объекты»: сводки нет

    def draw(self, screen):
        target = self._target()
        if target is None:
            return
        title, rows = target.describe()
        self.card.draw(screen, self.input.mouse_pos, title, rows)