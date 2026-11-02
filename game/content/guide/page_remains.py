"""game/content/guide/page_remains.py — страница инструкции «Останки»: обломки (лечение) и останки улучшений."""
from ai import ARCHETYPES
from inputs import Action
from engine import shade_color
from ui import SectionHeader, InfoText, AccordionRow, make_swatch_icon, make_upgrade_icon
from ...match.loot.params import (
    WRECK_LIFE_S, WRECK_HOLD_S, WRECK_HEAL_PCT,
    UPGRADE_MIN_ROUND, UPGRADE_LIFE_S, WRECK_ZONE_MARGIN_M
)
from ...match.loot.upgrades import UPGRADES, SLOT_COUNT, MAX_LEVEL
from ...view.loot_view import HEAL, UPG_RING
from .. import texts
from .common import k as _k

def _heal_rows():
    """Сколько лечат обломки каждого класса, от большего к меньшему."""
    ranked = sorted(WRECK_HEAL_PCT.items(), key=lambda kv: -kv[1])
    return [f"{ARCHETYPES[key].name}: {pct * 100:g}% максимального здоровья."
            for key, pct in ranked if key in ARCHETYPES]

def _upgrade_rows():
    """Список улучшений: по одной строке на улучшение, пункты по уровням."""
    rows = []
    for key, d in UPGRADES.items():
        arch = ARCHETYPES[key]
        details = [f"Уровень {lvl}: {d.effect(lvl)}." for lvl in range(1, MAX_LEVEL + 1)]
        details.append(f"Выпадает с врага «{arch.name}».")
        rows.append(AccordionRow(make_upgrade_icon(d.icon, (32, 32), 2, bg=shade_color(arch.color, 0.55)),
                                 d.title, f"{d.label}. Источник: «{arch.name}».", details, col_w=40))
    return rows

def build():
    take, decline = _k(Action.TAKE_UPGRADE), _k(Action.DECLINE_UPGRADE)
    sw = 40
    return [
        InfoText("Каждый уничтоженный враг оставляет на земле обломки: на них можно подлечиться. "
                 "Последний враг раунда может оставить ещё и останки улучшения, которое усиливает "
                 "вашу машину до конца боя."),
        InfoText(texts.GUIDE_EXPAND_HINT),

        SectionHeader("Обломки: лечение"),
        AccordionRow(make_swatch_icon(HEAL), "Обломки",
                     "Тёмный силуэт уничтоженной машины с едва заметным кругом вокруг. "
                     "Пока вы в круге, вы чините себя.", [
                         f"Обломки лежат {WRECK_LIFE_S:g} с, последние секунды они бледнеют.",
                         f"Заедьте в круг вокруг обломков (он шире самих обломков на {WRECK_ZONE_MARGIN_M:g} м) "
                         f"и пробудьте в нём {WRECK_HOLD_S:g} с: вокруг обломков идёт зелёная дуга прогресса.",
                         "Если выехать за круг раньше времени, отсчёт сбрасывается. "
                         "Если рядом несколько обломков, собираются они по одному.",
                         "При полном здоровье обломки не расходуются: они подождут, пока вы получите урон.",
                         "Подобрать можно и обломки, оставшиеся от прошлых врагов, пока они не пропали.",
                     ], col_w=sw),
        AccordionRow(None, "Сколько лечат",
                     "Зависит от класса уничтоженного врага: чем он толще, тем больше лечение.",
                     _heal_rows()),

        SectionHeader("Останки улучшений"),
        AccordionRow(make_swatch_icon(UPG_RING), "Как выпадают",
                     "Тёмный диск с цветным ромбом и жёлтой дугой оставшегося времени.", [
                         f"Выпадают только с раунда {UPGRADE_MIN_ROUND}.",
                         "Выпадают с последнего врага раунда. Если в один кадр погибло несколько врагов раунда, "
                         "берётся самый дорогой.",
                         "Улучшение зависит от класса этого врага (см. список ниже).",
                         "Если такое улучшение у вас уже на максимальном уровне, останки не выпадают.",
                         f"Лежат {UPGRADE_LIFE_S:g} с рядом с обломками. Если останки вне экрана, у края стоит "
                         "жёлтый треугольник с секундами до исчезновения.",
                     ], col_w=sw),
        AccordionRow(None, "Как взять",
                     "Подъедите к останкам: рядом с панелью улучшений появится карточка предложения.", [
                         f"[{take}] или кнопка «Взять» принимает улучшение, [{decline}] или кнопка «Отказаться» "
                         "убирает останки.",
                         "Если рядом несколько останков, предлагаются ближайшие.",
                         "Пока карточка открыта, выстрела по клику на неё не будет.",
                     ]),
        AccordionRow(None, "Ячейки и уровни",
                     f"Одновременно действуют до {SLOT_COUNT} улучшений, у каждого до {MAX_LEVEL} уровней.", [
                         "Улучшение, которое у вас уже есть, повышает свой уровень.",
                         "Новое улучшение занимает свободную ячейку.",
                         "Если все ячейки заняты, нужно выбрать ячейку для замены (щелчок по ней). "
                         f"Клавиша [{take}] в этом режиме не работает. Замена начинается с первого уровня.",
                         "Панель в правом нижнем углу показывает ячейки. Треугольник рядом раскрывает названия и эффекты.",
                         "Улучшения живут до конца партии.",
                     ]),

        SectionHeader("Список улучшений"),
        *_upgrade_rows(),
    ]