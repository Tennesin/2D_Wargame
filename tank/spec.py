"""tank/spec.py — формулы конструктора: входные параметры -> все характеристики танка."""
import math

from common import PX_PER_M, clamp
from .params import (
    PARAMS, REF_CAL, REF_POWER, REF_MASS, REF_FILLING, REF_ARMOR_MASS, REF_PW,
    REF_ARMOR_SHARE, TURN_SPEED_PENALTY, KMH_TO_PX, TURRET_FRONT_M,
    BARREL_VISIBLE_K, BARREL_THICK_REF_M, SHELL_LEN_K,
    FRONT_AREA_M2, SIDE_AREA_M2, REAR_AREA_M2, STEEL_T_PER_M3,
    HULL_COLL_HALF_W_M, HULL_COLL_HALF_L_M, HULL_COLL_SHIFT_M,
    ACCEL_K, ACCEL_MIN, ACCEL_MAX, ACCEL_TAIL_FLOOR, REVERSE_ACCEL_K,
    COAST_DECEL, BRAKE_DECEL, HULL_TURN_CAP, HULL_TURN_MIN, HULL_ALPHA_REF,
    HULL_ALPHA_MIN, HULL_ALPHA_MAX, GUN_ARM_BASE_M, GUN_ARM_BARREL_K,
    TURRET_TURN_REF, TURRET_TURN_MIN, TURRET_TURN_MAX, TURRET_POWER_EXP,
    TURRET_INERTIA_EXP, TURRET_SPINUP_REF, TURRET_RADIUS_M,
)

# Границы входов берём из params (раньше они дублировались здесь)
_CAL = PARAMS["gun_caliber_mm"]
_FRONT = PARAMS["front_armor_mm"]
_SIDE = PARAMS["side_armor_mm"]
_REAR = PARAMS["rear_armor_mm"]
_POWER = PARAMS["engine_power_hp"]

def _turret_inertia(m_turret, m_gun, size_k, barrel_len_m):
    """Момент инерции вращающейся части (башня + орудие), т·м²."""
    r_turret = TURRET_RADIUS_M * size_k
    r_gun = GUN_ARM_BASE_M * size_k + GUN_ARM_BARREL_K * barrel_len_m
    return m_turret * r_turret ** 2 + m_gun * r_gun ** 2

# инерция эталонной башни (120 мм, длина ствола 40 калибров) — точка отсчёта
REF_TURRET_INERTIA = _turret_inertia(12.0, 2.5, 1.0, 120.0 * 40.0 / 1000.0 * BARREL_VISIBLE_K)

