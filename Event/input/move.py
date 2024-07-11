from util.log import _log
from Event.Art.Pet import *

from ui.PetWindow import DesktopPet

def move_clear(self: DesktopPet):
    self.move_count = 0
    self.Movetimer.stop()
    self.PetArt.setPixmap(PetArtList[0])

def move_left(self: DesktopPet):
    if self.move_count <= 0:
        _log.INFO("移动自然停止")
        move_clear(self)
    elif self.x() - 1 < 0:
        self.move(0, self.y())
        _log.INFO("已经移动到最左侧了")
        move_clear(self)
    else:
        self.move_count -= 1
        self.move(self.x() - 1, self.y())