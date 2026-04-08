from register.Timeout import TimeoutRegisterInit
from register.MouseEvent import MouseEventRegisterInit
from register.Menu import MenuRegisterInit

def registerInit():
    TimeoutRegisterInit()
    MouseEventRegisterInit()
    MenuRegisterInit()
    # 初始化自动行走
    from Event.Ai.walk import auto_walk