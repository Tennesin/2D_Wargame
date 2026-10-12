"""game/bot_control.py — кадр ботов: команда от мозга, физика танка, выстрел."""
from collections import namedtuple

from ai import PlanBudget, TerrainNavCache

PLANS_PER_FRAME = 1          # сколько путей A* можно построить за кадр на всех ботов

BotContext = namedtuple("BotContext", "targets terrain walls fleet budget nav")

class BotController:
    def __init__(self, fleet, walls, terrain, effects, targets):
        self.fleet = fleet
        self.walls = walls
        self.terrain = terrain
        self.effects = effects
        self.budget = PlanBudget(PLANS_PER_FRAME)
        self.nav = TerrainNavCache(terrain)
        self.ctx = BotContext(targets, terrain, walls, fleet, self.budget, self.nav)
        self._rr = 0                                  # сдвиг очереди, чтобы бот в начале списка не был «любимчиком»

    def update(self, dt):
        self.budget.new_frame()
        player = self.fleet.player
        bots = list(self.fleet.bots)
        if bots:
            self._rr = (self._rr + 1) % len(bots)
            bots = bots[self._rr:] + bots[:self._rr]
        for bot in bots:
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