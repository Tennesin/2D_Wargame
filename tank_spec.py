"""tank_spec.py — формулы конструктора: входные параметры -> все характеристики танка."""
import math
from core import PX_PER_M

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ---------- границы входных параметров (совпадают с ползунками в ui.py) ----------
CAL_MIN, CAL_MAX = 45.0, 175.0
FRONT_MIN, FRONT_MAX = 15.0, 500.0
SIDE_MIN, SIDE_MAX = 15.0, 375.0
REAR_MIN, REAR_MAX = 15.0, 250.0
POWER_MIN, POWER_MAX = 500.0, 1500.0
MASS_MIN, MASS_MAX = 25.0, 200.0

# ---------- эталонный танк (300/75/50, 750 л.с., 120 мм) ----------
REF_CAL = 120.0
REF_POWER = 750.0
REF_MASS = 65.0
REF_FILLING = 34.30        # масса «начинки» эталона (без брони), т
REF_ARMOR_MASS = 30.69     # масса брони эталона, т
REF_PW = 11.54             # удельная мощность эталона, л.с./т
REF_ARMOR_SHARE = 0.472    # доля брони в массе эталона

# ---------- прочее ----------
TURN_SPEED_PENALTY = 0.65  # множитель скорости при повороте (как раньше)
KMH_TO_PX = PX_PER_M * 1000.0 / 3600.0   # км/ч -> px/с (при 100 px = 1 м это ≈ 27.78)
TURRET_FRONT_M = 1.85      # от центра башни до места выхода ствола, м эталонного спрайта

