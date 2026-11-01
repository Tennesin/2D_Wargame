"""game/match/loot/controller.py — добыча в партии: обломки и останки улучшений."""
import math
import random

from ai import ARCHETYPES
from engine import obb_distance_to_point
from inputs import Action
from ...state.stats import archetype_key
from .params import (
    WRECK_HOLD_S, WRECK_PICKUP_PX, WRECK_HEAL_PCT, WRECK_HEAL_DEFAULT,
    UPGRADE_MIN_ROUND, UPGRADE_PICKUP_PX, UPGRADE_OFFSET_PX, UPGRADE_CLEAR_PX,
    UPGRADE_SPOT_TRIES,
)
from .pickups import Wreck, UpgradeRemains
from .upgrades import UpgradeSlots, UPGRADES, Plan

class LootController:
    def __init__(self, ctx, input_handler):
        self.fleet = ctx.fleet
        self.terrain = ctx.terrain
        self.walls = ctx.walls
        self.notifier = ctx.notifier
        self.input = input_handler
        self.wrecks = []
        self.remains = []                    # останки улучшений на земле
        self.offer = None                    # останки, которые сейчас предлагаются игроку (или None)
        self.slots = UpgradeSlots()          # ячейки игрока (живут одну партию)
        self._rng = random.Random()          # рисунок обломков и место останков: на игру не влияет
        self.match_stats = ctx.match_stats

    # ---------- события ----------
    def on_bots_removed(self, bots):
        """Колбэк Fleet.on_removed: что оставляют после себя погибшие боты."""
        for bot in bots:
            key = archetype_key(bot.tank)
            if key is None:
                continue
            self.wrecks.append(Wreck.from_tank(bot.tank, key, ARCHETYPES[key].color, self._rng))
        self._drop_upgrades(bots)

    def _drop_upgrades(self, dead):
        """Улучшение выпадает с последнего бота раунда."""
        alive_rounds = {b.round for b in self.fleet.bots}
        for rnd in sorted({b.round for b in dead}):
            if rnd < UPGRADE_MIN_ROUND or rnd in alive_rounds:
                continue
            last = max((b for b in dead if b.round == rnd), key=lambda b: b.tank.spec.cost)
            key = archetype_key(last.tank)
            if key not in UPGRADES or self.slots.plan(key) is Plan.MAXED:
                continue                                      # предлагать нечего
            x, y = self._free_spot(last.tank)
            self.remains.append(UpgradeRemains(x, y, key, ARCHETYPES[key].color))
            self.notifier.on_upgrade_drop(UPGRADES[key].title)

    def _free_spot(self, tank):
        """Точка рядом с обломками, где свободно (камни, глубокая вода, стены, край карты)."""
        cx, cy = tank.hull_obb()[:2]
        lo, hi = UPGRADE_OFFSET_PX
        for _ in range(UPGRADE_SPOT_TRIES):
            a = self._rng.uniform(0.0, 2.0 * math.pi)
            r = self._rng.uniform(lo, hi)
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            probe = (x, y, UPGRADE_CLEAR_PX, UPGRADE_CLEAR_PX, 0.0)
            if not self.terrain.blocks_obb(probe) and not self.walls.blocks_obb(probe):
                return x, y
        return cx, cy

    # ---------- ввод ----------
    def handle_hotkeys(self):
        """Взять или отказаться."""
        if self.offer is None:
            return
        if self.input.was_pressed(Action.DECLINE_UPGRADE):
            self.decline()
        elif self.input.was_pressed(Action.TAKE_UPGRADE):
            if self.slots.plan(self.offer.key) is not Plan.REPLACE:
                self.take()

    def take(self, slot=None):
        """Взять предложенное улучшение. slot нужен только если все ячейки заняты. True при успехе."""
        r = self.offer
        if r is None:
            return False
        done = self.slots.apply(r.key, slot)
        if done is None:
            return False
        r.gone = True
        self.offer = None
        self.match_stats.on_upgrade_taken(r.key)
        player = self.fleet.player
        player.set_mods(self.slots.build_mods())
        self.notifier.on_upgrade(player, UPGRADES[r.key].title, done[1])
        return True

    def decline(self):
        """Отказаться: останки исчезают сразу."""
        r = self.offer
        if r is None:
            return
        r.gone = True
        self.offer = None

    # ---------- кадр ----------
    def update(self, dt):
        player = self.fleet.player
        hull = player.hull_obb() if player.alive else None
        self._update_wrecks(dt, player, hull)
        self._update_remains(dt, hull)

    def _update_wrecks(self, dt, player, hull):
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

    def _update_remains(self, dt, hull):
        """Таймеры останков и выбор того, что предлагается игроку (ближайшее из тех, над которыми он стоит)."""
        best, best_d = None, None
        for r in self.remains:
            r.life -= dt
            if r.life <= 0.0 or r.gone:
                continue
            if self.slots.plan(r.key) is Plan.MAXED:
                r.gone = True                                # уже прокачано другим подбором: предлагать нечего
                continue
            if hull is None:
                continue
            d = obb_distance_to_point(hull, r.x, r.y)
            if d <= UPGRADE_PICKUP_PX and (best_d is None or d < best_d):
                best, best_d = r, d
        self.remains = [r for r in self.remains if r.life > 0.0 and not r.gone]
        self.offer = best

    def _collect(self, wreck, player):
        pct = WRECK_HEAL_PCT.get(wreck.key, WRECK_HEAL_DEFAULT)
        healed = player.heal(player.max_hp * pct)
        wreck.taken = True
        self.match_stats.on_wreck_collected(healed)
        self.notifier.on_wreck_heal(player, healed)