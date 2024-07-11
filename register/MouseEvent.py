from ui.PetWindow import PetWindow
from Event.input.mouse import *

from util.log import _log

def MouseEventRegisterInit():
    PetWindow.RegistermousePressEvent(lambda self, event: PetmousePressEvent(self, event))
    PetWindow.RegistermouseReleaseEvent(lambda self, event: PetmouseReleaseEvent(self, event))
    PetWindow.RegistermouseMoveEvent(lambda self, event: PetmouseMoveEvent(self, event))
    PetWindow.RegistermouseDoubleClickEvent(lambda self, event: PetDoubleClickEvent(self, event))
    PetWindow.RegisterenterEvent(lambda self, event: PetenterEvent(self, event))
    _log.INFO("Register Mouse Success")
   
