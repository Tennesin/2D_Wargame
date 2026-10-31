"""game/hud/upgrade_link.py — связка панели улучшений с LootController: превращает ячейки и предложение
в простые данные для виджета и отдаёт ему действия «взять / отказаться / заменить». Сам виджет про игру не знает."""
from ai import ARCHETYPES
from inputs import Action, key_label
from ui import CellView, OfferView
from ..content import texts
from ..match.loot.upgrades import UPGRADES, Plan, MAX_LEVEL

class UpgradeLink:
    def __init__(self, bar, loot):
        self.bar = bar
        self.loot = loot
        self._take = texts.UPGRADE_TAKE.format(key=key_label(Action.TAKE_UPGRADE))
        self._decline = texts.UPGRADE_DECLINE.format(key=key_label(Action.DECLINE_UPGRADE))
        bar.on_take = loot.take            # take(slot=None)
        bar.on_replace = loot.take         # take(номер ячейки)
        bar.on_decline = loot.decline
        self.update()

    def update(self):
        """Каждый кадр после Match.update."""
        cells = []
        for s in self.loot.slots.slots:
            if s is None:
                cells.append(None)
                continue
            key, level = s
            d = UPGRADES[key]
            cells.append(CellView(d.title, level, MAX_LEVEL, ARCHETYPES[key].color, d.effect(level)))
        self.bar.set_state(cells, self._offer())

    def _offer(self):
        r = self.loot.offer
        if r is None:
            return None
        slots = self.loot.slots
        d = UPGRADES[r.key]
        plan = slots.plan(r.key)
        if plan is Plan.MAXED:
            return None
        if plan is Plan.LEVEL_UP:
            level = slots.slots[slots.index_of(r.key)][1]
            info = texts.UPGRADE_LEVEL.format(a=level, b=level + 1, effect=d.effect(level + 1))
        elif plan is Plan.FREE:
            info = texts.UPGRADE_NEW.format(effect=d.effect(1))
        else:
            info = texts.UPGRADE_REPLACE.format(effect=d.effect(1))
        return OfferView(d.title, ARCHETYPES[r.key].color, info, plan is Plan.REPLACE,
                         self._take, self._decline)