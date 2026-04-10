from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QIcon, QAction

from Event.setting.system import *

from Event.setting.system import _create_icon_from_base64
from resources.image_resources import LOGO_PNG

from ui.PetWindow import DesktopPet, app
from ui.UnifiedSettingsWindow import UnifiedSettingsWindow


def _open_settings_window(self: DesktopPet):
    existing = getattr(self, "settings_window", None)
    if existing is not None and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        return

    self.settings_window = UnifiedSettingsWindow(None)
    self.settings_window.show()
    self.settings_window.raise_()
    self.settings_window.activateWindow()

def menu_init(self: DesktopPet):
    self.menu = QMenu(self)

    hide = QAction("隐藏", self)
    hide.triggered.connect(lambda: HideApp(self))
    self.menu.addAction(hide)

    settings = QAction("设置", self)
    settings.triggered.connect(lambda: _open_settings_window(self))
    self.menu.addAction(settings)

    quit = QAction("退出", self)
    quit.triggered.connect(lambda: QuitApp(self, app))
    self.menu.addAction(quit)

def tray_init(self: DesktopPet):
    self.tray_icon = QSystemTrayIcon(self)
    self.tray_icon.setIcon(_create_icon_from_base64(LOGO_PNG))
    self.tray_icon.setContextMenu(self.menu)
    self.tray_icon.activated.connect(lambda reason: TrayIconActivated(reason, self))
    self.tray_icon.show()

def PetcontextMenuEvent(self: DesktopPet, event):
    # 右键事件
    self.menu.exec_(self.mapToGlobal(event.pos()))

