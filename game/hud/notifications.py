"""game/hud/notifications.py — сообщения о попаданиях: лента сверху и всплывающие числа над целью."""
from engine import get_text, FONT_SIZE_HEADER, TargetType
from ..content.texts import TRACK_RU, MODULE_ON
from ui import DamageFeed, FeedIcon, FeedTone

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
        self.feed = DamageFeed()
        self._pending = []

    # ---------- вывод ----------
    def say(self, text, color=C_DIM):
        """Строка в ленту."""
        self._feed.append(_Line(text, color))
        del self._feed[:-FEED_MAX]

    def float_at(self, x, y, text, color):
        """Всплывающий текст над точкой мира."""
        self._floaters.append(_Floater(x, y, text, color))
        del self._floaters[:-FLOAT_MAX]

    def _push(self, icon, tone, value):
        """Событие для иконочной ленты. Одинаковые «иконка + тон» за один кадр складываются в одно число."""
        for item in self._pending:
            if item[0] is icon and item[1] is tone:
                item[2] += value
                return
        self._pending.append([icon, tone, value])

    # ---------- события боя ----------
    def on_hit(self, owner, target, normal, res, dealt):
        """Снаряд owner попал в target."""
        if res.ricochet:
            self.on_ricochet(owner, target)
            return
        me = self.player
        frag = dealt > 0.0 and res.damage_frac <= 0.0
        if target is me:
            self._hit_on_player(normal, res, dealt, frag)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self._hit_on_enemy(target, normal, res, dealt, frag)
        elif owner is me and target.target_type is TargetType.WALL:
            self._hit_on_wall(target, dealt)

    def on_ricochet(self, owner, target):
        """Рикошеты в иконочную ленту не попадают."""
        me = self.player
        if target is me:
            self.float_at(me.x, me.y, "рикошет", C_GOOD)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self.float_at(target.x, target.y, "рикошет", C_WARN)
        elif owner is me and target.target_type is TargetType.WALL:
            self.say("Рикошет от стены", C_DIM)

    def on_miss(self, owner):
        """Промахи игнорируются."""

    def on_ram(self, a, b, dmg_a, dmg_b, zone_a, zone_b):
        """Танки a и b столкнулись."""
        me = self.player
        if me is a:
            foe, mine, theirs = b, dmg_a, dmg_b
        elif me is b:
            foe, mine, theirs = a, dmg_b, dmg_a
        else:
            return
        if mine <= 0.0 and theirs <= 0.0:
            return
        if theirs > 0.0:
            self._push(FeedIcon.RAM, FeedTone.GOOD, theirs)
            self.float_at(foe.x, foe.y, f"-{theirs:.0f}", C_GOOD)
        if mine > 0.0:
            self._push(FeedIcon.RAM, FeedTone.BAD, mine)
            self.float_at(me.x, me.y, f"-{mine:.0f}", C_BAD)
        if foe.hp <= 0.0:
            self.say("ЦЕЛЬ УНИЧТОЖЕНА!", C_GOOD)

    def on_rock_ram(self, dmg):
        """Игрок получил урон от тарана камня."""
        if dmg > 0.0:
            self._push(FeedIcon.RAM, FeedTone.BAD, dmg)
            self.float_at(self.player.x, self.player.y, f"-{dmg:.0f}", C_BAD)

    def on_splash(self, owner, target, dealt):
        """Осколки фугаса задели target (не прямая цель)."""
        me = self.player
        if target is me:
            self._push(FeedIcon.SHIELD, FeedTone.WARN, dealt)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_WARN)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self._push(FeedIcon.SHELL, FeedTone.WARN, dealt)
            self.float_at(target.x, target.y, f"-{dealt:.0f}", C_WARN)
            if target.hp <= 0.0:
                self.say("ЦЕЛЬ УНИЧТОЖЕНА!", C_GOOD)
        elif owner is me and target.target_type is TargetType.WALL:
            if target.hp <= 0.0:
                self.say("Стена разрушена", C_DIM)

    def on_artillery(self, owner, target, dealt, stunned):
        """Взрыв САУ задел target."""
        me = self.player
        if target is not me:
            return
        self._push(FeedIcon.SHIELD, FeedTone.BAD, dealt)
        self.float_at(me.x, me.y, f"-{dealt:.0f}", C_BAD)
        if stunned:
            self.on_stun(owner, target)

    def on_track_broken(self, owner, target, side):
        """Сбитые гусеницы игнорируются."""
        me = self.player
        if target is me:
            self.float_at(me.x, me.y, "гусеница", C_BAD)
        elif owner is me:
            self.float_at(target.x, target.y, "гусеница", C_GOOD)

    def on_track_repaired(self, vehicle, side):
        if vehicle is self.player:
            self.say(f"{TRACK_RU[side].capitalize()} гусеница починена", C_GOOD)

    def on_wreck_heal(self, player, healed):
        """Игрок подобрал обломки и восстановил здоровье."""
        if healed <= 0.0:
            return
        self._push(FeedIcon.PLUS, FeedTone.GOOD, healed)
        self.float_at(player.x, player.y, f"+{healed:.0f}", C_GOOD)

    def on_upgrade_drop(self, title):
        """С последнего бота раунда выпали останки улучшения."""
        self.say(f"Останки улучшения: «{title}»", C_WARN)

    def on_upgrade(self, player, title, level):
        """Игрок взял улучшение (или повысил его уровень)."""
        self.say(f"Улучшение «{title}»: уровень {level}", C_GOOD)
        self.float_at(player.x, player.y, f"{title} {level}", C_GOOD)

    def on_stun(self, owner, target):
        """Цель оглушена прямым попаданием HESH. Показываем только связанное с игроком."""
        me = self.player
        if target is me:
            self.say("Вы оглушены!", C_BAD)
            self.float_at(me.x, me.y, "оглушение", C_BAD)
        elif owner is me:
            self.say("Враг оглушён", C_GOOD)
            self.float_at(target.x, target.y, "оглушение", C_GOOD)

    def on_module_absorb(self, owner, target, module, lost_mm):
        """Внешний модуль (гусеница, экран) съел часть пробития."""
        me = self.player
        where = MODULE_ON.get(module, "модуле")
        if target is me:
            self.say(f"Пробитие снижено на {lost_mm:.0f} мм на {where}", C_GOOD)
        elif owner is me and target.target_type is TargetType.VEHICLE:
            self.say(f"Пробитие снижено на {lost_mm:.0f} мм на {where}", C_WARN)

    # ---------- разбор попаданий ----------
    def _hit_on_player(self, normal, res, dealt, frag=False):
        me = self.player
        if frag:
            self._push(FeedIcon.SHIELD, FeedTone.WARN, dealt)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_WARN)
        elif res.damage_frac <= 0.0:
            self._push(FeedIcon.SHIELD, FeedTone.GOOD, 0.0)
            self.float_at(me.x, me.y, "0", C_GOOD)
        elif res.damage_frac >= 1.0:
            self._push(FeedIcon.SHIELD, FeedTone.BAD, dealt)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_BAD)
        else:
            self._push(FeedIcon.SHIELD, FeedTone.WARN, dealt)
            self.float_at(me.x, me.y, f"-{dealt:.0f}", C_WARN)

    def _hit_on_enemy(self, target, normal, res, dealt, frag=False):
        if frag:
            self._push(FeedIcon.SHELL, FeedTone.WARN, dealt)
            self.float_at(target.x, target.y, f"-{dealt:.0f}", C_WARN)
        elif res.damage_frac <= 0.0:
            self._push(FeedIcon.SHELL, FeedTone.BAD, 0.0)
            self.float_at(target.x, target.y, "0", C_DIM)
        elif res.damage_frac >= 1.0:
            self._push(FeedIcon.SHELL, FeedTone.GOOD, dealt)
            self.float_at(target.x, target.y, f"-{dealt:.0f}", C_GOOD)
        else:
            self._push(FeedIcon.SHELL, FeedTone.WARN, dealt)
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

        for icon, tone, value in self._pending:
            self.feed.push(icon, tone, value)
        self._pending.clear()
        self.feed.update(dt)

    def draw(self, screen, camera):
        self._draw_floaters(screen, camera)
        self._draw_feed(screen)
        self.feed.draw(screen)

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