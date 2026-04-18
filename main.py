import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog
from ui.ErrorDialog import ErrorDialog
from util.log import _log
from resources.image_resources import get_available_resource_packs, get_resource_pack_display_name, set_resource_pack
from util.cfg import init_config_dir, load_config, save_config
from util.i18n import attach_mod_lang_dirs_early

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
    app = QApplication.instance()
    error_dialog = ErrorDialog(exc_type, exc_value, exc_traceback, parent=None)
    error_dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    error_dialog.show()
    error_dialog.raise_()
    error_dialog.activateWindow()
    error_dialog.exec()

if __name__ == "__main__":
    # 设置全局异常处理
    sys.excepthook = exception_hook

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    init_config_dir()

    # 在任何 UI 模块导入之前加载 mod 语言文件，
    # 确保 class-level tab_name = tr(...) 能获取到 mod 翻译。
    _mod_lang_count = attach_mod_lang_dirs_early()
    if _mod_lang_count:
        _log.INFO(f"[i18n]提前加载了 {_mod_lang_count} 个 mod 语言目录")

    basic_config = load_config("basic")
    use_auto_pack = bool(basic_config.get("auto_load_resource_pack", False))
    default_pack = str(basic_config.get("default_resource_pack", "image.json"))
    selected_pack = None

    if use_auto_pack:
        available_packs = set(get_available_resource_packs())
        if default_pack not in available_packs:
            basic_config["auto_load_resource_pack"] = False
            basic_config["default_resource_pack"] = ""
            save_config("basic", basic_config)
            _log.WARN(f"默认资源包不存在，已清除自动加载设置: {default_pack}")
        else:
            try:
                set_resource_pack(default_pack)
                selected_pack = default_pack
                _log.INFO(f"自动加载默认资源包成功: {selected_pack}")
            except FileNotFoundError as exc:
                basic_config["auto_load_resource_pack"] = False
                basic_config["default_resource_pack"] = ""
                save_config("basic", basic_config)
                _log.WARN(f"默认资源包未找到，已清除自动加载设置: {default_pack}, 原因: {exc}")
            except Exception as exc:
                _log.WARN(f"自动加载默认资源包失败: {default_pack}, 原因: {exc}")

    if not selected_pack:
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
        selected_pack = selector.selected_pack
        _log.INFO(f"已选择资源包: {selected_pack}")

        if selector.remember_as_default:
            basic_config["auto_load_resource_pack"] = True
            basic_config["default_resource_pack"] = selected_pack
            save_config("basic", basic_config)
            _log.INFO(f"已设置默认资源包: {selected_pack}")

    from ui.PetWindow import PetWindow, app
    from module.life.runtime import start_life_loop, configure_tick_intervals, load_mods
    from register import registerInit
    from Event.setting.system import ShowApp

    debug_cfg = load_config("debug")
    normal_ms = int(debug_cfg.get("life_tick_interval_ms", 1000))
    afk_ms = int(debug_cfg.get("life_afk_tick_interval_ms", 5000))
    afk_timeout_s = int(debug_cfg.get("life_afk_timeout_s", 3600))
    configure_tick_intervals(normal_ms, afk_ms)

    registerInit()
    start_life_loop(app, interval_ms=normal_ms)
    load_mods()

    from util.idle_monitor import IdleMonitor
    IdleMonitor.start(app, afk_timeout_s=afk_timeout_s)

    QTimer.singleShot(0, lambda: ShowApp(PetWindow))
    sys.exit(app.exec())