"""game/match/control/bots.py — кадр ботов: команда от мозга, физика танка, выстрел."""
from ai import PlanBudget, TerrainNavCache, BotContext, HazardBoard

PLANS_PER_FRAME = 1          # сколько путей A* можно построить за кадр на всех ботов

class BotController:
    def __init__(self, game_ctx):
        self.game_ctx = game_ctx
        self.fleet = game_ctx.fleet
        self.budget = PlanBudget(PLANS_PER_FRAME)
        self.nav = TerrainNavCache(game_ctx.terrain)
        self.hazards = HazardBoard(game_ctx.effects, game_ctx.settings, game_ctx.fleet)
        self.ctx = BotContext(game_ctx.targets, game_ctx.terrain, game_ctx.walls,
                              game_ctx.fleet, self.budget, self.nav,
                              self.hazards, game_ctx.settings)
        self._rr = 0

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
            if tank.tracks.broken and tank.tracks.repair_side is None:
                tank.start_repair()
            command = bot.brain.think(dt, tank, player, self.ctx)
            self.game_ctx.step_vehicle(tank, command, dt)