class TankSpec:
    """Считает всё один раз в __init__. Имена в ЗАГЛАВНЫХ буквах читают Tank и Renderer."""

    def __init__(self, cal, front, side, rear, power):
        # входные параметры (с защитой от выхода за границы)
        self.cal = clamp(float(cal), _CAL.min, _CAL.max)
        self.front = clamp(float(front), _FRONT.min, _FRONT.max)
        self.side = clamp(float(side), _SIDE.min, _SIDE.max)
        self.rear = clamp(float(rear), _REAR.min, _REAR.max)
        self.power = clamp(float(power), _POWER.min, _POWER.max)
        self._calc()

    # ---------- фабрики ----------
    @classmethod
    def from_values(cls, v):
        """v — словарь из ConstructorUI.get_values()."""
        return cls(v["gun_caliber_mm"], v["front_armor_mm"], v["side_armor_mm"],
                   v["rear_armor_mm"], v["engine_power_hp"])

    @classmethod
    def from_config(cls):
        """Танк из стартовых значений (params.PARAMS[...].default)."""
        return cls(_CAL.default, _FRONT.default, _SIDE.default, _REAR.default, _POWER.default)

    # ---------- расчёт: порядок вызовов важен, каждый метод использует результаты предыдущих ----------
    def _calc(self):
        self._calc_mass()          # 1. масса
        self._calc_internal()      # 2. внутренние переменные
        self._calc_mobility()      # 3. ход и повороты
        self._calc_gun()           # 4. орудие
        self._calc_hp()            # 5. HP
        self._calc_economy()       # 6. стоимость и время
        self._calc_engine_names()  # 7. имена для Tank
        self._calc_visual()        # 8. внешний вид
        self._calc_collision()     # 9. размеры для столкновений
        self._calc_shot()          # 10. выстрел и эффекты

    def _calc_mass(self):
        cal, P = self.cal, self.power
        cr = cal / REF_CAL

        self.m_gun = 2.5 * (cal / 125.0) ** 2
        self.m_turret = 12.0 * cr ** 1.5
        self.m_engine = 4.0 * (P / REF_POWER)
        self.m_fixed = 16.0                                   # гусеницы 5 + каркас 11
        filling = self.m_fixed + self.m_engine + self.m_turret + self.m_gun
        self.size_k = (filling / REF_FILLING) ** (1.0 / 3.0)  # линейный размер, эталон ≈ 1.0
        k2 = self.size_k ** 2
        self.m_front = self.front / 1000.0 * FRONT_AREA_M2 * STEEL_T_PER_M3 * k2
        self.m_side = self.side / 1000.0 * SIDE_AREA_M2 * STEEL_T_PER_M3 * k2
        self.m_rear = self.rear / 1000.0 * REAR_AREA_M2 * STEEL_T_PER_M3 * k2
        self.m_armor = self.m_front + self.m_side + self.m_rear
        self.mass = filling + self.m_armor

    def _calc_internal(self):
        cal, P = self.cal, self.power
        cr = cal / REF_CAL
        M = self.mass

        self.pw = P / M                                       # удельная мощность
        self.s = 1.0 - math.exp(-self.pw / 14.2)              # «ходовая отдача» 0..1
        self.q_pw = self.pw / REF_PW                          # мощность относительно эталона
        self.q_gun = cr / self.size_k
        self.q_arm = (self.m_armor / M) / REF_ARMOR_SHARE     # доля брони относительно эталона
        self.l_cal = clamp(40.0 * self.size_k ** 0.45, 30.0, 55.0)  # k^0.45 = прежнее mr^0.15
        self.s_h = self.size_k

    def _calc_mobility(self):
        M = self.mass

        self.v_max = clamp(90.0 * self.s * (REF_MASS / M) ** 0.1, 8.0, 90.0)
        self.v_avg = self.v_max * (0.5 + 0.2 * self.s)
        self.v_back = min(0.3 * self.v_max, 25.0)
        # --- корпус: мощность против сопротивления грунта и инерции ---
        # момент сопротивления ~ M * size_k, момент тяги ~ P * size_k, инерция ~ M * size_k²
        self.q_turn = self.q_pw / self.size_k                     # 1.0 у эталона
        self.i_hull = (M / REF_MASS) * self.size_k ** 2           # инерция корпуса относительно эталона
        self.hull_turn = max(
            HULL_TURN_MIN,
            HULL_TURN_CAP * (1.0 - math.exp(-math.log(2.0) * self.q_turn)))   # эталон = CAP / 2
        self.hull_alpha = clamp(HULL_ALPHA_REF * self.q_turn, HULL_ALPHA_MIN, HULL_ALPHA_MAX)

        # --- башня: инерция башни и орудия, привод от двигателя ---
        barrel_len = self.cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K
        self.i_turret = _turret_inertia(self.m_turret, self.m_gun, self.size_k, barrel_len)
        i_rel = self.i_turret / REF_TURRET_INERTIA
        self.turret_turn = clamp(
            TURRET_TURN_REF * (self.power / REF_POWER) ** TURRET_POWER_EXP * i_rel ** -TURRET_INERTIA_EXP,
            TURRET_TURN_MIN, TURRET_TURN_MAX)
        self.turret_alpha = self.turret_turn / (TURRET_SPINUP_REF * i_rel ** 0.5)   # °/с²
        # разгон и торможение (км/ч в секунду)
        self.accel = clamp(ACCEL_K * self.pw, ACCEL_MIN, ACCEL_MAX)
        self.accel_back = self.accel * REVERSE_ACCEL_K
        self.decel_coast = COAST_DECEL
        self.decel_brake = BRAKE_DECEL
        self.t_avg = self.v_avg / self.accel                       # время разгона до средней скорости
        self.t_max = self._time_to_speed(self.v_max - 0.5)         # время разгона до (почти) максимальной

    def accel_at(self, v):
        """Ускорение (км/ч/с) при скорости v >= 0 км/ч.
        До v_avg постоянное, потом линейно падает к нулю у v_max (но не ниже доли ACCEL_TAIL_FLOOR)."""
        if v >= self.v_max:
            return 0.0
        if v <= self.v_avg:
            return self.accel
        tail = (self.v_max - v) / (self.v_max - self.v_avg)
        return self.accel * max(tail, ACCEL_TAIL_FLOOR)

    def _time_to_speed(self, target, dt=0.05):
        """Сколько секунд разгоняться с места до скорости target (численно, один раз при расчёте танка)."""
        v, t = 0.0, 0.0
        while v < target and t < 120.0:
            v += self.accel_at(v) * dt
            t += dt
        return t

    def _calc_gun(self):
        cr = self.cal / REF_CAL
        lr = self.l_cal / 40.0

        self.damage = 400.0 * cr ** 2 * lr ** 0.3
        self.penetration = 350.0 * cr ** 0.8 * lr ** 0.5
        self.reload = max(0.5, 2.0 * cr * self.q_gun ** 0.5)

        overload = max(0.0, self.q_gun - 1.15)
        self.reload *= 1.0 + 2.0 * overload

    def _calc_hp(self):
        mr = self.mass / REF_MASS

        self.hp = 2400.0 * mr ** 0.75 * (0.6 + 0.4 * self.q_arm)

    def _calc_economy(self):
        cr = self.cal / REF_CAL
        P = self.power

        e_armor = (self.m_armor / REF_ARMOR_MASS) ** 1.5
        e_hull = (self.m_fixed + self.m_turret) / 28.0
        e_engine = (P / REF_POWER) ** 1.3
        e_gun = cr ** 2.2
        self.cost = 500000.0 * (0.30 * e_armor + 0.15 * e_hull + 0.20 * e_engine + 0.35 * e_gun)
        self.build_time = 10.0 * (0.40 * e_armor + 0.20 * e_hull + 0.15 * e_engine + 0.25 * e_gun)

    def _calc_engine_names(self):
        """Имена, которые читает Tank (раньше он брал их из tank_config)."""
        self.FORWARD_SPEED_PX = self.v_max * KMH_TO_PX
        self.BACKWARD_SPEED_PX = self.v_back * KMH_TO_PX
        self.TURN_SPEED_PENALTY = TURN_SPEED_PENALTY
        self.HULL_ROTATION_SPEED = self.hull_turn
        self.TURRET_ROTATION_SPEED = self.turret_turn

    def _calc_visual(self):
        cal = self.cal
        cr = cal / REF_CAL

        self.HULL_SCALE = self.size_k
        self.TURRET_SCALE = self.size_k * clamp(cr ** 0.35, 0.8, 1.15)
        self.BARREL_LEN_M = round(cal * self.l_cal / 1000.0 * BARREL_VISIBLE_K / 0.25) * 0.25
        self.BARREL_THICK_M = max(0.18, BARREL_THICK_REF_M * cr ** 0.7)

    def _calc_collision(self):
        """Хитбоксы для столкновений (мировые px): корпус и ствол. Масштабируются вместе со спрайтами."""
        k = self.HULL_SCALE * PX_PER_M
        self.COLLISION_HALF_W_PX = HULL_COLL_HALF_W_M * k
        self.COLLISION_HALF_L_PX = HULL_COLL_HALF_L_M * k
        self.COLLISION_SHIFT_PX = HULL_COLL_SHIFT_M * k

        # ствол: прямоугольник вдоль оси башни, от торца маски орудия до дульного среза
        t = self.TURRET_SCALE * PX_PER_M
        self.BARREL_COLL_START_PX = TURRET_FRONT_M * t
        self.BARREL_COLL_END_PX = (TURRET_FRONT_M + self.BARREL_LEN_M) * t   # = MUZZLE_DIST_PX
        self.BARREL_COLL_HALF_W_PX = (self.BARREL_THICK_M + 0.08) * t / 2.0  # +8 см на эжектор

    def _calc_shot(self):
        """Всё, что зависит от калибра (размеры в мировых px, 100 px = 1 м)."""
        cal = self.cal
        cal_k = clamp((cal - _CAL.min) / (_CAL.max - _CAL.min), 0.0, 1.0)   # 0..1 по диапазону калибров

        # где находится дульный срез от центра танка (px мира, с учётом масштаба башни)
        self.MUZZLE_DIST_PX = (TURRET_FRONT_M + self.BARREL_LEN_M) * self.TURRET_SCALE * PX_PER_M

        # снаряд
        self.SHELL_LEN_PX = SHELL_LEN_K * cal                          # 120 мм -> 300 px (3 м)
        self.SHELL_THICK_PX = 0.15 * cal                               # 120 мм -> 18 px
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
            "Разгон до средней": f"{self.t_avg:.1f} с",
            "Разгон до макс.": f"{self.t_max:.1f} с",
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
            "Инерция башни": f"{self.i_turret:.1f} т·м²",
            "Угл. разгон корпуса": f"{self.hull_alpha:.0f} °/с²",
            "Угл. разгон башни": f"{self.turret_alpha:.0f} °/с²",
        }

    def print_specs(self):
        print("=" * 50)
        print("        ХАРАКТЕРИСТИКИ ТАНКА (TankSpec)")
        print("=" * 50)
        for name, text in {**self.main_stats(), **self.internal_stats()}.items():
            print(f"{name + ':':<24}{text}")
        print("=" * 50)