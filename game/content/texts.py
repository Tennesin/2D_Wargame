"""game/content/texts.py — тексты интерфейса игры (слой game)."""

# Главное меню
MENU_PLAY = "Играть"
MENU_CONSTRUCTOR = "Конструктор"
MENU_INSTRUCTION = "Инструкция"
MENU_SETTINGS = "Настройки"
MENU_STATS = "Статистика"
MENU_QUIT = "Выйти"

# Инструкция
INSTRUCTION_TITLE = "Инструкция"

# Настройки
SETTINGS_TITLE = "Настройки"
SETTINGS_TECH = "Технические"
SETTINGS_GAME = "Игра"
SETTINGS_FPS_LIMIT = "Лимит FPS"
SETTINGS_SHOW_FPS = "Показывать FPS в бою"
SETTINGS_ROUND_TIME = "Время раунда"
SETTINGS_ROCK_HURTS = "Урон танку от тарана камня"
SETTINGS_ROCK_HURTS_HINT = "Удар о сдвигаемый камень наносит урон самой технике. Относится и к ботам."
SETTINGS_FRIENDLY_FIRE = "Урон по союзникам"
SETTINGS_FRIENDLY_FIRE_HINT = ("Осколки фугаса задевают и стрелявшего, а боты ранят друг друга осколками "
                               "и тараном. Прямые попадания снарядов по своим не засчитываются.")
SETTINGS_SAVE = "Сохранить"
BACK = "Назад"

# Новая игра
NEWGAME_TITLE = "Новая игра"
NEWGAME_MAP = "Карта"
NEWGAME_WIDTH = "Ширина карты"
NEWGAME_LENGTH = "Длина карты"
NEWGAME_MAP_HINT = "Размер задаётся отдельно по ширине и длине. Игрок появляется в центре карты."
NEWGAME_TANK = "Ваша техника"
NEWGAME_START = "В бой"
NEWGAME_ENEMIES = "Враги: архетипы"
NEWGAME_ENEMIES_HINT = "Появляются только отмеченные типы. Минимум один."
NEWGAME_LOCKED_NOTE = "последний"

# Подсказки над HUD
HINT_IDLE = "{combat} — боевой режим, {camera} — камера, {debug} — отладка"
HINT_COMBAT = "БОЕВОЙ РЕЖИМ: ЛКМ — огонь"
HINT_AMMO = "{a}/{b}/{c} — тип снаряда"
HINT_FREE_CAM = "Свободная камера ({key}): ПКМ — двигать"
HINT_VISCOUS = "Вязкая местность: скорость ×{k:.2f}"
HINT_STUNNED = "Оглушение: {t:.1f} с"
HINT_TURRET_LOCKED = "Башня зафиксирована ({key})"
KILLS = "Уничтожено: {n}"
DEATH_TITLE = "Машина уничтожена"
DEATH_HINT = "{key} — в меню"
DEATH_HINT = "{key} — итоги боя"

# Гусеницы
TRACK_RU = {"left": "левая", "right": "правая"}
HINT_TRACK_BROKEN = "Гусеница сбита ({sides}): {key} — ремонт"
HINT_TRACK_REPAIR = "Ремонт: {side} гусеница, {t:.1f} с"

# Раунды
ROUND_TITLE = "Раунд {n}"
ROUND_STARTS_IN = "Начало через {t} с"
ROUND_WAITING = "Группа выходит…"
ROUND_TIME_LEFT = "До конца раунда: {t} с"
ROUND_ENEMIES = "Врагов в группе: {alive} / {total}"

# Прочее
DISTANCE_FMT = "{:.0f} м"
ZONE_RU = {"front": "в лоб", "side": "в борт", "rear": "в корму"}
MODULE_ON = {"left": "гусенице", "right": "гусенице", "screen": "лобовом экране"}

# Статистика и итоги боя
STATS_TITLE = "Статистика"
RESULT_TITLE = "Итоги боя"
RESULT_AGAIN = "Играть снова"
RESULT_TO_MENU = "В меню"
STATS_NONE = "Нет данных"
STATS_TOTAL = "Всего"
STATS_RECORD_MARK = "   ★ рекорд!"

STATS_SEC_GENERAL = "Общее"
STATS_MATCHES = "Сыграно матчей"
STATS_SEC_ROUNDS = "Раунды"
STATS_ROUNDS = "Пройдено раундов"
STATS_SEC_DAMAGE = "Нанесённый урон"
STATS_BY_SHOTS = "Выстрелами"
STATS_BY_RAM = "Тараном"
STATS_SEC_KILLS = "Уничтожено врагов"
STATS_SEC_FIRE = "Стрельба"
STATS_ACCURACY = "Точность"
STATS_HITS = "Попаданий с уроном"
STATS_SHOTS = "Выпущено снарядов"
STATS_SEC_AMMO = "Снаряды по видам"
STATS_SEC_TAKEN = "Полученный урон"
STATS_FROM_SHOTS = "От выстрелов"
STATS_FROM_RAM = "От тарана"
STATS_SEC_SOURCES = "Больше всего урона нанесли"
STATS_SEC_RECORDS = "Рекорды"
STATS_REC_ROUNDS = "Раундов за матч"
STATS_REC_DAMAGE = "Урона за матч"
STATS_REC_KILLS = "Врагов за матч"

AMMO_RU = {"AP": "Бронебойные", "HEAT": "Кумулятивные",
           "HESH": "HESH", "HE": "Осколочно-фугасные"}