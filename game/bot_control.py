"""game/bot_control.py — кадр ботов: команда от мозга, физика танка, выстрел."""
from collections import namedtuple

BotContext = namedtuple("BotContext", "targets terrain walls fleet")

class BotController:
    def __init__(self, fleet, walls, terrain, effects, targets):
        self.fleet = fleet
        self.walls = walls
        self.terrain = terrain
        self.effects = effects
        self.ctx = BotContext(targets, terrain, walls, fleet)

    def update(self, dt):
        player = self.fleet.player
        for bot in list(self.fleet.bots):
            tank = bot.tank
            if not tank.alive:
                continue
            command = bot.brain.think(dt, tank, player, self.ctx)
            reach = tank.reach_px()
            obstacles = self.walls.obbs_near(tank.x, tank.y, reach)
            obstacles += self.fleet.obbs_near(tank, reach)
            shot = tank.update(command, dt, obstacles, self.terrain)
            if shot is not None:
                self.effects.spawn_shot(shot, tank.spec, tank)