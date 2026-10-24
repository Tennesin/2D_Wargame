"""game/content/stats_tables.py — блоки таблиц для «Итогов боя» и «Статистики».
Принимает MatchStats или Career (у них одинаковые поля) и возвращает список блоков для TableScene."""
from ai import ARCHETYPES
from engine import fmt_num
from ui import SectionHeader, StatsBlock
from . import texts

AMMO_NAMES = ("AP", "HEAT", "HESH", "HE")

def _block(rows):
    """Блок «название ... значение» из словаря {название: строка}. Пустой словарь: одна строка-заглушка."""
    rows = rows or {texts.STATS_NONE: "—"}
    block = StatsBlock(list(rows))
    block.values.update(rows)
    return block

def _by_archetype(table):
    """{ключ архетипа: число} -> {имя архетипа: строка}, по убыванию, только значения больше нуля."""
    ranked = sorted(table.items(), key=lambda kv: -kv[1])
    return {ARCHETYPES[k].name: fmt_num(v) for k, v in ranked if k in ARCHETYPES and v > 0}

def _sections(d, marks=()):
    """Основные разделы. marks: ключи рекордов, которые нужно пометить («rounds», «damage», «kills»)."""
    def mark(key, text):
        return text + texts.STATS_RECORD_MARK if key in marks else text

    kills = {texts.STATS_TOTAL: mark("kills", fmt_num(d.kills_total))}
    kills.update(_by_archetype(d.kills))

    return [
        SectionHeader(texts.STATS_SEC_ROUNDS),
        _block({texts.STATS_ROUNDS: mark("rounds", fmt_num(d.rounds))}),

        SectionHeader(texts.STATS_SEC_DAMAGE),
        _block({texts.STATS_TOTAL: mark("damage", fmt_num(d.damage)),
                texts.STATS_BY_SHOTS: fmt_num(d.damage_shots),
                texts.STATS_BY_RAM: fmt_num(d.damage_ram)}),

        SectionHeader(texts.STATS_SEC_KILLS),
        _block(kills),

        SectionHeader(texts.STATS_SEC_FIRE),
        _block({texts.STATS_ACCURACY: f"{d.accuracy * 100:.0f}%",
                texts.STATS_HITS: fmt_num(d.hits),
                texts.STATS_SHOTS: fmt_num(d.shots_fired)}),

        SectionHeader(texts.STATS_SEC_AMMO),
        _block({texts.AMMO_RU[n]: fmt_num(d.ammo.get(n, 0)) for n in AMMO_NAMES}),

        SectionHeader(texts.STATS_SEC_TAKEN),
        _block({texts.STATS_TOTAL: fmt_num(d.taken),
                texts.STATS_FROM_SHOTS: fmt_num(d.taken_shots),
                texts.STATS_FROM_RAM: fmt_num(d.taken_ram)}),

        SectionHeader(texts.STATS_SEC_SOURCES),
        _block(_by_archetype(d.taken_from)),
    ]

def _records(career):
    r = career.records
    return [
        SectionHeader(texts.STATS_SEC_RECORDS),
        _block({texts.STATS_REC_ROUNDS: fmt_num(r["rounds"]),
                texts.STATS_REC_DAMAGE: fmt_num(r["damage"]),
                texts.STATS_REC_KILLS: fmt_num(r["kills"])}),
    ]

def result_items(stats, career):
    """Итоги одного боя; побитые рекорды помечены, внизу текущие рекорды."""
    return _sections(stats, stats.new_records) + _records(career)

def career_items(career):
    """Вкладка «Статистика»: всё накопленное и рекорды."""
    general = [SectionHeader(texts.STATS_SEC_GENERAL),
               _block({texts.STATS_MATCHES: fmt_num(career.matches)})]
    return general + _records(career) + _sections(career)