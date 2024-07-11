from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtGui import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt as QtC

import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from ui.PetArt import *

from util.log import _log

# 所有Event类型请通过注册表注册使用

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('')
        # 清除窗口框体和任务栏图标
        self.setWindowFlag(Qt.FramelessWindowHint | self.windowFlags() | QtC.Tool)
        # 默认设置在顶层
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(200, 200)

        self.mouse_press_position = None
        self.is_follow_mouse = False

        # 行动点数
        self.move_count = 0

        # 图像初始化
        self.PetArt = QLabel(self)
        self.PetArt.setPixmap(PetArtList[0])
        self.PetArt.move(0, 0)

        # 定时器
        self.Picktimer = QTimer(self)
        self.Picktimer.setSingleShot(True)
    
    # 定时器注册
    def RegisterTimeout(self, callback): self.Picktimer.timeout.connect(callback)

    # 菜单界面和功能注册
    def RegisterMenu(self, callback): self.menu_init = callback
    def RegisterTray(self, callback): self.tray_init = callback
    # 菜单事件注册
    def RegistercontextMenuEvent(self, callback): self.context_Menu_callback = callback
    def contextMenuEvent(self, event): self.context_Menu_callback(self, event)

    ##
    ##  指针事件初始化
    ##
    ##  事件注册
    def RegistermouseDoubleClickEvent(self, callback): self.double_click_callback = callback
    def RegistermousePressEvent(self, callback): self.mouse_Press_callback = callback
    def RegistermouseReleaseEvent(self, callback): self.mouse_Release_callback = callback
    def RegistermouseMoveEvent(self, callback): self.mouse_Move_callback = callback
    def RegisterenterEvent(self, callback): self.enter_callback = callback
    ##  注册绑定
    def mouseDoubleClickEvent(self, event): self.double_click_callback(self, event)
    def mousePressEvent(self, event): self.mouse_Press_callback(self, event)
    def mouseReleaseEvent(self, event): self.mouse_Release_callback(self, event)
    def mouseMoveEvent(self, event): self.mouse_Move_callback(self, event)
    def enterEvent(self, event): self.enter_callback(self, event)

PetWindow = DesktopPet()