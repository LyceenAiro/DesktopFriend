from util.log import _log
from ui.PetArt import PetArtList

def SetPetArt(self, Art):
    self.PetArt.setPixmap(PetArtList[Art])