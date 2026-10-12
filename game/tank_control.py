"""game/tank_control.py — танк игрока: команда из ввода и обновление."""
from .modes import Mode

class TankController:
    def __init__(self, ctx, input_handler, modes):
        self.ctx = ctx
        self.tank = ctx.fleet.player
        self.input = input_handler
        self.camera = ctx.camera
        self.modes = modes

    def update(self, dt):
        modes = self.modes
        command = self.input.read_command(self.camera,
                                          active=modes.mode != Mode.BUILD,
                                          follow_mouse=modes.turret_follow,
                                          combat=modes.combat)
        self.ctx.step_vehicle(self.tank, command, dt)