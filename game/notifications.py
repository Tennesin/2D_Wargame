"""game/notifications.py — сообщения о попаданиях: лента сверху и всплывающие числа над целью."""
from engine import get_text, FONT_SIZE_HEADER, TargetType
from .texts import TRACK_RU, MODULE_ON

FEED_MAX = 5                 # сколько строк в ленте одновременно
FEED_LIFE = 3.5              # сколько секунд живёт строка
FEED_FADE = 0.8              # последние секунды строка плавно гаснет
FEED_TOP = 14                # отступ ленты от верхнего края окна, px
FEED_LINE_H = 26
FEED_SIZE = FONT_SIZE_HEADER

FLOAT_MAX = 24               # сколько всплывающих чисел одновременно
FLOAT_LIFE = 1.1
FLOAT_START_PX = 80.0        # на сколько выше центра цели число появляется (px мира)
FLOAT_RISE_PX = 140.0        # на сколько оно поднимается за время жизни (px мира)
FLOAT_SIZE = 22

C_GOOD = (110, 220, 110)
C_BAD = (240, 80, 70)
C_WARN = (240, 200, 70)
C_DIM = (170, 176, 186)
C_SHADOW = (0, 0, 0)

ZONE_RU = {"front": "в лоб", "side": "в борт", "rear": "в корму"}

def _faded(surf, alpha):
    """Копия поверхности с прозрачностью alpha (0..255). Исходную менять нельзя: она общая (кэш текста)."""
    if alpha >= 255:
        return surf
    out = surf.copy()
    out.set_alpha(alpha)
    return out

class _Line:
    __slots__ = ("text", "color", "age")

    def __init__(self, text, color):
        self.text, self.color, self.age = text, color, 0.0

class _Floater:
    __slots__ = ("x", "y", "text", "color", "age")

    def __init__(self, x, y, text, color):
        self.x, self.y, self.text, self.color, self.age = x, y, text, color, 0.0

