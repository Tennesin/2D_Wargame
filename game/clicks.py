"""game/clicks.py — распределяет клики по миру (интерфейс свои уже забрал) между частями игры."""
from inputs import MouseOwner
from .modes import Mode

class ClickRouter:
    def __init__(self, input_handler, camera, modes, camera_ctrl, wall_editor):
        self.input = input_handler
        self.camera = camera
        self.modes = modes
        self.camera_ctrl = camera_ctrl
        self.wall_editor = wall_editor

    def update(self):
        """При свободной камере ПКМ может оказаться началом перетаскивания, поэтому его обработка
        откладывается до отпускания кнопки: CameraController вернёт позицию «чистого» клика."""
        for button, pos in self.input.pop_world_clicks():
            if button == 3 and self.camera_ctrl.free_camera:
                self.camera_ctrl.begin_pan(pos)
            else:
                self._dispatch(button, pos)

        tap = self.camera_ctrl.update_pan()
        if tap is not None:
            self._dispatch(3, tap)

    def _dispatch(self, button, pos):
        """Что значит клик, решает режим."""
        wx, wy = self.camera.screen_to_world(*pos)
        if self.modes.mode == Mode.BUILD:
            self.wall_editor.click_build(button, wx, wy)
        else:
            self._click_play(button, pos, wx, wy)

    def _click_play(self, button, pos, wx, wy):
        """DRIVE и WALL_EDIT. ЛКМ: по белой точке вращает стену; иначе в боевом состоянии это огонь,
        а без него выбор стены. ПКМ здесь ничего не делает."""
        if button != 1:
            return
        if self.wall_editor.grab_rotate(pos):
            return
        if self.modes.combat:
            self.input.grab_mouse(MouseOwner.FIRE, 1)
        else:
            self.wall_editor.select_or_drive(wx, wy)