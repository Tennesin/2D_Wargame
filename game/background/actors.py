"""game/background/actors.py — актёры фона: техника и её «пилот» (маршрут, преследование, прицел, огонь).
Физику и стрельбу делает сама техника (Vehicle.update); пилот только формирует VehicleCommand."""
import math

from ai.movement.navigator import Navigator
from ai.movement.steering import steer_to, StuckGuard
from ai.tactics.gunnery import lead_point
from engine import (VehicleCommand, PX_PER_M, bearing_deg, heading_vector,
                    shortest_angle_diff, clamp)

LOOK_PX = 7.0 * PX_PER_M          # точка пути ближе этого считается пройденной (едем к следующей)
ARRIVE_PX = 3.0 * PX_PER_M        # так близко к последней точке: приехали
AIM_FAR_PX = 3000.0               # на каком расстоянии ставим точку прицела «в направлении»
EXIT_EXTRA_PX = 500.0             # запас за краем, куда уезжает техника после последней точки
CHASE_NEAR_PX = 6.0 * PX_PER_M    # ближе этого к своему месту в погоне выравниваемся по курсу цели
CATCH_UP_KMH_PER_M = 1.5          # прибавка скорости за каждый метр отставания от своего места
CATCH_UP_MAX_KMH = 35.0
STOP_KMH = 2.0
LEAD_K = 0.9                      # качество упреждения при наводке на другого актёра
NAV_AHEAD_PX = 15.0 * PX_PER_M    # на какую точку маршрута вперёд смотрит навигатор
FIRE_RANGE_K = 0.9                # стреляем по актёру или точке, только если снаряд долетит (доля дальности)

