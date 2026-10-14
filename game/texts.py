"""game/texts.py — тексты интерфейса игры (слой game)."""

# Главное меню
MENU_PLAY = "Играть"
MENU_CONSTRUCTOR = "Конструктор"
MENU_SETTINGS = "Настройки"
MENU_QUIT = "Выйти"

# Настройки
SETTINGS_TITLE = "Настройки"
SETTINGS_SUBTITLE = "Враги: допустимые архетипы"
SETTINGS_HINT = "Изменения вступят в силу в новой игре."
SETTINGS_LOCKED_NOTE = "нельзя отключить"
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

# Прочее
DISTANCE_FMT = "{:.0f} м"
ZONE_RU = {"front": "в лоб", "side": "в борт", "rear": "в корму"}