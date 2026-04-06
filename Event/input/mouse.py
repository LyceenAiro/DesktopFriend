from util.log import _log
from PySide6.QtGui import Qt, QCursor
from Event.Art.Pet import *
from Event.input.move import *

from ui.PetWindow import DesktopPet
from ui.PetArt import DEFAULT, PICKUP

def PickUpPet(self: DesktopPet):
    # 宠物被提起
    self.is_follow_mouse = True
    SetPetArt(self, PICKUP)
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
        self.move_count = 0
        self.Picktimer.start(300)

    event.accept() 

def PetDoubleClickEvent(self: DesktopPet, event):
    # 双击鼠标
    if self.move_count == 0:
        move_jump(self)

def PetmouseReleaseEvent(self: DesktopPet, event):
    # 松开鼠标
    if event.button() == Qt.LeftButton:
        # 左键事件
        self.Picktimer.stop()
        # self.setCursor(QCursor(Qt.ArrowCursor))
    if self.is_follow_mouse:
        SetPetArt(self, DEFAULT)
        self.setCursor(Qt.OpenHandCursor)
        self.is_follow_mouse = False
    event.accept()

def PetenterEvent(self: DesktopPet, event):
    # 触摸到
    self.setCursor(Qt.OpenHandCursor)