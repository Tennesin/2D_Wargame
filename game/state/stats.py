"""game/state/stats.py — игровая статистика."""
from engine import Team, TargetType
from . import storage

STATS_FILE = "stats.json"
FORMAT_VERSION = 1

NUMBERS = ("rounds", "damage_shots", "damage_ram", "shots_fired", "hits", "taken_shots", "taken_ram",
           "play_time", "distance_px", "misses", "ricochets_own", "ricochets_armor",
           "stuns_dealt", "stuns_taken", "tracks_broken", "tracks_lost", "tracks_repaired",
           "wrecks_taken", "healed", "upgrades_taken")
TABLES = ("kills", "ammo", "taken_from", "upgrades")
RECORDS = ("rounds", "damage", "kills", "best_hit", "time")

def archetype_key(tank):
    """Ключ архетипа техники."""
    return getattr(tank, "arch_key", None)

def _inc(table, key, amount=1):
    table[key] = table.get(key, 0) + amount

def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)

# ==========================================
# ОБЩИЕ ПОКАЗАТЕЛИ
# ==========================================

class StatsData:
    """Набор показателей. Общий для одной партии и для накопленной статистики:
    таблицы интерфейса строятся по одним и тем же полям."""
    best_hit = 0.0        # самый сильный выстрел: у партии своё значение, у Career это рекорд (property)

    def __init__(self):
        for name in NUMBERS:
            setattr(self, name, 0)
        for name in TABLES:
            setattr(self, name, {})

    @property
    def damage(self):
        return self.damage_shots + self.damage_ram

    @property
    def taken(self):
        return self.taken_shots + self.taken_ram

    @property
    def kills_total(self):
        return sum(self.kills.values())

    @property
    def accuracy(self):
        """Доля выстрелов, прямо попавших по врагу и нанёсших урон (0..1)."""
        return min(1.0, self.hits / self.shots_fired) if self.shots_fired else 0.0

# ==========================================
# ОДНА ПАРТИЯ
# ==========================================

class MatchStats(StatsData):
    def __init__(self, player):
        super().__init__()
        self.player = player
        self.active = True               # False после конца партии: поздние события не считаются
        self.new_records = set()         # какие рекорды побиты этой партией (заполняет Career.add_match)
        self._hurt = set()               # id врагов, которым игрок нанёс урон (для зачёта убийств)
        self.best_hit = 0.0              # урон самого сильного прямого попадания игрока

    def stop(self):
        self.active = False

    # ---------- события ----------
    def on_round_finished(self):
        if self.active:
            self.rounds += 1

    def on_shot(self, kind):
        """Игрок выстрелил снарядом kind (AmmoKind)."""
        if self.active:
            self.shots_fired += 1
            _inc(self.ammo, kind.name)

    def on_enemy_destroyed(self, tank):
        if not self.active:
            return
        if id(tank) not in self._hurt:
            return
        self._hurt.discard(id(tank))
        key = archetype_key(tank)
        if key is not None:
            _inc(self.kills, key)

    def on_damage(self, source, target, amount, via, direct=False):
        """source нанёс target реально снятые amount HP. via: "shot" или "ram".
        direct=True: прямое попадание снаряда (идёт в точность)."""
        if not self.active or amount <= 0.0:
            return
        me = self.player
        if source is me and target is not me and target.team is Team.BOTS:
            self._hurt.add(id(target))
            if via == "ram":
                self.damage_ram += amount
            else:
                self.damage_shots += amount
                if direct:
                    self.hits += 1
                    self.best_hit = max(self.best_hit, amount)
        elif target is me and source is not None and source is not me:
            if via == "ram":
                self.taken_ram += amount
            else:
                self.taken_shots += amount
            key = archetype_key(source)
            if key is not None:
                _inc(self.taken_from, key, amount)

    def on_time(self, dt):
        """Секунды, прожитые игроком в бою."""
        if self.active:
            self.play_time += dt

    def on_move(self, distance_px):
        """Сколько игрок проехал за кадр."""
        if self.active and distance_px > 0.0:
            self.distance_px += distance_px

    def on_miss(self, owner):
        if self.active and owner is self.player:
            self.misses += 1

    def on_ricochet(self, owner, target):
        """Рикошет от техники: свой снаряд отскочил от врага или вражеский от вашей брони."""
        if not self.active or target.target_type is not TargetType.VEHICLE:
            return
        me = self.player
        if owner is me and target is not me:
            self.ricochets_own += 1
        elif target is me and owner is not me:
            self.ricochets_armor += 1

    def on_stun(self, source, target):
        if not self.active:
            return
        me = self.player
        if source is me and target is not me:
            self.stuns_dealt += 1
        elif target is me:
            self.stuns_taken += 1

    def on_track_broken(self, source, target):
        if not self.active:
            return
        me = self.player
        if target is me:
            self.tracks_lost += 1
        elif source is me:
            self.tracks_broken += 1

    def on_track_repaired(self, vehicle):
        if self.active and vehicle is self.player:
            self.tracks_repaired += 1

    def on_wreck_collected(self, healed):
        if self.active and healed > 0.0:
            self.wrecks_taken += 1
            self.healed += healed

    def on_upgrade_taken(self, key):
        if self.active:
            self.upgrades_taken += 1
            _inc(self.upgrades, key)

# ==========================================
# НАКОПЛЕННАЯ СТАТИСТИКА И РЕКОРДЫ
# ==========================================

class Career(StatsData):
    def __init__(self):
        super().__init__()
        self.matches = 0
        self.records = {name: 0 for name in RECORDS}
        self._load()

    @property
    def best_hit(self):
        """У накопленной статистики это рекорд."""
        return self.records["best_hit"]

    def add_match(self, m):
        """Прибавляет партию к «Статистике» и обновляет «Рекорды» (только если новое значение лучше).
        Возвращает множество ключей побитых рекордов. Сразу сохраняет файл."""
        self.matches += 1
        for name in NUMBERS:
            setattr(self, name, getattr(self, name) + getattr(m, name))
        for name in TABLES:
            mine = getattr(self, name)
            for key, value in getattr(m, name).items():
                _inc(mine, key, value)

        broken = set()
        for name, value in (("rounds", m.rounds), ("damage", round(m.damage)), ("kills", m.kills_total),
                            ("best_hit", round(m.best_hit)), ("time", round(m.play_time))):
            if value > self.records[name]:
                self.records[name] = value
                broken.add(name)
        self.save()
        return broken

    # ---------- файл ----------
    def to_dict(self):
        data = {"version": FORMAT_VERSION, "matches": self.matches, "records": dict(self.records)}
        for name in NUMBERS:
            data[name] = getattr(self, name)
        for name in TABLES:
            data[name] = dict(getattr(self, name))
        return data

    def save(self):
        return storage.write_json(STATS_FILE, self.to_dict())

    def _load(self):
        """Каждое поле проверяется отдельно: испорченное остаётся нулевым, остальные подхватываются."""
        data = storage.read_json(STATS_FILE)
        if not isinstance(data, dict):
            return
        if _is_number(data.get("matches")):
            self.matches = data["matches"]
        for name in NUMBERS:
            if _is_number(data.get(name)):
                setattr(self, name, data[name])
        for name in TABLES:
            table = data.get(name)
            if isinstance(table, dict):
                setattr(self, name, {str(k): v for k, v in table.items() if _is_number(v)})
        records = data.get("records")
        if isinstance(records, dict):
            for name in RECORDS:
                if _is_number(records.get(name)):
                    self.records[name] = records[name]