class TankSpec:
    """Считает всё один раз в __init__. Имена в ЗАГЛАВНЫХ буквах читают Tank и Renderer."""

    def __init__(self, cal, front, side, rear, power):
        # --- 0. входные параметры (с защитой от выхода за границы) ---
        self.cal = _clamp(float(cal), CAL_MIN, CAL_MAX)
        self.front = _clamp(float(front), FRONT_MIN, FRONT_MAX)
        self.side = _clamp(float(side), SIDE_MIN, SIDE_MAX)
        self.rear = _clamp(float(rear), REAR_MIN, REAR_MAX)
        self.power = _clamp(float(power), POWER_MIN, POWER_MAX)
        self._calc()

    # ---------- фабрики ----------
    @classmethod
    def from_values(cls, v):
        """v — словарь из ConstructorUI.get_values()."""
        return cls(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                   v["rear_armor_mm"], v["engine_power_hp"])

    @classmethod
    def from_config(cls):
        """Танк из стартовых значений tank_config."""
        import tank_config as c
        return cls(c.GUN_CALIBER_MM, c.FRONT_ARMOR_THICKNESS_MM, c.SIDE_ARMOR_THICKNESS_MM,
                   c.REAR_ARMOR_THICKNESS_MM, c.ENGINE_POWER_HP)

    # ---------- расчёт ----------
    def _calc(self):
        cal, P = self.cal, self.power
        cr = cal / REF_CAL

        # 1. МАССА
        self.m_gun = 2.5 * (cal / 125.0) ** 2
        self.m_turret = 12.0 * cr ** 1.5
        self.m_engine = 4.0 * (P / REF_POWER)
        self.m_fixed = 16.0                                   # гусеницы 5 + каркас 11
        filling = self.m_fixed + self.m_engine + self.m_turret + self.m_gun
        k2 = (filling / REF_FILLING) ** (2.0 / 3.0)           # k^2: площади плит растут как k^2
        self.m_front = 0.03925 * self.front * k2
        self.m_side = 0.2355 * self.side * k2
        self.m_rear = 0.02512 * self.rear * k2
        self.m_armor = self.m_front + self.m_side + self.m_rear
        self.mass = _clamp(filling + self.m_armor, MASS_MIN, MASS_MAX)
        M = self.mass
        mr = M / REF_MASS

        # 2. ВНУТРЕННИЕ ПЕРЕМЕННЫЕ
        self.pw = P / M                                       # удельная мощность
        self.s = 1.0 - math.exp(-self.pw / 14.2)              # «ходовая отдача» 0..1
        self.q_pw = self.pw / REF_PW                          # мощность относительно эталона
        self.q_gun = cr / mr ** (1.0 / 3.0)                   # калибр относительно платформы
        self.q_arm = (self.m_armor / M) / REF_ARMOR_SHARE     # доля брони относительно эталона
        self.l_cal = _clamp(40.0 * mr ** 0.15, 30.0, 55.0)    # длина ствола в калибрах
        self.s_h = mr ** (1.0 / 3.0)                          # линейный размер танка

        # 3. ХОД И ПОВОРОТЫ
        self.v_max = _clamp(90.0 * self.s * (REF_MASS / M) ** 0.1, 8.0, 90.0)
        self.v_avg = self.v_max * (0.5 + 0.2 * self.s)
        self.v_back = min(0.3 * self.v_max, 25.0)
        self.hull_turn = _clamp(81.0 * self.s, 10.0, 80.0)
        self.turret_turn = _clamp(
            60.0 * self.q_gun ** -0.5 * self.q_pw ** 0.15 * (self.l_cal / 40.0) ** -0.3,
            15.0, 120.0)

        # 4. ОРУДИЕ
        lr = self.l_cal / 40.0
        self.damage = 400.0 * cr ** 2 * lr ** 0.3
        self.penetration = 350.0 * cr ** 0.8 * lr ** 0.5
        self.reload = max(0.5, 2.0 * cr * self.q_gun ** 0.5)

        # 5. HP
        self.hp = 2400.0 * mr ** 0.75 * (0.85 + 0.15 * self.q_arm)

        # 6. СТОИМОСТЬ И ВРЕМЯ ПРОИЗВОДСТВА
        e_armor = (self.m_armor / REF_ARMOR_MASS) ** 1.5
        e_hull = (self.m_fixed + self.m_turret) / 28.0
        e_engine = (P / REF_POWER) ** 1.3
        e_gun = cr ** 2.2
        self.cost = 500000.0 * (0.30 * e_armor + 0.15 * e_hull + 0.20 * e_engine + 0.35 * e_gun)
        self.build_time = 10.0 * (0.40 * e_armor + 0.20 * e_hull + 0.15 * e_engine + 0.25 * e_gun)

        # 7. ИМЕНА ДЛЯ Tank (те же, что он раньше читал из tank_config)
        self.FORWARD_SPEED_PX = self.v_max * KMH_TO_PX
        self.BACKWARD_SPEED_PX = self.v_back * KMH_TO_PX
        self.TURN_SPEED_PENALTY = TURN_SPEED_PENALTY
        self.HULL_ROTATION_SPEED = self.hull_turn
        self.TURRET_ROTATION_SPEED = self.turret_turn

        # 8. ВНЕШНИЙ ВИД (для Renderer)
        self.HULL_SCALE = self.s_h
        self.TURRET_SCALE = self.s_h * self.q_gun ** 0.25
        self.BARREL_LEN_M = cal * self.l_cal / 1000.0 * 0.85   # 120 мм × 40 кал. × 0,75 = 3,6 м
        self.BARREL_THICK_M = max(0.14, 0.26 * cr ** 0.7)      # чуть утолщён ради читаемости на малом зуме

        # 9. ВЫСТРЕЛ (всё зависит от калибра; размеры в мировых px, 100 px = 1 м)
        cal_k = _clamp((cal - CAL_MIN) / (CAL_MAX - CAL_MIN), 0.0, 1.0)   # 0..1 по диапазону калибров

        # где находится дульный срез от центра танка (px мира, с учётом масштаба башни)
        self.MUZZLE_DIST_PX = (TURRET_FRONT_M + self.BARREL_LEN_M) * self.TURRET_SCALE * PX_PER_M

        # снаряд
        self.SHELL_LEN_PX = 2.5 * cal                                  # 120 мм -> 300 px (3 м)
        self.SHELL_THICK_PX = 0.15 * cal                               # 120 мм -> 18 px (утолщён для читаемости)
        self.SHELL_SPEED_PX = 6000.0 * (self.l_cal / 40.0) ** 0.3
        self.SHELL_RANGE_PX = 3500.0                                   # дальше — взрыв, как при попадании в землю

        # откат ствола (метры эталонного спрайта)
        self.RECOIL_DEPTH_M = 0.12 + 0.0028 * cal                      # 120 мм -> ≈0,46 м
        self.RECOIL_TIME = 0.25 + cal / 400.0                          # полный цикл «назад и обратно», с

        # вспышка
        self.FLASH_SIZE_PX = 2.2 * cal
        self.FLASH_TIME = 0.07 + 0.05 * cal_k

        # дым
        self.SMOKE_TIME = 1.0 + 0.5 * cal_k                            # 1.0 .. 1.5 с
        self.SMOKE_STREAKS = 5 + int(cal / 20)                         # число полосок
        self.SMOKE_REACH_PX = 160.0 + 3.2 * cal                        # на сколько они расходятся
        self.SMOKE_WIDTH_PX = max(8.0, cal / 6.0)

        # взрыв снаряда и след на земле
        self.BLAST_SIZE_PX = 1.8 * cal                                 # диаметр огненного шара
        self.BLAST_TIME = 0.35 + 0.2 * cal_k
        self.BLAST_DIRT_COUNT = 6 + int(cal / 15)                      # комья земли
        self.SCORCH_RADIUS_PX = 0.9 * cal
        self.SCORCH_TIME = 4.0 + 2.0 * cal_k                           # пятно исчезает за 4–6 с

    # ---------- вывод в интерфейс и в консоль ----------
    def main_stats(self):
        """Расчётные характеристики: {название: готовая строка} (порядок = порядок в панели)."""
        return {
            "Стоимость": f"{self.cost:,.0f}".replace(",", " "),
            "Время производства": f"{self.build_time:.1f} с",
            "HP": f"{self.hp:,.0f}".replace(",", " "),
            "Масса": f"{self.mass:.1f} т",
            "Макс. скорость": f"{self.v_max:.0f} км/ч",
            "Средняя скорость": f"{self.v_avg:.0f} км/ч",
            "Скорость назад": f"{self.v_back:.0f} км/ч",
            "Поворот корпуса": f"{self.hull_turn:.0f} °/с",
            "Поворот башни": f"{self.turret_turn:.0f} °/с",
            "Урон": f"{self.damage:.0f}",
            "Пробитие": f"{self.penetration:.0f} мм",
            "Перезарядка": f"{self.reload:.2f} с",
        }

    def internal_stats(self):
        """Внутренние показатели (полезны при отладке баланса)."""
        return {
            "Удельная мощность": f"{self.pw:.1f} л.с./т",
            "Калибр / платформа": f"{self.q_gun:.2f}",
            "Бронированность": f"{self.q_arm:.2f}",
            "Длина ствола": f"{self.l_cal:.1f} кал.",
        }

    def print_specs(self):
        print("=" * 50)
        print("        ХАРАКТЕРИСТИКИ ТАНКА (TankSpec)")
        print("=" * 50)
        for name, text in {**self.main_stats(), **self.internal_stats()}.items():
            print(f"{name + ':':<24}{text}")
        print("=" * 50)