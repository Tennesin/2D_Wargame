"""game/match/rounds/composer.py — состав группы: какие архетипы открыты, кого выбрать, под какой бюджет.
Не знает ни про экран, ни про поиск места: на вход игрок и номер раунда, на выход готовые танки."""
from engine import Team
from vehicles import VEHICLE_TYPES, make_vehicle
from ai import ARCHETYPES, fit_loadout, threat_profile, counter_multipliers
from ai.loadout import loadout_cost
from .schedule import round_budgets, UNLOCKS, EARLY_UNLOCK_ROUND, EARLY_UNLOCK_MULT, REPEAT_K

class GroupComposer:
    def __init__(self, prefs, rng):
        self.prefs = prefs
        self.rng = rng                     # общий с BotSpawner: порядок вызовов не меняется
        self.profile = {}                  # профиль игрока (для отладочных строк)
        self.multipliers = {}              # множители шансов архетипов (для отладки)
        self.fit_info = "-"                # «Универсал 100%, Разведчик 99%»: попадание в бюджет

    def compose(self, round_n, player):
        """Подбирает сборки группы по текущей цене танка игрока. Возвращает [(архетип, танк)]."""
        value = player.spec.cost
        self.profile = threat_profile(player.spec)
        pool, mult = self._unlocked(round_n)

        picked, result, info = [], [], []
        for frac in round_budgets(round_n):
            key = self._pick_key(pool, mult, picked)
            picked.append(key)
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

    def _unlocked(self, round_n):
        """Открытые на этом раунде архетипы (только включённые в настройках) и их множители шансов."""
        allowed = self.prefs.enabled_keys()
        keys = [k for k in ARCHETYPES if k in allowed]
        mult = counter_multipliers(self.profile, keys)
        self.multipliers = mult
        ordered = [(n, k) for n, k in UNLOCKS if k in allowed]
        progress = round_n + ordered[0][0] - 1            # первый из включённых доступен с раунда 1
        pool = [k for n, k in ordered
                if progress >= n
                or (round_n >= EARLY_UNLOCK_ROUND and mult[k] >= EARLY_UNLOCK_MULT)]
        return pool, mult

    def _pick_key(self, pool, mult, picked):
        weights = [ARCHETYPES[k].spawn_weight * mult[k] * REPEAT_K ** picked.count(k)
                   for k in pool]
        return self.rng.choices(pool, weights=weights)[0]