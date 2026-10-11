"""game/inspector.py — «Краткая сводка»: что под курсором и какие данные о нём показать.
Окно появляется при простой наводке мыши (без кликов)."""
from engine import fmt_num, heading_vector
from structures import Wall
from ui import InfoCard
from vehicles import Tank
from world import ROCK
from .modes import Mode

HIDE_IN_BUILD = True     # в режиме стройки сводку не показываем (мешает целиться призраком стены)

def _in_obb(obb, x, y):
    """Лежит ли точка (x, y) внутри повёрнутого прямоугольника (x, y, half_w, half_l, angle)."""
    cx, cy, hw, hl, angle = obb
    fx, fy = heading_vector(angle)
    dx, dy = x - cx, y - cy
    return abs(-dx * fy + dy * fx) <= hw and abs(dx * fx + dy * fy) <= hl

class HoverInspector:
    def __init__(self, input_handler, camera, modes, fleet, walls, terrain):
        self.input = input_handler
        self.camera = camera
        self.modes = modes
        self.fleet = fleet
        self.walls = walls
        self.terrain = terrain
        self.card = InfoCard()

    # ---------- что под курсором ----------
    def _target(self):
        """Танк, стена, камень или None. Сводка скрыта, если игрок мёртв, включён боевой режим
        (или стройка), либо курсор сейчас занят интерфейсом / вращением стены / перетаскиванием камеры."""
        if not self.fleet.player.alive:
            return None
        if self.modes.combat:
            return None
        if HIDE_IN_BUILD and self.modes.mode == Mode.BUILD:
            return None
        if not self.input.pointer_in_world:
            return None

        wx, wy = self.camera.screen_to_world(*self.input.mouse_pos)

        # порядок как при рисовании: сверху танки (игрок самый верхний), потом стены, потом камни
        for tank in reversed(self.fleet.tanks):
            if tank.alive and _in_obb(tank.hull_obb(), wx, wy):
                return tank
        wall = self.walls.pick(wx, wy)
        if wall is not None:
            return wall
        for patch in self.terrain.patches_near(wx, wy, 0.0):
            if patch.kind is ROCK and patch.contains(wx, wy):
                return patch
        return None                                    # вода и грязь не «объекты»: сводки нет

    # ---------- содержимое окна ----------
    def _archetype_name(self, tank):
        for bot in self.fleet.bots:
            if bot.tank is tank:
                return bot.brain.arch.name
        return "танк"

    def _describe(self, target):
        """(заголовок, [(название, значение), ...])."""
        if isinstance(target, Tank):
            s = target.spec
            title = "Ваш танк" if target.team == "player" else f"Враг: {self._archetype_name(target)}"
            return title, [
                ("Калибр", f"{s.cal:.0f} мм"),
                ("Броня: лоб", f"{s.front:.0f} мм"),
                ("Броня: борт", f"{s.side:.0f} мм"),
                ("Броня: корма", f"{s.rear:.0f} мм"),
                ("Масса", f"{fmt_num(s.mass, 1)} т"),
            ]
        if isinstance(target, Wall):
            t = target.thickness_m                     # у прямоугольной стены толщина одна на всю стену
            return "Стена", [
                ("Средняя толщина", f"{t:.2f} м"),
                ("Наименьшая толщина", f"{t:.2f} м"),
                ("Масса", f"{fmt_num(target.mass_t, 1)} т"),
            ]
        avg, low = target.thickness_stats()            # иначе это камень (Patch)
        return "Камень", [
            ("Средняя толщина", f"{avg:.2f} м"),
            ("Наименьшая толщина", f"{low:.2f} м"),
            ("Масса", f"{fmt_num(target.mass_t, 1)} т"),
        ]

    # ---------- кадр ----------
    def draw(self, screen):
        target = self._target()
        if target is None:
            return
        title, rows = self._describe(target)
        self.card.draw(screen, self.input.mouse_pos, title, rows)