class Actor:
    def __init__(self, stage, vehicle):
        self.stage = stage
        self.v = vehicle
        self.done = False         # маршрут пройден до конца
        self.retired = False      # уехал за пределы экрана: убрать, как только скроется
        self.removed = False      # уже убран со сцены
        self._mode = "idle"       # idle / route / chase / spin / brake
        self._route = []
        self._i = 0
        self._exit_index = None
        self._speed_kmh = None
        self._target = None
        self._gap_px = 0.0
        self._lat_px = 0.0
        self._spin = 0.0
        self._aim = ("ahead", None)
        self._volleys = 0
        self._tol = 4.0
        self._fire_ttl = 0.0
        self.nav = Navigator(stage.rng)  # объезд камней, воды и других танков
        self.stuck = StuckGuard()  # если всё же застрял: короткий задний ход
        self._dt = 0.0

    @property
    def tank(self):
        """Навигатор ожидает у элементов fleet.bots поле .tank."""
        return self.v

    # ---------- вопросы для событий ----------
    def is_done(self):
        return self.done or self.removed

    def volley_done(self):
        return self._volleys <= 0

    def offscreen(self):
        """Техника целиком (с запасом на ствол) за краем экрана."""
        cam = self.stage.camera
        sx, sy = cam.world_to_screen(self.v.x, self.v.y)
        r = self.v.reach_px() * cam.zoom
        w, h = self.stage.size
        return sx < -r or sx > w + r or sy < -r or sy > h + r

    def far_away(self):
        """Потерялась далеко от камеры (страховка от вечных актёров)."""
        cam = self.stage.camera
        w, h = self.stage.size
        return math.hypot(self.v.x - cam.x, self.v.y - cam.y) > 2.5 * math.hypot(w, h) / cam.zoom

    # ---------- движение ----------
    def drive(self, route, speed=None, extend=True, face=True):
        """Ехать по маршруту (список мировых точек, см. Stage.route).
        speed: скорость в ширинах экрана в секунду (None: на полном газу).
        extend: после последней точки уехать за экран и исчезнуть. False: остановиться в последней точке.
        face: сразу развернуть корпус по маршруту (нужно при появлении, не посреди движения)."""
        self.nav.invalidate()
        pts = list(route)
        self._exit_index = None
        if extend and len(pts) >= 2:
            (px, py), (lx, ly) = pts[-2], pts[-1]
            d = math.hypot(lx - px, ly - py) or 1.0
            far = self.v.reach_px() + EXIT_EXTRA_PX
            self._exit_index = len(pts)
            pts.append((lx + (lx - px) / d * far, ly + (ly - py) / d * far))
        self._route, self._i = pts, 0
        self._speed_kmh = self.stage.kmh(speed) if speed else None
        self._mode = "route"
        self.done = False
        if face and len(pts) >= 2:
            self.v.hull_angle = bearing_deg(self.v.x, self.v.y, *pts[min(2, len(pts) - 1)]) % 360.0

    def chase(self, target, gap_m=25.0, lateral_m=0.0):
        """Ехать позади другого актёра на заданном расстоянии (lateral_m: смещение вправо от его курса)."""
        self.nav.invalidate()
        self._target = target
        self._gap_px = gap_m * PX_PER_M
        self._lat_px = lateral_m * PX_PER_M
        self._mode = "chase"
        self.done = False

    def spin(self, rate=1.0):
        """Вращаться на месте (rate -1..1)."""
        self._mode, self._spin = "spin", rate

    def brake(self):
        """Затормозить до остановки и стоять."""
        self._mode = "brake"

    def stop(self):
        self._mode = "idle"

    # ---------- прицел и огонь ----------
    def aim_ahead(self):
        self._aim = ("ahead", None)

    def aim_at(self, point):
        """Целиться в точку мира (используйте stage.pt(fx, fy))."""
        self._aim = ("point", point)

    def aim_dir(self, deg):
        """Целиться в сторону света: 0 вверх, 90 вправо, 180 вниз, 270 влево."""
        self._aim = ("dir", deg)

    def aim_actor(self, other):
        self._aim = ("actor", other)

    def snap_turret(self, abs_deg):
        """Мгновенно повернуть башню (чтобы не ждать долгий разворот в начале события)."""
        self.v.turret_rel_angle = (abs_deg - self.v.hull_angle) % 360.0

    def fire(self, count=1, tol=4.0, timeout=8.0):
        """Сделать count выстрелов, как только орудие довернётся к цели (допуск tol градусов).
        Не вышло за timeout секунд (цель вне сектора ПТ-САУ и т.п.): залп отменяется."""
        self._volleys, self._tol, self._fire_ttl = count, tol, timeout

    def cease_fire(self):
        self._volleys = 0

    # ---------- кадр (зовёт Stage) ----------
    def command(self, dt):
        self._dt = dt
        self.nav.tick(dt)
        throttle, steer = self._drive_inputs()
        aim = self._aim_point()
        fire = False
        if self._volleys > 0:
            reachable = self._aim_reachable(aim)
            if reachable:
                self._fire_ttl -= dt
            if self._fire_ttl <= 0.0:
                self._volleys = 0
            elif reachable:
                v = self.v
                err = shortest_angle_diff(bearing_deg(v.x, v.y, *aim), v.turret_angle)
                fire = abs(err) <= self._tol
        return VehicleCommand(throttle=throttle, steer=steer, aim_point=aim, fire=fire)

    def on_shot(self):
        if self._volleys > 0:
            self._volleys -= 1

    # ---------- внутреннее ----------
    def _heading_to(self, goal, want):
        """Курс к точке с объездом препятствий. Пути нет (или бюджет кадра выбран): напрямик."""
        ctx = self.stage.nav_ctx
        if ctx is None:
            return want
        heading, go = self.nav.drive_to(self.v, ctx, goal, want, no_breach=True)
        return want if go == 0.0 else heading

    def _guard(self, inputs):
        """Анти-застревание: заклинило, значит едем назад с поворотом."""
        throttle, steer = inputs
        pushing = throttle != 0.0 or steer != 0.0
        if self.stuck.update(self._dt, self.v, pushing, self.stage.rng):
            return -1.0, self.stuck.turn
        return throttle, steer

    def _nav_goal(self):
        """Точка маршрута примерно в NAV_AHEAD_PX впереди: к ней навигатор строит путь."""
        pts, v = self._route, self.v
        last = len(pts) - 1
        j = self._i
        while j < last and math.hypot(pts[j][0] - v.x, pts[j][1] - v.y) < NAV_AHEAD_PX:
            j += 1
        return pts[j]

    def _forward_point(self):
        fx, fy = heading_vector(self.v.hull_angle)
        return self.v.x + fx * AIM_FAR_PX, self.v.y + fy * AIM_FAR_PX

    def _aim_point(self):
        kind, arg = self._aim
        v = self.v
        if kind == "point":
            return arg
        if kind == "actor":
            if arg.removed:
                return self._forward_point()
            return lead_point(v, arg.v, LEAD_K)
        if kind == "dir":
            fx, fy = heading_vector(arg)
            return v.x + fx * AIM_FAR_PX, v.y + fy * AIM_FAR_PX
        return self._forward_point()

    def _throttle(self):
        if self._speed_kmh is None:
            return 1.0
        return clamp(self._speed_kmh / max(self.v.spec.v_max, 1.0), 0.1, 1.0)

    def _drive_inputs(self):
        mode = self._mode
        if mode == "route":
            return self._route_inputs()
        if mode == "chase":
            return self._chase_inputs()
        if mode == "spin":
            return 0.0, self._spin
        if mode == "brake":
            s = self.v.speed_kmh
            if s > STOP_KMH:
                return -1.0, 0.0          # противоположный газ = торможение
            if s < -STOP_KMH:
                return 1.0, 0.0
            self._mode = "idle"
        return 0.0, 0.0

    def _route_inputs(self):
        pts, v = self._route, self.v
        last = len(pts) - 1
        while self._i < last and math.hypot(pts[self._i][0] - v.x, pts[self._i][1] - v.y) < LOOK_PX:
            self._i += 1
        if self._exit_index is not None and self._i >= self._exit_index:
            self.retired = True               # проехали последнюю видимую точку: можно убирать за экраном
        tx, ty = pts[self._i]
        if self._i == last and math.hypot(tx - v.x, ty - v.y) < ARRIVE_PX:
            self.done = True
            self._mode = "brake"
            return 0.0, 0.0
        gx, gy = self._nav_goal()
        heading = self._heading_to((gx, gy), bearing_deg(v.x, v.y, gx, gy))
        return self._guard(steer_to(v, heading, self._throttle()))

    def _chase_inputs(self):
        t, v = self._target, self.v
        if t is None or t.removed or t.done:
            return self._leave_chase()
        tv = t.v
        fx, fy = heading_vector(tv.hull_angle)
        rx, ry = -fy, fx
        gx = tv.x - fx * self._gap_px + rx * self._lat_px      # своё место позади цели
        gy = tv.y - fy * self._gap_px + ry * self._lat_px
        dist = math.hypot(gx - v.x, gy - v.y)
        behind = (gx - v.x) * fx + (gy - v.y) * fy             # > 0: я отстал от своего места
        tspeed = abs(tv.speed_kmh)
        want = tspeed + clamp(behind / PX_PER_M * CATCH_UP_KMH_PER_M, -tspeed, CATCH_UP_MAX_KMH)
        if dist > CHASE_NEAR_PX:
            heading = self._heading_to((gx, gy), bearing_deg(v.x, v.y, gx, gy))
        else:
            heading = tv.hull_angle
        return self._guard(steer_to(v, heading, clamp(want / max(v.spec.v_max, 1.0), 0.0, 1.0)))

    def _leave_chase(self):
        """Цель исчезла: едем прямо, как ехали, и уходим со сцены."""
        v = self.v
        fx, fy = heading_vector(v.hull_angle)
        self._route = [(v.x, v.y), (v.x + fx * 40000.0, v.y + fy * 40000.0)]
        self._i, self._exit_index, self._speed_kmh = 1, None, None
        self._mode = "route"
        self.retired = True
        return self._route_inputs()

    def _aim_reachable(self, aim):
        """По актёру или точке стреляем, только когда снаряд долетит. Прицел «вперёд» и «в сторону» не ограничиваем."""
        if self._aim[0] not in ("actor", "point"):
            return True
        v = self.v
        return math.hypot(aim[0] - v.x, aim[1] - v.y) <= v.round_stats().range_px * FIRE_RANGE_K

    def in_range(self, other, k=FIRE_RANGE_K):
        """Дотянется ли мой снаряд до другого актёра (для условий yield в событиях)."""
        o = other.v
        return math.hypot(o.x - self.v.x, o.y - self.v.y) <= self.v.round_stats().range_px * k

    def visible(self, margin=0.04):
        """Техника целиком в пределах экрана (с отступом в долях)."""
        fx, fy = self.stage.frac(self.v.x, self.v.y)
        return margin <= fx <= 1.0 - margin and margin <= fy <= 1.0 - margin