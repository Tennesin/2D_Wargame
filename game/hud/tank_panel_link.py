"""game/hud/tank_panel_link.py — связка панели танка с игрой: состояние гусениц, режим стрельбы, снаряд,
оглушение и местность превращаются в простые данные для виджета. Сам виджет про танки не знает."""
from ui import (ModuleView, MODULE_OK, MODULE_BROKEN, MODULE_REPAIR,
                TERRAIN_PLAIN, TERRAIN_WATER, TERRAIN_MUD)
from vehicles import TRACK_SIDES
from world import SHALLOWS, MID_WATER, MUD

# вид местности из физики -> значение для виджета (всё остальное: обычная местность)
_TERRAIN_OF = {SHALLOWS: TERRAIN_WATER, MID_WATER: TERRAIN_WATER, MUD: TERRAIN_MUD}

class TankPanelLink:
    def __init__(self, panel, tank, modes):
        self.panel = panel
        self.tank = tank
        self.modes = modes
        self._rects = tuple(tank.spec.layout.track_rects)     # (левая, правая) в метрах корпуса
        self.update()

    def update(self):
        """Каждый кадр после Match.update."""
        tank = self.tank
        tracks = tank.tracks
        views = []
        for side, rect in zip(TRACK_SIDES, self._rects):
            if tracks.repair_side == side:                    # проверяем первым: у чинимой гусеницы health ещё 0
                total = tracks.repair_total
                progress = 1.0 - tracks.repair_left / total if total > 0.0 else 0.0
                views.append(ModuleView(rect, MODULE_REPAIR, progress))
            elif tracks.is_broken(side):
                views.append(ModuleView(rect, MODULE_BROKEN))
            else:
                views.append(ModuleView(rect, MODULE_OK))
        self.panel.set_modules(views)
        self.panel.set_weapon(tank.ammo, self.modes.combat)
        self.panel.set_stun(tank.stun_left)
        self.panel.set_terrain(_TERRAIN_OF.get(tank.terrain_kind, TERRAIN_PLAIN), tank.terrain_k)