"""game/match/control/clicks.py — клики по миру (интерфейс свои уже забрал): огонь и перетаскивание камеры."""
from inputs import MouseOwner

class ClickRouter:
    def __init__(self, input_handler, camera_ctrl, modes):
        self.input = input_handler
        self.camera_ctrl = camera_ctrl
        self.modes = modes

    def update(self):
        """При свободной камере ПКМ начинает перетаскивание. ЛКМ в боевом состоянии захватывает мышь под огонь."""
        for button, pos in self.input.pop_world_clicks():
            if button == 3 and self.camera_ctrl.free_camera:
                self.camera_ctrl.begin_pan(pos)
            elif button == 1 and self.modes.combat:
                self.input.grab_mouse(MouseOwner.FIRE, 1)
        self.camera_ctrl.update_pan()        # «чистый» ПКМ-клик в партии больше ничего не значит