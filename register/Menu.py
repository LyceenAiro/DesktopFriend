from ui.PetWindow import PetWindow
from Event.setting.menu import *

from util.log import _log

def MenuRegisterInit():
    PetWindow.RegistercontextMenuEvent(lambda self, event: PetcontextMenuEvent(self, event))
    PetWindow.RegisterMenu(lambda self: menu_init(self))
    PetWindow.RegisterTray(lambda self: tray_init(self))
    PetWindow.menu_init(PetWindow)
    PetWindow.tray_init(PetWindow)
    _log.INFO("Register Menu Success")