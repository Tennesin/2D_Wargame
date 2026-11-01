"""game/match/control/player.py — танк игрока: команда из ввода и обновление."""
from math import hypot
from inputs import Action, AMMO_HOTKEYS

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
                                          follow_mouse=modes.turret_follow,
                                          combat=modes.combat)
        x0, y0 = self.tank.x, self.tank.y
        shot = self.ctx.step_vehicle(self.tank, command, dt)
        self.ctx.match_stats.on_move(hypot(self.tank.x - x0, self.tank.y - y0))
        if shot is not None:
            self.ctx.match_stats.on_shot(shot.ammo.kind)

    def handle_hotkeys(self):
        for action, kind in zip(AMMO_HOTKEYS, self.tank.spec.ammo_kinds):
            if self.input.was_pressed(action):
                self.tank.select_ammo(kind)
        if self.input.was_pressed(Action.REPAIR):
            self.tank.start_repair()        # чинит первую сбитую; если ремонт уже идёт, ничего не делает