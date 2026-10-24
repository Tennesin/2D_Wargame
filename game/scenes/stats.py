"""game/scenes/stats.py — «Статистика» (из меню) и «Итоги боя» (после матча): таблицы на основе TableScene."""
from ui import Button
from .table_scene import TableScene, BTN_W, BTN_H
from ..content import texts
from ..content.stats_tables import career_items, result_items

class StatsScene(TableScene):
    def __init__(self, career, on_back, on_quit):
        back = Button((0, 0, BTN_W, BTN_H), texts.BACK)
        super().__init__(texts.STATS_TITLE, career_items(career), [(back, on_back)], on_quit, on_back)

class ResultScene(TableScene):
    def __init__(self, stats, career, on_again, on_menu, on_quit):
        again = Button((0, 0, BTN_W, BTN_H), texts.RESULT_AGAIN)
        menu = Button((0, 0, BTN_W, BTN_H), texts.RESULT_TO_MENU)
        super().__init__(texts.RESULT_TITLE, result_items(stats, career),
                         [(again, on_again), (menu, on_menu)], on_quit, on_menu)