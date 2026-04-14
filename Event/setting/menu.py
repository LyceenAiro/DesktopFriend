from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from PySide6.QtGui import QAction

from Event.setting.system import *

from Event.setting.system import _create_icon_from_base64
from resources.image_resources import LOGO_PNG
from util.cfg import load_config
from util.i18n import tr

from ui.PetWindow import DesktopPet, app
from ui.UnifiedSettingsWindow import UnifiedSettingsWindow


MENU_STYLE = """
QMenu {
    background-color: #242424;
    color: #ececec;
    border: 1px solid #3a3a3a;
    border-radius: 10px;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 14px;
    margin: 1px 0px;
}
QMenu::item:selected {
    background-color: #4a2220;
    border: 1px solid #f95f53;
    color: #ffffff;
}
QMenu::item:disabled {
    color: #777777;
}
QMenu::separator {
    height: 1px;
    background: #3a3a3a;
    margin: 4px 4px;
}
"""


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


def _open_life_window(self: DesktopPet):
    from ui.life import LifeWindow

    existing = getattr(self, "life_window", None)
    if existing is not None and existing.isVisible():
        existing.raise_()
        existing.activateWindow()
        return

    self.life_window = LifeWindow(self)
    self.life_window.show()
    self.life_window.raise_()
    self.life_window.activateWindow()

def menu_init(self: DesktopPet):
    self.menu = QMenu(self)
    self.menu.setStyleSheet(MENU_STYLE)

    hide = QAction(tr("menu.hide"), self)
    hide.triggered.connect(lambda: HideApp(self))
    self.menu.addAction(hide)

    settings = QAction(tr("menu.settings"), self)
    settings.triggered.connect(lambda: _open_settings_window(self))
    self.menu.addAction(settings)

    life_panel = QAction(tr("menu.life"), self)
    life_panel.triggered.connect(lambda: _open_life_window(self))
    self.menu.addAction(life_panel)

    self.menu.addSeparator()

    quit = QAction(tr("menu.quit"), self)
    quit.triggered.connect(lambda: QuitApp(self, app))
    self.menu.addAction(quit)

    # 让菜单宽度略大于最宽文本，预留缩进空间
    fm = self.menu.fontMetrics()
    max_text_width = max(
        fm.horizontalAdvance(hide.text()),
        fm.horizontalAdvance(settings.text()),
        fm.horizontalAdvance(life_panel.text()),
        fm.horizontalAdvance(quit.text()),
    )
    self.menu.setMinimumWidth(max_text_width + 56)

    def _update_life_panel_visibility():
        enabled = bool(load_config("life").get("life_enabled", True))
        life_panel.setVisible(enabled)

    self.menu.aboutToShow.connect(_update_life_panel_visibility)

def tray_init(self: DesktopPet):
    self.tray_icon = QSystemTrayIcon(self)
    self.tray_icon.setIcon(_create_icon_from_base64(LOGO_PNG))
    self.tray_icon.setContextMenu(self.menu)
    self.tray_icon.activated.connect(lambda reason: TrayIconActivated(reason, self))
    self.tray_icon.show()

def PetcontextMenuEvent(self: DesktopPet, event):
    # 右键事件
    self.menu.exec_(self.mapToGlobal(event.pos()))

