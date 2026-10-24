"""game/background/casting.py — подбор техники для актёров: машина игрока из конструктора и боты по архетипам."""
from ai import ARCHETYPES, fit_loadout
from engine import Team
from vehicles import VEHICLE_TYPES, SPGSpec, make_vehicle

class Casting:
    def __init__(self, session, rng):
        self.session = session
        self.rng = rng
        self._arty = {}

    def player(self):
        """Техника игрока ровно из конструктора."""
        return make_vehicle(self.session.kind, self.session.spec(), team=Team.PLAYER)

    def bot(self, key, budget_k=0.7):
        """Бот архетипа key, собранный под долю стоимости машины игрока (как в GroupComposer)."""
        arch = ARCHETYPES[key]
        budget = self.session.spec().cost * budget_k
        values = fit_loadout(arch, budget, self.rng)
        spec = VEHICLE_TYPES[arch.kind].spec_cls.from_values(values, unbounded=True)
        return make_vehicle(arch.kind, spec, team_color=arch.color, team=Team.BOTS,
                            label=arch.name, emblem=arch.emblem)

    def arty_spec(self, cal=200):
        """Спецификация САУ: из неё берутся параметры снаряда, взрыва и вспышки. Самих САУ на экране нет."""
        spec = self._arty.get(cal)
        if spec is None:
            spec = self._arty[cal] = SPGSpec(cal, 25, 25, 25, 800)
        return spec