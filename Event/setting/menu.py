from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QIcon, QAction

from Event.setting.system import *

from Event.setting.system import _create_icon_from_base64
from resources.image_resources import LOGO_PNG

from ui.PetWindow import DesktopPet, app
from ui.SettingsWindow import SettingsWindow
from ui.AboutWindow import AboutWindow
from ui.SmartConfigWindow import SmartConfigWindow

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

    settings = QAction("设置", self)
    settings.triggered.connect(lambda: SettingsWindow(self).exec())
    self.menu.addAction(settings)

    smart_config = QAction("智能配置", self)
    smart_config.triggered.connect(lambda: SmartConfigWindow(self).exec())
    self.menu.addAction(smart_config)

    about = QAction("关于", self)
    about.triggered.connect(lambda: AboutWindow(self).exec())
    self.menu.addAction(about)

def tray_init(self: DesktopPet):
    self.tray_icon = QSystemTrayIcon(self)
    self.tray_icon.setIcon(_create_icon_from_base64(LOGO_PNG))
    self.tray_icon.setContextMenu(self.menu)
    self.tray_icon.activated.connect(lambda reason: TrayIconActivated(reason, self))
    self.tray_icon.show()

def PetcontextMenuEvent(self: DesktopPet, event):
    # 右键事件
    self.menu.exec_(self.mapToGlobal(event.pos()))

