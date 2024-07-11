from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QIcon, QAction

from Event.setting.system import *

from ui.PetWindow import DesktopPet, app

def menu_init(self: DesktopPet):
    self.menu = QMenu(self)
    
    stayTop = QAction("置顶", self, checkable=True)
    stayTop.setChecked(True)
    stayTop.triggered.connect(lambda: AppStayTop(self, stayTop))
    self.menu.addAction(stayTop)

    hide = QAction("隐藏", self)
    hide.triggered.connect(lambda: HideApp(self))
    self.menu.addAction(hide)

    quit = QAction("退出", self)
    quit.triggered.connect(lambda: QuitApp(self, app))
    self.menu.addAction(quit)

def tray_init(self: DesktopPet):
    self.tray_icon = QSystemTrayIcon(self)
    self.tray_icon.setIcon(QIcon("logo.png"))
    self.tray_icon.setContextMenu(self.menu)
    self.tray_icon.activated.connect(lambda reason: TrayIconActivated(reason, self))
    self.tray_icon.show()

def PetcontextMenuEvent(self: DesktopPet, event):
    # 右键事件
    self.menu.exec_(self.mapToGlobal(event.pos()))

