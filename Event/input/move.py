from util.log import _log
from Event.Art.Pet import *
from PySide6.QtCore import QTimer

from ui.PetWindow import DesktopPet, PetWindow
from ui.PetArt import DEFAULT, DEFAULT_R, WALK1, WALK2, WALK3, WALK4, WALK1_R, WALK2_R, WALK3_R, WALK4_R, JUMP


def _pause_exclusive_for_input(pet: DesktopPet):
    """保存并暂停独占动作，返回动作 ID。"""
    if hasattr(pet, 'action_system') and pet.action_system is not None:
        return pet.action_system.stop_exclusive_for_input()
    return None


def _resume_exclusive_for_input(pet: DesktopPet, action_id: str | None):
    """恢复之前因输入中断的独占动作。"""
    if action_id and hasattr(pet, 'action_system') and pet.action_system is not None:
        pet.action_system.resume_exclusive_from_input(action_id)


def move_clear(self: DesktopPet):
    self.move_count = 0
    if hasattr(self, 'Movetimer') and self.Movetimer:
        self.Movetimer.stop()
    _walk.stop()
    self.PetArt.setPixmap(PetArtList[DEFAULT])
    # 恢复独占动作或待机
    saved = getattr(self, '_saved_exclusive', None)
    if saved:
        _resume_exclusive_for_input(self, saved)
        self._saved_exclusive = None
    else:
        _restore_vanilla_idle(self)
    # 移动完成后重新启动自动行走定时器
    from Event.Ai.walk import auto_walk
    auto_walk.is_paused_due_to_action = False
    auto_walk.start_timer()


def _restore_vanilla_idle(pet: DesktopPet):
    """恢复动作系统的待机标记。"""
    if hasattr(pet, 'action_system') and pet.action_system is not None:
        pet.action_system._vanilla_idle_active = True


def move_left(self: DesktopPet):
    if self.move_count <= 0:
        _log.DEBUG("移动自然停止")
        move_clear(self)
    else:
        if not hasattr(self, '_saved_exclusive'):
            self._saved_exclusive = _pause_exclusive_for_input(self)
        _pause_vanilla_idle(self)
        _walk.start_left()


def move_right(self: DesktopPet):
    if self.move_count <= 0:
        _log.DEBUG("移动自然停止")
        move_clear(self)
    else:
        if not hasattr(self, '_saved_exclusive'):
            self._saved_exclusive = _pause_exclusive_for_input(self)
        _pause_vanilla_idle(self)
        _walk.start_right()


def _pause_vanilla_idle(pet: DesktopPet):
    if hasattr(pet, 'action_system') and pet.action_system is not None:
        pet.action_system._vanilla_idle_active = False


def move_jump(self: DesktopPet):
    _log.INFO("跳跃")
    if hasattr(self, 'jump_timer') and self.jump_timer:
        self.move_count = 0
        self.jump_timer.stop()

    self._saved_exclusive = _pause_exclusive_for_input(self)
    _pause_vanilla_idle(self)
    self.PetArt.setPixmap(PetArtList[JUMP])
    self.jump_timer = QTimer(self)
    self.jump_timer.setSingleShot(True)
    def on_jump_finished():
        self.PetArt.setPixmap(PetArtList[DEFAULT])
        saved = getattr(self, '_saved_exclusive', None)
        if saved:
            _resume_exclusive_for_input(self, saved)
            self._saved_exclusive = None
        else:
            _restore_vanilla_idle(self)
        # 跳跃完成后重新启动自动行走定时器
        from Event.Ai.walk import auto_walk
        auto_walk.is_paused_due_to_action = False
        auto_walk.start_timer()
    self.jump_timer.timeout.connect(on_jump_finished)
    self.jump_timer.start(150)


class move_event:
    def __init__(self, self_pet: DesktopPet):
        self.Pet = self_pet
        self.code = 0
        self.status = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_step)

    def move_init(self):
        self.code = 0
        self.status = 0

    def start_left(self):
        if self.status != 1:
            self.move_init()
            self.Pet.PetArt.setPixmap(PetArtList[WALK1])
        self.status = 1
        self.timer.start(self.Pet.move_timer)

    def start_right(self):
        if self.status != 2:
            self.move_init()
            self.Pet.PetArt.setPixmap(PetArtList[WALK1_R])
        self.status = 2
        self.timer.start(self.Pet.move_timer)

    def animate_step(self):
        self.code += 1

        if self.status == 1:
            if self.Pet.move_count <= 0:
                move_clear(self.Pet)
                return

            if self.Pet.x() - 2 < 0:
                _log.DEBUG("已经移动到最左侧了")
                self.Pet.move(0, self.Pet.y())
                move_clear(self.Pet)
                return

            _log.DEBUG(f"正在向左移动，距离计数器：{self.Pet.move_count}，动画码：{self.code}，距离原点：{self.Pet.origin_x}")

            if self.code == 1:
                self.Pet.PetArt.setPixmap(PetArtList[WALK1])
            elif self.code == 2:
                self.Pet.PetArt.setPixmap(PetArtList[WALK2])
            elif self.code == 3:
                self.Pet.PetArt.setPixmap(PetArtList[WALK3])
            elif self.code == 4:
                self.Pet.PetArt.setPixmap(PetArtList[WALK4])
                self.Pet.move_count -= 2
                self.Pet.origin_x -= 2
                self.Pet.move(self.Pet.x() - 2, self.Pet.y())
                self.Pet.PetArt.setPixmap(PetArtList[DEFAULT])
                self.code = 0
            else:
                self.code = 0

        elif self.status == 2:
            if self.Pet.move_count <= 0:
                move_clear(self.Pet)
                return

            if self.Pet.x() + 2 >= self.Pet.screen_max_x - self.Pet.width():
                _log.DEBUG("已经移动到最右侧了")
                self.Pet.move(self.Pet.screen_max_x - self.Pet.width(), self.Pet.y())
                move_clear(self.Pet)
                return

            _log.DEBUG(f"正在向右移动，距离计数器：{self.Pet.move_count}，动画码：{self.code}，距离原点：{self.Pet.origin_x}")

            if self.code == 1:
                self.Pet.PetArt.setPixmap(PetArtList[WALK1_R])
            elif self.code == 2:
                self.Pet.PetArt.setPixmap(PetArtList[WALK2_R])
            elif self.code == 3:
                self.Pet.PetArt.setPixmap(PetArtList[WALK3_R])
            elif self.code == 4:
                self.Pet.PetArt.setPixmap(PetArtList[WALK4_R])
                self.Pet.move_count -= 2
                self.Pet.origin_x += 2
                self.Pet.move(self.Pet.x() + 2, self.Pet.y())
                self.Pet.PetArt.setPixmap(PetArtList[DEFAULT_R])
                self.code = 0
            else:
                self.code = 0

    def stop(self):
        _log.DEBUG("移动停止")
        self.timer.stop()
        self.move_init()

_walk = move_event(PetWindow)
