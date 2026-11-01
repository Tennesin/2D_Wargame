"""game/hud/tank_panel_link.py — связка панели танка с игрой: состояние гусениц, режим стрельбы и снаряд
превращаются в простые данные для виджета. Сам виджет про танки не знает."""
from ui import ModuleView, MODULE_OK, MODULE_BROKEN, MODULE_REPAIR
from vehicles import TRACK_SIDES

class TankPanelLink:
    def __init__(self, panel, tank, modes):
        self.panel = panel
        self.tank = tank
        self.modes = modes
        self._rects = tuple(tank.spec.layout.track_rects)     # (левая, правая) в метрах корпуса
        self.update()

    def update(self):
        """Каждый кадр после Match.update."""
        tracks = self.tank.tracks
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
        self.panel.set_weapon(self.tank.ammo, self.modes.combat)