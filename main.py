import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog
from ui.ErrorDialog import ErrorDialog
from util.log import _log
from resources.image_resources import get_available_resource_packs, get_resource_pack_display_name, set_resource_pack

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

    QApplication.instance() or QApplication(sys.argv)

    resource_pack_items = [
        {
            "file": pack_name,
            "display": get_resource_pack_display_name(pack_name),
        }
        for pack_name in get_available_resource_packs()
    ]

    from ui.ResourcePackSelector import ResourcePackSelector
    selector = ResourcePackSelector(resource_pack_items)
    if selector.exec() != QDialog.DialogCode.Accepted:
        _log.INFO("用户取消资源包选择，程序退出")
        sys.exit(0)

    set_resource_pack(selector.selected_pack)
    _log.INFO(f"已选择资源包: {selector.selected_pack}")

    from ui.PetWindow import PetWindow, app
    from register import registerInit
    from Event.setting.system import ShowApp

    registerInit()
    QTimer.singleShot(0, lambda: ShowApp(PetWindow))
    sys.exit(app.exec())