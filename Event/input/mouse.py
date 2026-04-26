from util.log import _log
from PySide6.QtGui import Qt, QCursor
from Event.Art.Pet import *
from Event.input.move import *
from Event.Ai.walk import auto_walk

from ui.PetWindow import DesktopPet
from ui.PetArt import DEFAULT, PICKUP

def _get_action_system(pet: DesktopPet):
    return getattr(pet, 'action_system', None)

def PickUpPet(self: DesktopPet):
    # 宠物被提起
    _log.INFO("抓起")
    self.is_follow_mouse = True
    asys = _get_action_system(self)
    saved = None
    if asys:
        saved = asys.stop_exclusive_for_input()
        asys._vanilla_idle_active = False
    if saved:
        # 独占动作播放中：允许拖动但不切换图标（保持当前动画帧）
        pass
    else:
        SetPetArt(self, PICKUP)
    self._saved_exclusive = saved
    self.setCursor(QCursor(Qt.ClosedHandCursor))
    auto_walk.reset_idle()

def PetmouseMoveEvent(self: DesktopPet, event):
    # 移动过程时
    if Qt.LeftButton and self.is_follow_mouse:
        self.move(event.globalPos() - self.mouse_press_position)
    event.accept()

def PetmousePressEvent(self: DesktopPet, event):
    # 按住鼠标
    if event.button() == Qt.LeftButton:
        # 左键事件
        self.mouse_press_position = event.globalPos() - self.pos()
        self.move_count = 0
        self.Picktimer.start(300)

    event.accept() 

def PetDoubleClickEvent(self: DesktopPet, event):
    # 双击鼠标：独占动作播放时不响应跳跃
    if self.move_count == 0:
        asys = _get_action_system(self)
        if asys and asys._active_exclusive is not None:
            _log.DEBUG("[Input]独占动作播放中，跳过跳跃")
            return
        move_jump(self)

def PetmouseReleaseEvent(self: DesktopPet, event):
    # 松开鼠标
    if event.button() == Qt.LeftButton:
        # 左键事件
        self.Picktimer.stop()
        # self.setCursor(QCursor(Qt.ArrowCursor))
    if self.is_follow_mouse:
        _log.INFO("放下")
        SetPetArt(self, DEFAULT)

        self.setCursor(Qt.OpenHandCursor)
        self.is_follow_mouse = False
        auto_walk.reset_idle()
        # 恢复动作系统状态
        asys = _get_action_system(self)
        saved = getattr(self, '_saved_exclusive', None)
        if asys:
            if saved:
                asys.resume_exclusive_from_input(saved)
                self._saved_exclusive = None
            else:
                asys._vanilla_idle_active = True
        # 设置原点位置
        self.origin_x = 0
    event.accept()

def PetenterEvent(self: DesktopPet, event):
    # 触摸到
    self.setCursor(Qt.OpenHandCursor)