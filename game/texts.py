"""game/texts.py — тексты интерфейса игры (слой game)."""

# Главное меню
MENU_PLAY = "Играть"
MENU_CONSTRUCTOR = "Конструктор"
MENU_INSTRUCTION = "Инструкция"
MENU_SETTINGS = "Настройки"
MENU_QUIT = "Выйти"

# Инструкция
INSTRUCTION_TITLE = "Инструкция"

# Настройки
SETTINGS_TITLE = "Настройки"
SETTINGS_SUBTITLE = "Враги: допустимые архетипы"
SETTINGS_HINT = "Изменения вступят в силу в новой игре."
SETTINGS_LOCKED_NOTE = "последний"
BACK = "Назад"

# Подсказки над HUD
HINT_IDLE = "{combat} — боевой режим, {camera} — камера, {debug} — отладка"
HINT_COMBAT = "БОЕВОЙ РЕЖИМ: ЛКМ — огонь"
HINT_AMMO = "{a}/{b}/{c} — тип снаряда"
HINT_FREE_CAM = "Свободная камера ({key}): ПКМ — двигать"
HINT_VISCOUS = "Вязкая местность: скорость ×{k:.2f}"
HINT_TURRET_LOCKED = "Башня зафиксирована ({key})"
KILLS = "Уничтожено: {n}"
DEATH_TITLE = "Машина уничтожена"
DEATH_HINT = "{key} — в меню"

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