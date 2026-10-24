"""game/content/guide/page_enemies.py — страница инструкции «Враги»."""
from engine import VehicleKind
from ui import SectionHeader, InfoText, IconRow, make_swatch_icon
from vehicles import SPG_PARAMS
from vehicles.spg.params import SPG_RANGE_M, SPG_DEAD_K, SPG_RELOAD_S, SPG_HP_MIN, SPG_HP_MAX, \
    SPG_WALL_K, SPG_INNER_K
from ...hud.artillery_warning import RED
from ...match.rounds.schedule import ARTILLERY_PAIR_CHANCE
from .page_vehicles import vehicle_icon, VEHICLE_ICON_SIZE

def build():
    cal = SPG_PARAMS["gun_caliber_mm"]
    armor = SPG_PARAMS["front_armor_mm"]
    col = VEHICLE_ICON_SIZE[0]
    sw = 40
    return [
        InfoText("Здесь описана техника, которую нельзя собрать в Конструкторе: она бывает только у врагов. "
                 "Какие типы врагов появляются, настраивается в окне «Новая игра»."),
        SectionHeader("Артиллерия (САУ)"),
        IconRow(vehicle_icon(VehicleKind.SPG), "САУ — самоходная артиллерия",
                f"Хрупкая машина без башни: здоровье {SPG_HP_MIN:.0f}-{SPG_HP_MAX:.0f}, броня не толще "
                f"{armor.max:.0f} мм, калибр {cal.min:.0f}-{cal.max:.0f} мм. Стреляет только фугасами по дуге "
                f"на {SPG_RANGE_M[0]:.0f}-{SPG_RANGE_M[1]:.0f} м (чем крупнее калибр, тем дальше), поэтому "
                "стены и камни от её снарядов не защищают. Вокруг САУ есть мёртвая зона "
                f"({SPG_DEAD_K * 100:.0f}% дальности): вплотную она не стреляет и пытается отъехать. "
                f"Перезарядка {SPG_RELOAD_S[0]:.0f}-{SPG_RELOAD_S[1]:.0f} с.", col_w=col),

        SectionHeader("Предупреждение об ударе"),
        IconRow(make_swatch_icon(RED), "Красная зона",
                "После выстрела на земле появляется красный круг: это внешняя граница взрыва. Четыре треугольника "
                "сходятся к центру и исчезают в момент падения снаряда. Снаряд летит несколько секунд: "
                "успейте выехать из круга. Если зона за экраном, у края показывается красный указатель "
                "с секундами до падения.", col_w=sw),

        SectionHeader("Урон взрыва"),
        InfoText(f"В центре зоны (около {SPG_INNER_K * 100:.0f}% радиуса) цель получает полный урон и "
                 "оглушается: ехать и стрелять она не может. Дальше от центра урон падает и режется броней "
                 "той грани, что ближе к центру взрыва. Стены разрушаются с уроном "
                 f"×{SPG_WALL_K:g}. Если включён урон по союзникам, взрыв задевает и самих ботов."),

        SectionHeader("Когда появляется"),
        InfoText("В группе из одного врага САУ не бывает. В группе из двух она занимает слот с шансом "
                 f"{ARTILLERY_PAIR_CHANCE * 100:.0f}%, а в группе из трёх и более всегда занимает один слот. "
                 "Если в «Новой игре» оставить только артиллерию, эти правила не действуют."),
    ]