from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtGui import Qt
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt as QtC

import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from ui.PetArt import *

from util.log import _log
from util.version import version

# 所有Event类型请通过注册表注册使用

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()
        _log.INFO("初始化桌宠...")

        self.setWindowTitle('')
        # 清除窗口框体和任务栏图标
        self.setWindowFlag(Qt.FramelessWindowHint | self.windowFlags() | QtC.Tool)
        # 默认设置在顶层
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(128, 128)

        self.mouse_press_position = None
        self.is_follow_mouse = False

        # AI逻辑
        self.AutoMove = True
        self.auto_walk_on_show = True  # 隐藏/显示时的独立开关

        # 行动点数
        self.move_count = 0
        self.move_timer = 200

        # 原点位置（每次pickup结束后重置）
        self.origin_x = 0
        self.max_move_range = 20  # 最大移动范围

        # 图像初始化
        self.PetArt = QLabel(self)
        self.PetArt.setPixmap(PetArtList[DEFAULT])
        self.PetArt.move(0, 0)

        # 最大x坐标
        self.screen_max_x = self.ScreenMaxX()

        # 定时器
        self.Picktimer = QTimer(self)
        self.Picktimer.setSingleShot(True)

        _log.INFO(f"初始化完成")
        _log.INFO(f"当前版本: v{version}")
        _log.INFO(f"作者: LyceenAiro")
        _log.INFO(f"开源链接: github.com/LyceenAiro/DesktopFriend")
        _log.INFO(f"资源包名：艾罗 !!!请勿盗用!!!")
        _log.INFO(f"如果发现有任何问题均可在GitHub上提交issue或直接联系我")
        _log.INFO(f"该软件完全开源免费，禁止任何形式的二次销售！")

    # 屏幕最大X轴坐标
    def ScreenMaxX(self): return app.primaryScreen().size().width()
    
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