"""game/content/guide/page_controls.py — страница инструкции «Управление»."""
from inputs import Action, AMMO_HOTKEYS
from structures import ROTATE_SNAP_DEG
from ui import SectionHeader, KeyRow, make_mouse_icon
from vehicles.chassis.params import TRACK_REPAIR_S
from ...config import COMBAT_HOLD
from .common import k as _k

def build():
    combat_text = ("Боевой режим, пока клавиша зажата: появляется красная линия прицела и работает огонь."
                   if COMBAT_HOLD else
                   "Включить или выключить боевой режим: появляется красная линия прицела и работает огонь.")
    return [
        SectionHeader("Движение и прицел"),
        KeyRow([_k(Action.FORWARD), _k(Action.LEFT), _k(Action.BACKWARD), _k(Action.RIGHT)],
               "Движение корпуса: вперёд, влево, назад, вправо. Стрелки работают так же."),
        KeyRow([make_mouse_icon()],
               "Орудие следит за курсором. Если навести курсор на танк, стену или камень, "
               "появится краткая сводка."),
        KeyRow([_k(Action.LOCK_TURRET)],
               "Зафиксировать башню в текущем положении или снова отпустить."),

        SectionHeader("Бой"),
        KeyRow([_k(Action.COMBAT)], combat_text),
        KeyRow([make_mouse_icon("left")],
               "Выстрел. Работает только в боевом режиме; удерживайте кнопку для стрельбы по готовности."),
        KeyRow([_k(a) for a in AMMO_HOTKEYS],
               "Выбор снаряда: бронебойный, спецснаряд (кумулятивный или HESH), фугасный. "
               "То же делают кнопки справа от сводки танка."),
        KeyRow([_k(Action.REPAIR)],
               f"Ремонт сбитой гусеницы: {TRACK_REPAIR_S:.0f} с на гусеницу, по одной за раз."),

        SectionHeader("Камера"),
        KeyRow([make_mouse_icon("wheel")],
               "Колёсико мыши приближает и отдаляет вид. Клавиши + и − (PgUp, PgDn) делают то же."),
        KeyRow([make_mouse_icon()],
               "Камера плавно смещается к курсору: подведите мышь к краю экрана, чтобы заглянуть вперёд. "
               "Пока курсор у центра, камера стоит на танке."),
        KeyRow([_k(Action.TOGGLE_FREE_CAM), make_mouse_icon("right")],
               "Свободная камера: правая кнопка с перетаскиванием двигает вид. Повторное нажатие возвращает камеру к танку."),

        SectionHeader("Стены"),
        KeyRow([_k(Action.TOGGLE_BUILD)],
               "Режим стройки. Левая кнопка мыши ставит стену, правая выходит из режима. Танком в это время не управляют."),
        KeyRow([make_mouse_icon("left")],
               "Клик по стене выбирает её и открывает панель настроек. Белая точка в центре стены поворачивает её; "
               f"с Shift поворот идёт шагом {ROTATE_SNAP_DEG:.0f}°."),
        KeyRow([_k(Action.DELETE_WALL)], "Удалить выбранную стену."),

        SectionHeader("Прочее"),
        KeyRow([_k(Action.TOGGLE_DEBUG)], "Отладочная информация: FPS, координаты, сведения о ботах."),
        KeyRow([_k(Action.CANCEL)],
               "Закрывает по одному слою: стройку или панель стены, затем боевой режим, а потом выходит в меню."),
    ]