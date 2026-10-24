"""game/match/control/player.py — танк игрока: команда из ввода и обновление."""
from inputs import Action, AMMO_HOTKEYS
from ..modes import Mode

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
        shot = self.ctx.step_vehicle(self.tank, command, dt)
        if shot is not None:
            self.ctx.match_stats.on_shot(shot.ammo.kind)

    def handle_hotkeys(self):
        for action, kind in zip(AMMO_HOTKEYS, self.tank.spec.ammo_kinds):
            if self.input.was_pressed(action):
                self.tank.select_ammo(kind)
        if self.input.was_pressed(Action.REPAIR):
            self.tank.start_repair()        # чинит первую сбитую; если ремонт уже идёт, ничего не делает