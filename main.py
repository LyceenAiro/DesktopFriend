import sys
from ui.PetWindow import PetWindow, app
from register import registerInit
from PySide6.QtCore import QTimer
from Event.setting.system import ShowApp
from ui.ErrorDialog import ErrorDialog
from util.log import _log

from warnings import filterwarnings
filterwarnings("ignore", category=DeprecationWarning)

def exception_hook(exc_type, exc_value, exc_traceback):
    """全局异常处理钩子"""
    if issubclass(exc_type, KeyboardInterrupt):
        # 忽略键盘中断
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # 记录错误日志
    _log.ERROR(f"未处理的异常: {exc_type.__name__}: {exc_value}")
    import traceback
    _log.ERROR("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
    # 显示错误对话框
    error_dialog = ErrorDialog(exc_type, exc_value, exc_traceback)
    error_dialog.exec()

if __name__ == "__main__":
    # 设置全局异常处理
    sys.excepthook = exception_hook
    registerInit()
    QTimer.singleShot(0, lambda: ShowApp(PetWindow))
    sys.exit(app.exec())