from ui.PetWindow import PetWindow
from Event.input.mouse import *

from util.log import _log

def TimeoutRegisterInit():
    PetWindow.RegisterTimeout(lambda: PickUpPet(PetWindow))
    _log.INFO("Register Timeout Success")