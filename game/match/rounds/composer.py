"""game/match/rounds/composer.py — состав группы: какие архетипы открыты, кого выбрать, под какой бюджет.
Не знает ни про экран, ни про поиск места: на вход игрок и номер раунда, на выход готовые танки."""
from engine import Team
from vehicles import VEHICLE_TYPES, make_vehicle
from ai import ARCHETYPES, fit_loadout, threat_profile, counter_multipliers
from ai.roster.loadout import loadout_cost
from .schedule import (round_budgets, artillery_slots, UNLOCKS, ARTILLERY_KEY,
                       EARLY_UNLOCK_ROUND, EARLY_UNLOCK_MULT, REPEAT_K)

class GroupComposer:
    def __init__(self, prefs, rng):
        self.prefs = prefs
        self.rng = rng                     # общий с BotSpawner
        self.profile = {}                  # профиль игрока (для отладочных строк)
        self.multipliers = {}              # множители шансов архетипов (для отладки)
        self.fit_info = "-"                # «Универсал 100%, Разведчик 99%»: попадание в бюджет

    def compose(self, round_n, player):
        """Подбирает сборки группы по текущей цене танка игрока. Возвращает [(архетип, танк)]."""
        value = player.spec.cost
        self.profile = threat_profile(player.spec)
        pool, mult = self._unlocked(round_n)

        budgets = round_budgets(round_n)
        keys = [ARTILLERY_KEY] * self._artillery_count(len(budgets), pool)
        while len(keys) < len(budgets):
            keys.append(self._pick_key(pool, mult, keys))

        result, info = [], []
        for key, frac in zip(keys, budgets):
            arch = ARCHETYPES[key]
            budget = value * frac
            values = fit_loadout(arch, budget, self.rng)
            spec = VEHICLE_TYPES[arch.kind].spec_cls.from_values(values, unbounded=True)
            tank = make_vehicle(arch.kind, spec, team_color=arch.color, team=Team.BOTS,
                                label=arch.name, emblem=arch.emblem)
            result.append((arch, tank))
            info.append(f"{arch.name} {loadout_cost(values, VEHICLE_TYPES[arch.kind]) / budget * 100:.0f}%")
        self.fit_info = ", ".join(info)
        return result

    def _artillery_count(self, count, pool):
        """Сколько слотов займёт САУ. Пустой pool значит, что обычных архетипов не включено вовсе."""
        if ARTILLERY_KEY not in self.prefs.enabled_keys():
            return 0
        return artillery_slots(count, self.rng.random(), only=not pool)

    def _unlocked(self, round_n):
        """Открытые на этом раунде обычные архетипы (только включённые в настройках) и множители шансов.
        САУ сюда не входит: её слоты считает _artillery_count."""
        allowed = self.prefs.enabled_keys()
        regular = [k for k in ARCHETYPES if k in allowed and k != ARTILLERY_KEY]
        mult = counter_multipliers(self.profile, regular)
        self.multipliers = mult
        ordered = [(n, k) for n, k in UNLOCKS if k in allowed]
        if not ordered:                                   # включена только артиллерия
            return [], mult
        progress = round_n + ordered[0][0] - 1            # первый из включённых доступен с раунда 1
        pool = [k for n, k in ordered
                if progress >= n
                or (round_n >= EARLY_UNLOCK_ROUND and mult[k] >= EARLY_UNLOCK_MULT)]
        return pool, mult

    def _pick_key(self, pool, mult, picked):
        weights = [ARCHETYPES[k].spawn_weight * mult[k] * REPEAT_K ** picked.count(k)
                   for k in pool]
        return self.rng.choices(pool, weights=weights)[0]