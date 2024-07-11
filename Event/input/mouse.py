from util.log import _log
from PySide6.QtGui import Qt, QCursor
from PySide6.QtCore import QTimer
from Event.Art.Pet import *
from Event.input.move import *

from ui.PetWindow import DesktopPet

def PickUpPet(self: DesktopPet):
    # 宠物被提起
    self.is_follow_mouse = True
    SetPetArt(self, 1)
    self.setCursor(QCursor(Qt.ClosedHandCursor))

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
        self.Picktimer.start(1000)
    event.accept()

def PetDoubleClickEvent(self: DesktopPet, event):
    # 双击鼠标
    if self.move_count == 0:
        if hasattr(self, 'Movetimer') and self.Movetimer:
            self.Movetimer.stop()
            self.Movetimer.timeout.disconnect()

        # Init
        self.Movetimer = QTimer(self)
        self.move_count = 30 # 移动长度

        _log.INFO("开始向左移动")
        SetPetArt(self, 2)
        self.Movetimer.timeout.connect(lambda: move_left(self))
        self.Movetimer.start(50)


def PetmouseReleaseEvent(self: DesktopPet, event):
    # 松开鼠标
    if event.button() == Qt.LeftButton:
        # 左键事件
        self.Picktimer.stop()
        # self.setCursor(QCursor(Qt.ArrowCursor))
    if self.is_follow_mouse:
        SetPetArt(self, 0)
        self.setCursor(Qt.OpenHandCursor)
        self.is_follow_mouse = False
    event.accept()

def PetenterEvent(self: DesktopPet, event):
    # 触摸到
    self.setCursor(Qt.OpenHandCursor)