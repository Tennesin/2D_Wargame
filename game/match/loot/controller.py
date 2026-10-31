"""game/match/loot/controller.py — добыча в партии: появление обломков, таймеры, подбор игроком."""
import random

from ai import ARCHETYPES
from engine import obb_distance_to_point
from ...state.stats import archetype_key
from .params import WRECK_HOLD_S, WRECK_PICKUP_PX, WRECK_HEAL_PCT, WRECK_HEAL_DEFAULT
from .pickups import Wreck

class LootController:
    def __init__(self, ctx):
        self.fleet = ctx.fleet
        self.notifier = ctx.notifier
        self.wrecks = []
        self._rng = random.Random()          # рисунок обломков: на игру не влияет, сид не нужен

    # ---------- события ----------
    def on_bots_removed(self, bots):
        """Колбэк Fleet.on_removed: что оставляют после себя погибшие боты."""
        for bot in bots:
            key = archetype_key(bot.tank)
            if key is None:
                continue
            self.wrecks.append(Wreck.from_tank(bot.tank, key, ARCHETYPES[key].color, self._rng))

    # ---------- кадр ----------
    def update(self, dt):
        player = self.fleet.player
        hull = player.hull_obb() if player.alive else None
        for w in self.wrecks:
            w.life -= dt
            if hull is None or w.life <= 0.0:
                w.hold = 0.0
                continue
            on_it = obb_distance_to_point(hull, w.x, w.y) <= WRECK_PICKUP_PX
            if on_it and player.hp < player.max_hp:         # при полном здоровье обломки не «съедаются»
                w.hold += dt
                if w.hold >= WRECK_HOLD_S:
                    self._collect(w, player)
            else:
                w.hold = 0.0
        self.wrecks = [w for w in self.wrecks if w.life > 0.0 and not w.taken]

    def _collect(self, wreck, player):
        pct = WRECK_HEAL_PCT.get(wreck.key, WRECK_HEAL_DEFAULT)
        healed = player.heal(player.max_hp * pct)
        wreck.taken = True
        self.notifier.on_wreck_heal(player, healed)