class Notifier:
    """Принимает события боя (попадание, рикошет, промах) и показывает только те, что касаются игрока."""

    def __init__(self, player):
        self.player = player
        self._feed = []
        self._floaters = []

    # ---------- вывод ----------
    def say(self, text, color=C_DIM):
        """Строка в ленту."""
        self._feed.append(_Line(text, color))
        del self._feed[:-FEED_MAX]

    def float_at(self, x, y, text, color):
        """Всплывающий текст над точкой мира."""
        self._floaters.append(_Floater(x, y, text, color))
        del self._floaters[:-FLOAT_MAX]

    # ---------- события боя ----------
    def on_hit(self, owner, target, normal, res, dealt, min_frac=0.0):
        """Снаряд owner попал в target. res — HitResult, dealt — нанесённый урон.
        Вызывать ПОСЛЕ take_hit, чтобы hp уже был обновлён."""
        if res.ricochet:
            self.on_ricochet(owner, target)
            return
        me = self.player
        frag = dealt > 0.0 and res.damage_frac < min_frac
        if target is me:
            self._hit_on_player(normal, res, dealt, frag)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self._hit_on_enemy(target, normal, res, dealt, frag)
        elif owner is me and target.target_type is TargetType.WALL:
            self._hit_on_wall(target, dealt)
        elif owner is me and target.target_type is TargetType.TERRAIN:
            self.say("Камень: снаряд не пробил", C_DIM)

    def on_ricochet(self, owner, target):
        """Снаряд отскочил от target и летит дальше."""
        me = self.player
        if target is me:
            self.say("Рикошет! Снаряд отскочил от брони", C_GOOD)
            self.float_at(me.x, me.y, "рикошет", C_GOOD)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self.say("Рикошет! Цель цела", C_WARN)
            self.float_at(target.x, target.y, "рикошет", C_WARN)
        elif owner is me and target.target_type is TargetType.WALL:
            self.say("Рикошет от стены", C_DIM)

    def on_miss(self, owner):
        """Снаряд долетел до предела дальности, ничего не задев."""
        if owner is self.player:
            self.say("Промах", C_DIM)

    def on_ram(self, a, b, dmg_a, dmg_b, zone_a, zone_b):
        """Танки a и b столкнулись. dmg_* — урон каждому, zone_* — грань, принявшая удар.
        Показываем только столкновения с участием игрока."""
        me = self.player
        if me is a:
            foe, mine, theirs, my_zone, their_zone = b, dmg_a, dmg_b, zone_a, zone_b
        elif me is b:
            foe, mine, theirs, my_zone, their_zone = a, dmg_b, dmg_a, zone_b, zone_a
        else:
            return
        if mine <= 0.0 and theirs <= 0.0:
            return
        self.say(f"Таран! Врагу -{theirs:.0f} HP ({ZONE_RU[their_zone]}), "
                 f"вам -{mine:.0f} HP ({ZONE_RU[my_zone]})", C_WARN)
        if theirs > 0.0:
            self.float_at(foe.x, foe.y, f"-{theirs:.0f}", C_GOOD)
        if mine > 0.0:
            self.float_at(me.x, me.y, f"-{mine:.0f}", C_BAD)
        if foe.hp <= 0.0:
            self.say("ЦЕЛЬ УНИЧТОЖЕНА!", C_GOOD)

    def on_splash(self, owner, target, dealt):
        """Осколки фугаса задели target (не прямая цель). Показываем только связанное с игроком."""
        me = self.player
        if target is me:
            self.say(f"Осколки: -{dealt:.0f} HP", C_WARN)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_WARN)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self.float_at(target.x, target.y, f"-{dealt:.0f}", C_WARN)
            if target.hp <= 0.0:
                self.say("ЦЕЛЬ УНИЧТОЖЕНА!", C_GOOD)
        elif owner is me and target.target_type is TargetType.WALL:
            if target.hp <= 0.0:
                self.say("Стена разрушена", C_DIM)

    def on_track_broken(self, owner, target, side):
        """Сбита гусеница. Показываем только связанное с игроком."""
        me = self.player
        name = TRACK_RU[side]
        if target is me:
            self.say(f"Сбита {name} гусеница!", C_BAD)
            self.float_at(me.x, me.y, "гусеница", C_BAD)
        elif owner is me:
            self.say(f"Сбита {name} гусеница врага", C_GOOD)
            self.float_at(target.x, target.y, "гусеница", C_GOOD)

    def on_track_repaired(self, vehicle, side):
        if vehicle is self.player:
            self.say(f"{TRACK_RU[side].capitalize()} гусеница починена", C_GOOD)

    def on_module_absorb(self, owner, target, module):
        """Кумулятив сработал на внешнем модуле (гусеница, экран): пробитие упало."""
        me = self.player
        where = MODULE_ON.get(module, "модуле")
        if target is me:
            self.say(f"КС сработал на {where}: пробитие снижено", C_GOOD)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self.say(f"КС сработал на {where}: пробитие снижено", C_WARN)

    # ---------- разбор попаданий ----------
    def _hit_on_player(self, normal, res, dealt, frag=False):
        me = self.player
        zone = ZONE_RU[me.zone_at(normal)]
        if frag:
            self.say(f"Фугас {zone}: осколки -{dealt:.0f} HP", C_WARN)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_WARN)
        elif res.damage_frac <= 0.0:
            self.say(f"Броня не пробита! ({zone}, приведённая {res.eff_armor:.0f} мм)", C_GOOD)
            self.float_at(me.x, me.y, "0", C_GOOD)
        elif res.damage_frac >= 1.0:
            self.say(f"ВАС ПРОБИЛИ {zone}! -{dealt:.0f} HP", C_BAD)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_BAD)
        else:
            self.say(f"Частичное пробитие {zone}: -{dealt:.0f} HP", C_WARN)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_WARN)

    def _hit_on_enemy(self, target, normal, res, dealt, frag=False):
        zone = ZONE_RU[target.zone_at(normal)]
        if frag:
            self.say(f"Фугас {zone}: осколки -{dealt:.0f} HP (осталось {max(0.0, target.hp):.0f})", C_WARN)
            self.float_at(target.x, target.y, f"-{dealt:.0f}", C_WARN)
        elif res.damage_frac <= 0.0:
            self.say(f"Не пробито ({zone}): приведённая броня {res.eff_armor:.0f} мм", C_BAD)
            self.float_at(target.x, target.y, "0", C_DIM)
        elif res.damage_frac >= 1.0:
            self.say(f"Пробитие {zone}! -{dealt:.0f} HP (осталось {max(0.0, target.hp):.0f})", C_GOOD)
            self.float_at(target.x, target.y, f"-{dealt:.0f}", C_GOOD)
        else:
            self.say(f"Урон ослаблен ({zone}): -{dealt:.0f} HP", C_WARN)
            self.float_at(target.x, target.y, f"-{dealt:.0f}", C_WARN)
        if target.hp <= 0.0:
            self.say("ЦЕЛЬ УНИЧТОЖЕНА!", C_GOOD)

    def _hit_on_wall(self, wall, dealt):
        if dealt <= 0.0:
            self.say("Стена: броня не пробита", C_DIM)
        else:
            self.say(f"Стена: -{dealt:.0f} HP (осталось {max(0.0, wall.hp):.0f})", C_DIM)
        if wall.hp <= 0.0:
            self.say("Стена разрушена", C_DIM)

    # ---------- кадр ----------
    def update(self, dt):
        for group in (self._feed, self._floaters):
            for item in group:
                item.age += dt
        self._feed = [l for l in self._feed if l.age < FEED_LIFE]
        self._floaters = [f for f in self._floaters if f.age < FLOAT_LIFE]

    def draw(self, screen, camera):
        self._draw_floaters(screen, camera)
        self._draw_feed(screen)

    def _draw_floaters(self, screen, camera):
        for f in self._floaters:
            u = f.age / FLOAT_LIFE
            sx, sy = camera.world_to_screen(f.x, f.y - FLOAT_START_PX - FLOAT_RISE_PX * u)
            alpha = 255 if u < 0.6 else int(255 * (1.0 - (u - 0.6) / 0.4))
            self._blit_text(screen, f.text, FLOAT_SIZE, f.color, (round(sx), round(sy)), alpha)

    def _draw_feed(self, screen):
        cx = screen.get_width() // 2
        y = FEED_TOP + FEED_LINE_H // 2
        for line in self._feed:
            left = FEED_LIFE - line.age
            alpha = 255 if left >= FEED_FADE else int(255 * left / FEED_FADE)
            self._blit_text(screen, line.text, FEED_SIZE, line.color, (cx, y), alpha)
            y += FEED_LINE_H

    @staticmethod
    def _blit_text(screen, text, size, color, center, alpha):
        if alpha <= 0:
            return
        shadow = _faded(get_text(text, size, C_SHADOW), alpha)
        label = _faded(get_text(text, size, color), alpha)
        screen.blit(shadow, shadow.get_rect(center=(center[0] + 1, center[1] + 1)))
        screen.blit(label, label.get_rect(center=center))