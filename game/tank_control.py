"""game/tank_control.py — танк игрока: команда из ввода, обновление, ползунки конструктора."""
from vehicles import TankSpec
from .modes import Mode
from .panels import PanelMode

class TankController:
    def __init__(self, tank, input_handler, camera, modes, walls, terrain, effects, ui):
        self.tank = tank
        self.input = input_handler
        self.camera = camera
        self.modes = modes
        self.walls = walls
        self.terrain = terrain
        self.effects = effects
        self.ui = ui

        ui.set_on_change(PanelMode.TANK, self.on_constructor_change)
        self.show_stats()

    # ---------- конструктор ----------
    def on_constructor_change(self, values):
        """Ползунок сдвинут: пересчитываем танк (доля HP сохраняется внутри set_spec) и обновляем панель."""
        self.tank.set_spec(TankSpec.from_values(values))
        self.show_stats()

    def show_stats(self):
        spec = self.tank.spec
        for name, text in {**spec.main_stats(), **spec.internal_stats()}.items():
            self.ui.set_stat(name, text)

    # ---------- каждый кадр ----------
    def update(self, dt):
        modes = self.modes
        command = self.input.read_command(self.camera,
                                          active=modes.mode != Mode.BUILD,
                                          follow_mouse=modes.turret_follow,
                                          combat=modes.combat)
        tank = self.tank
        near_walls = self.walls.obbs_near(tank.x, tank.y, tank.reach_px())
        shot = tank.update(command, dt, near_walls, self.terrain)
        if shot is not None:
            self.effects.spawn_shot(shot, tank.spec, tank)