from register.Timeout import TimeoutRegisterInit
from register.MouseEvent import MouseEventRegisterInit
from register.Menu import MenuRegisterInit

def registerInit():
    TimeoutRegisterInit()
    MouseEventRegisterInit()
    MenuRegisterInit()