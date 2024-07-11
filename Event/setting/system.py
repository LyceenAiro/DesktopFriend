from util.log import _log
from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtGui import Qt

from ui.PetWindow import DesktopPet

def AppStayTop(self: DesktopPet, check):
    if check.isChecked():
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
    else:
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
    self.show()

def QuitApp(self: DesktopPet, app):
    # 退出程序
    app.exit()
    _log.INFO("成功退出了程序")

def HideApp(self: DesktopPet):
    # 隐藏程序
    self.hide()

def TrayIconActivated(reason, self: DesktopPet):
    if reason == QSystemTrayIcon.DoubleClick:
        # 双击触发
        self.show()
        self.activateWindow()
        _log.INFO("双击显示触发")