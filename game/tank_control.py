"""game/tank_control.py — танк игрока: команда из ввода и обновление."""
from .modes import Mode

class TankController:
    def __init__(self, tank, input_handler, camera, modes, walls, terrain, effects):
        self.tank = tank
        self.input = input_handler
        self.camera = camera
        self.modes = modes
        self.walls = walls
        self.terrain = terrain
        self.effects = effects

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