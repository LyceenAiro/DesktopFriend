from ui.PetWindow import DesktopPet
from util.log import _log
from ui.PetArt import PetArtList

def SetPetArt(self: DesktopPet, Art: int):
    self.PetArt.setPixmap(PetArtList[Art])