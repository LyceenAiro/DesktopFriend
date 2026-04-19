from register.Timeout import TimeoutRegisterInit
from register.MouseEvent import MouseEventRegisterInit
from register.Menu import MenuRegisterInit
from util.log import _log

def registerInit():
    _log.INFO("[Register]开始初始化注册器")
    TimeoutRegisterInit()
    MouseEventRegisterInit()
    MenuRegisterInit()
    # 初始化自动行走
    from Event.Ai.walk import auto_walk
    _log.INFO("[Register]注册器初始化完成")